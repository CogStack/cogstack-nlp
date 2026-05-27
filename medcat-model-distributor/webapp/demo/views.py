import sys
sys.path.insert(0, '/home/ubuntu/projects/MedCAT/')
import os
import requests
from django.shortcuts import render
from django.http import StreamingHttpResponse, HttpResponse, JsonResponse
from django.db import connection
from wsgiref.util import FileWrapper
from urllib.request import urlopen
from urllib.error import HTTPError
from .models import *
from .forms import DownloaderForm, UMLSApiKeyForm
from .decorators import require_valid_api_key

AUTH_CALLBACK_SERVICE = 'https://medcat.rosalind.kcl.ac.uk/auth-callback'
VALIDATION_BASE_URL = 'https://uts-ws.nlm.nih.gov/rest/isValidServiceValidate'
VALIDATION_LOGIN_URL = f'https://uts.nlm.nih.gov/uts/login?service={AUTH_CALLBACK_SERVICE}'

API_KEY_AUTH_URL = 'https://utslogin.nlm.nih.gov/cas/v1/api-key'
UMLS_SERVICE = 'http://umlsks.nlm.nih.gov'  # required as 'service' parameter
TEST_CUI = 'C0000005'  # harmless, public CUI for validation
CONTENT_API_URL = f'https://uts-ws.nlm.nih.gov/rest/content/current/CUI/{TEST_CUI}'

TPL_ENT = """<mark class="entity" v-on:click="show_info({id})" style="background: {bg}; padding: 0.12em 0.6em; margin: 0 0.25em; line-height: 1; border-radius: 0.35em; box-decoration-break: clone; -webkit-box-decoration-break: clone"> {text} <span style="font-size: 0.8em; font-weight: bold; line-height: 1; border-radius: 0.35em; text-transform: uppercase; vertical-align: middle; margin-left: 0.1rem">{label}</span></mark>"""
TPL_ENTS = """<div class="entities" style="line-height: 1.5; direction: {dir}">{content}</div>"""


medcat_version = "N/A"


def validate_umls_user(request):
    ticket = request.GET.get('ticket', '')
    validate_url = f'{VALIDATION_BASE_URL}?service={AUTH_CALLBACK_SERVICE}&ticket={ticket}'
    try:
        is_valid = urlopen(validate_url, timeout=10).read().decode('utf-8')
        context = {
            'is_valid': is_valid == 'true'
        }
        if is_valid == 'true':
            context['message'] = 'License verified! Please fill in the following form before downloading models.'
            context['downloader_form'] = DownloaderForm(MedcatModel.objects.all())
        else:
            context['message'] = f'License not found. Please request or renew your UMLS Metathesaurus License. If you think you have got the license, try {VALIDATION_LOGIN_URL} again.'
    except HTTPError:
        context = {
            'is_valid': False,
            'message': 'Something went wrong. Please try again.'
        }
    finally:
        context['medcat_version'] = medcat_version
        return render(request, 'umls_user_validation.html', context=context)


def validate_umls_api_key(request):
    if request.method == 'POST':
        form = UMLSApiKeyForm(request.POST)
        if form.is_valid():
            apikey = form.cleaned_data['apikey']
            try:
                # Step 1: Get TGT
                r = requests.post(API_KEY_AUTH_URL, data={'apikey': apikey}, timeout=10)
                if r.status_code != 201:
                    raise Exception('Invalid API key or auth server issue.')

                tgt_url = r.headers['Location']

                # Step 2: Get service ticket
                r = requests.post(tgt_url, data={'service': UMLS_SERVICE}, timeout=10)
                if r.status_code != 200:
                    raise Exception('Could not get service ticket.')

                service_ticket = r.text.strip()

                # Step 3: Use ticket to call a known endpoint
                params = {'ticket': service_ticket}
                r = requests.get(CONTENT_API_URL, params=params, timeout=10)

                if r.status_code == 200:
                    context = {
                        'is_valid': True,
                        'message': 'License verified via API key!',
                        'downloader_form': DownloaderForm(MedcatModel.objects.all())
                    }
                else:
                    context = {
                        'is_valid': False,
                        'message': 'API key is not valid or user is not licensed for UMLS.'
                    }

            except Exception as e:
                context = {
                    'is_valid': False,
                    'message': f'Error validating API key: {str(e)}'
                }

            context['medcat_version'] = medcat_version
            return render(request, 'umls_user_validation.html', context=context)
    else:
        form = UMLSApiKeyForm()

    return render(request, 'umls_api_key_entry.html',
                  {'form': form, 'medcat_version': medcat_version})


@require_valid_api_key
def model_after_api_key(request):
    context = {
        'is_valid': True,
        'message': f'Manually obtained API key is being used',
        'downloader_form': DownloaderForm(MedcatModel.objects.all())
    }
    context['medcat_version'] = medcat_version
    return render(request, 'umls_user_validation.html', context=context)


def download_model(request):
    if request.method == 'POST':
        downloader_form = DownloaderForm(MedcatModel.objects.all(), request.POST)
        if downloader_form.is_valid():
            mp_name = downloader_form.cleaned_data['modelpack']
            model = MedcatModel.objects.get(model_name=mp_name)
            if model is not None:
                mp_path = model.model_file.path
            else:
                return HttpResponse(f'Error: Unknown model "{downloader_form.modelpack}"')
            resp = StreamingHttpResponse(FileWrapper(open(mp_path, 'rb')))
            resp['Content-Type'] = 'application/zip'
            resp['Content-Length'] = os.path.getsize(mp_path)
            resp['Content-Disposition'] = f'attachment; filename={os.path.basename(mp_path)}'
            downloader_form.instance.downloaded_file = os.path.basename(mp_path)
            downloader_form.save()
            return resp
        else:
            context = {
                'is_valid': True,
                'downloader_form': downloader_form,
                'message': 'All non-optional fields must be filled out:'
            }
            context['medcat_version'] = medcat_version
            return render(request, 'umls_user_validation.html', context=context)
    else:
        return HttpResponse('Erorr: Unknown HTTP method.')


def report_health(request):
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    status = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "error", "db": db_ok}, status=status)
