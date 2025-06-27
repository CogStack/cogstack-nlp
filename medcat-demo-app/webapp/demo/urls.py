from django.contrib import admin
from django.urls import path
from .views import *

urlpatterns = [
    path('', show_annotations, name='train_annotations'),
    path('auth-callback', validate_umls_user, name='validate-umls-user'),
    path('auth-callback-api', validate_umls_api_key, name='validate-umls-api-key'),
    path('download-model', download_model, name="download-model")
]
