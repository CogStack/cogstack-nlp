from django.contrib import admin
from django.urls import path
from .views import *

urlpatterns = [
    path('health', report_health, name='report-health'),
    path('auth-callback', validate_umls_user, name='validate-umls-user'),
    path('auth-callback-api', validate_umls_api_key, name='validate-umls-api-key'),
    path('download-model', download_model, name="download-model"),
    # manual API callback
    path('manual-api-callback/', model_after_api_key,
         name="model_after_api_key"),
]
