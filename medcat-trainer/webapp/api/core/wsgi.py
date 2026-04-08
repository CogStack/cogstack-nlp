"""
WSGI config for MedCATTrainer project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/howto/deployment/wsgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Initialize OpenTelemetry before Django so uwsgi/gunicorn get tracing (manage.py only runs for CLI).
if os.environ.get('MCT_ENABLE_TRACING', 'False').lower() == 'true':
    from opentelemetry.instrumentation import auto_instrumentation

    auto_instrumentation.initialize()

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
