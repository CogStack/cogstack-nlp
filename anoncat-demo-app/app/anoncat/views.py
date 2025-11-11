from django.shortcuts import render
from medcat.cat import CAT
from rest_framework.decorators import api_view
from rest_framework.response import Response

from anoncat.models import DeidentifiedText
from app import settings

# Create your views here.

cat = CAT.load_model_pack(settings.DEID_MODEL) # Load a model

def index(request):
    return render(request, 'index.html')


@api_view(http_method_names=['POST'])
def deidentify(request):
    user = request.user

    if request.user.is_anonymous:
        return Response(status=404)

    input_text = request.data['text']
    redact = request.data['redact']
    output_text = deid_text(cat, input_text, redact=redact)

    # Save the form data to the DeidentifiedText model
    text = DeidentifiedText()
    text.input_text = input_text
    text.output_text = output_text
    text.save()

    return Response({'output_text': output_text})