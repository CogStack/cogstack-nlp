import sys
sys.path.insert(0, '/home/ubuntu/projects/MedCAT/')
import os
import json
import html
import requests
from django.shortcuts import render
from django.http import StreamingHttpResponse, HttpResponse
import numpy as np
from wsgiref.util import FileWrapper
from medcat import __version__ as medcat_version
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.vocab import Vocab
from urllib.request import urlretrieve, urlopen
from urllib.error import HTTPError
#from medcat.meta_cat import MetaCAT
from .models import *
from .forms import DownloaderForm, UMLSApiKeyForm

AUTH_CALLBACK_SERVICE = 'https://medcat.rosalind.kcl.ac.uk/auth-callback'
VALIDATION_BASE_URL = 'https://uts-ws.nlm.nih.gov/rest/isValidServiceValidate'
VALIDATION_LOGIN_URL = f'https://uts.nlm.nih.gov/uts/login?service={AUTH_CALLBACK_SERVICE}'

API_KEY_AUTH_URL = 'https://utslogin.nlm.nih.gov/cas/v1/api-key'
UMLS_SERVICE = 'http://umlsks.nlm.nih.gov'  # required as 'service' parameter
TEST_CUI = 'C0000005'  # harmless, public CUI for validation
CONTENT_API_URL = f'https://uts-ws.nlm.nih.gov/rest/content/current/CUI/{TEST_CUI}'

model_pack_path = os.getenv('MODEL_PACK_PATH', 'models/medmen_wstatus_2021_oct.zip')

try:
    cat = CAT.load_model_pack(model_pack_path)
except Exception as e:
    print(str(e))


TPL_ENT = """<mark class="entity" v-on:click="show_info({id})" style="background: {bg}; padding: 0.12em 0.6em; margin: 0 0.25em; line-height: 1; border-radius: 0.35em; box-decoration-break: clone; -webkit-box-decoration-break: clone"> {text} <span style="font-size: 0.8em; font-weight: bold; line-height: 1; border-radius: 0.35em; text-transform: uppercase; vertical-align: middle; margin-left: 0.1rem">{label}</span></mark>"""
TPL_ENTS = """<div class="entities" style="line-height: 1.5; direction: {dir}">{content}</div>"""


def doc2html(doc):
    markup = ""
    offset = 0
    text = doc.base.text

    for span in list(doc.linked_ents):
        start = span.base.start_char_index
        end = span.base.end_char_index
        fragments = text[offset:start].split("\n")

        for i, fragment in enumerate(fragments):
            markup += html.escape(fragment)
            if len(fragments) > 1 and i != len(fragments) - 1:
                markup += "</br>"
        ent = {'label': '', 'id': span.id,
               'bg': "rgb(74, 154, 239, {})".format(
                   span.context_similarity * span.context_similarity + 0.12),
               'text': html.escape(span.base.text)
               }
        # Add the entity
        markup += TPL_ENT.format(**ent)
        offset = end
    markup += html.escape(text[offset:])

    out = TPL_ENTS.format(content=markup, dir='ltr')

    return out


# NOTE: numpy uses np.float32 and those are not json serialisable
#       so we need to fix that
def fix_floats(in_dict: dict) -> dict:
    for k, v in in_dict.items():
        if isinstance(v, np.float32):
            in_dict[k] = float(v)
        elif isinstance(v, dict):
            fix_floats(v)
    return in_dict


def get_html_and_json(text):
    doc = cat(text)

    a = {
        "annotations": fix_floats(cat.get_entities(text)['entities']),
        "text": text,
    }
    for id, ent in a['annotations'].items():
        new_ent = {}
        for key in ent.keys():
            if key == 'pretty_name':
                new_ent['Pretty Name'] = ent[key]
            if key == 'icd10':
                icd10 = ent.get('icd10', [])
                new_ent['ICD-10 Code'] = icd10[-1] if icd10 else '-'
            if key == 'cui':
                new_ent['Identifier'] = ent[key]
            if key == 'types':
                new_ent['Type'] = ", ".join(ent[key])
            if key == 'acc':
                new_ent['Confidence Score'] = ent[key]
            if key == 'start':
                new_ent['Start Index'] = ent[key]
            if key == 'end':
                new_ent['End Index'] = ent[key]
            if key == 'id':
                new_ent['id'] = ent[key]
            if key == 'meta_anns':
                meta_anns = ent.get("meta_anns", {})
                if meta_anns:
                    for meta_ann in meta_anns.keys():
                        new_ent[meta_ann] = meta_anns[meta_ann]['value']

        a['annotations'][id] = new_ent

    doc_json = json.dumps(a)
    uploaded_text = UploadedText()
    uploaded_text.text = len(str(text))#str(text) no saving of text anymore
    uploaded_text.save()

    return doc2html(doc), doc_json


def show_annotations(request):
    context = {}
    context['doc_json'] = '{"msg": "No documents yet"}'

    if request.POST and 'text' in request.POST:
        doc_html, doc_json = get_html_and_json(request.POST['text'])

        context['doc_html'] = doc_html
        context['doc_json'] = doc_json
        context['text'] = request.POST['text']
    context['medcat_version'] = medcat_version
    return render(request, 'train_annotations.html', context=context)


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

            return render(request, 'umls_user_validation.html', context=context)
    else:
        form = UMLSApiKeyForm()

    return render(request, 'umls_api_key_entry.html', {'form': form})


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
