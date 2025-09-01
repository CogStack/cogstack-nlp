import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    name = 'api'

    def ready(self):
        from api.views import _submit_document
        from api.models import ProjectAnnotateEntities
        from . import signals
        resubmit_all = os.environ.get('RESUBMIT_ALL_ON_STARTUP', None)
        if resubmit_all is not None and resubmit_all.lower() in ('1', 'y', 'true'):
            logger.info('Found env var RESUBMIT_ALL_ON_STARTUP is True. '
                        'Attempting to resubmit all currently submitted state documents')

            projects = ProjectAnnotateEntities.objects.all()
            for project in projects:
                if project.project_status == 'A':
                    logger.info('Found project %s - in annotating state - resubmitting all validated documents...',
                                project.name)
                    validated_docs = project.validated_documents.all()
                    if len(validated_docs):
                        for doc in validated_docs:
                            try:
                                _submit_document(project, doc)
                                logger.info("Submitted doc: %s", doc.name)
                            except Exception as e:
                                logger.error("Failed to re-submit doc on startup with exception %s", e)
                    logger.info("Finished resubmitting Project %s", project.name)
        logger.info("MedCATTrainer App API ready...")
