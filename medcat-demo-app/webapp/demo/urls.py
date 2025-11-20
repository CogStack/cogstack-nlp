from django.contrib import admin
from django.urls import path
from .views import *
from .questionnaire import (
    get_client_identifier, get_questionnaire, submit_questionnaire, check_api_key)

urlpatterns = [
    path('', show_annotations, name='train_annotations'),
    path('auth-callback', validate_umls_user, name='validate-umls-user'),
    path('auth-callback-api', validate_umls_api_key, name='validate-umls-api-key'),
    path('download-model', download_model, name="download-model"),
    # questionnaire
    path('umls-license-questionnaire/get-client-id', get_client_identifier,
         name="get-client-identifier"),
    path('umls-license-questionnaire/', get_questionnaire,
         name="get-questionnaire"),
    path('umls-license-questionnaire/submit-questionnaire', submit_questionnaire,
         name="submit-questionnaire"),
    path('umls-license-questionnaire/check-api-key', check_api_key,
         name="check-api-key"),
    path('callback-after-questionnaire', model_after_api_key,
         name="model_after_api_key"),
]
