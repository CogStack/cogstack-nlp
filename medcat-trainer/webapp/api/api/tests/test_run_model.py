"""Tests for running a project model over its dataset.

The project-list Run action and ``POST /api/run-model/`` both queue
``prep_docs``. ``background: false`` runs the same code in the request.
"""

import json
from unittest.mock import MagicMock, patch

from background_task.models import Task
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ..models import AnnotatedEntity, Document, Entity, ProjectAnnotateEntities
from ..utils import run_project_model
from ._helpers import create_basic_project, create_document, create_user


MEDIA_ROOT = '/tmp/mct-tests-run-model'


class _Ent:
    def __init__(self, text, cui, start, end, acc=0.9):
        self.text = text
        self.cui = cui
        self.start_char_index = start
        self.end_char_index = end
        self.context_similarity = acc


class _Doc:
    def __init__(self, ents):
        self.linked_ents = list(ents)


def _fake_cat():
    def predict(text):
        if 'asthma' in text:
            start = text.index('asthma')
            return _Doc([_Ent('asthma', 'C0004096', start, start + len('asthma'))])
        return _Doc([])

    cat = MagicMock(side_effect=predict)
    cat.config.components.linking.filters.cuis_exclude = set()
    cat.config.components.linking.similarity_threshold = 0.3
    return cat


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class RunModelApiTests(TestCase):
    def setUp(self):
        self.user = create_user(username='runner', is_staff=True)
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='run-model-proj')
        self.project.cuis = 'C0004096'
        self.project.save()
        self.pending = create_document(self.project, name='pending', text='asthma is present')
        self.annotated = create_document(self.project, name='annotated', text='asthma already marked')
        self.validated = create_document(self.project, name='validated', text='asthma was submitted')
        self.prepared = create_document(self.project, name='prepared', text='asthma was prepared')
        entity = Entity.objects.create(label='C999')
        AnnotatedEntity.objects.create(
            user=self.user, project=self.project, document=self.annotated,
            entity=entity, value='asthma', start_ind=0, end_ind=6, acc=1.0,
        )
        self.project.validated_documents.add(self.validated)
        self.project.prepared_documents.add(self.prepared)

    def _queued_doc_ids(self):
        task = Task.objects.get(queue='doc_prep')
        return json.loads(task.task_params)[0][1], task

    def test_background_run_queues_only_unprepared_documents(self):
        resp = self.client.post(
            '/api/run-model/',
            {'project_id': self.project.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        body = resp.json()
        self.assertEqual(body['status'], 'queued')
        self.assertEqual(body['documents_queued'], 1)
        self.assertFalse(body['already_running'])
        self.assertIsNotNone(body['bg_job_id'])

        doc_ids, task = self._queued_doc_ids()
        self.assertEqual(doc_ids, [self.pending.id])
        self.assertEqual(task.id, body['bg_job_id'])

        # The project-list Run button posts to the original path.
        again = self.client.post(
            '/api/prepare-documents-bg/',
            {'project_id': self.project.id},
            format='json',
        )
        self.assertEqual(again.status_code, 200, msg=again.content)
        self.assertTrue(again.json()['already_running'])
        self.assertEqual(again.json()['bg_job_id'], task.id)
        self.assertEqual(Task.objects.filter(queue='doc_prep').count(), 1)

    def test_legacy_task_list_includes_the_queued_run(self):
        self.client.post('/api/run-model/', {'project_id': self.project.id}, format='json')
        listed = self.client.get('/api/prep-docs-bg-tasks/')
        self.assertEqual(listed.status_code, 200, msg=listed.content)
        running = listed.json()['running_tasks']
        self.assertEqual(len(running), 1)
        self.assertEqual(running[0]['project'], self.project.id)
        self.assertEqual(running[0]['user_id'], self.user.id)

        same = self.client.get('/api/run-model/')
        self.assertEqual(same.json()['running_tasks'], running)

    @patch('api.utils.get_medcat')
    def test_worker_function_stores_predictions(self, mock_get_medcat):
        mock_get_medcat.return_value = _fake_cat()
        self.client.post('/api/run-model/', {'project_id': self.project.id}, format='json')
        doc_ids, _task = self._queued_doc_ids()

        processed = run_project_model(self.project.id, doc_ids, self.user.id)
        self.assertEqual(processed, 1)

        ann = AnnotatedEntity.objects.get(document=self.pending, project=self.project)
        self.assertEqual(ann.entity.label, 'C0004096')
        self.assertEqual(ann.value, 'asthma')
        self.assertFalse(ann.deleted)
        self.project.refresh_from_db()
        prepared_ids = set(self.project.prepared_documents.values_list('id', flat=True))
        self.assertIn(self.pending.id, prepared_ids)
        self.assertFalse(
            AnnotatedEntity.objects.filter(document=self.validated, project=self.project).exists()
        )
        self.assertEqual(
            AnnotatedEntity.objects.filter(document=self.annotated, project=self.project).count(),
            1,
        )

    @patch('api.utils.get_medcat')
    def test_sync_run_finishes_inside_the_request(self, mock_get_medcat):
        cat = _fake_cat()
        mock_get_medcat.return_value = cat
        resp = self.client.post(
            '/api/run-model/',
            {'project_id': str(self.project.id), 'background': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        body = resp.json()
        self.assertEqual(body['status'], 'complete')
        self.assertEqual(body['documents_queued'], 1)
        self.assertEqual(body['documents_prepared'], 1)
        self.assertEqual(body['documents_remaining'], 0)
        self.assertFalse(Task.objects.filter(queue='doc_prep').exists())
        self.assertEqual(cat.config.components.linking.filters.cuis, {'C0004096'})
        self.assertTrue(
            AnnotatedEntity.objects.filter(document=self.pending, entity__label='C0004096').exists()
        )

        status = self.client.get(f'/api/run-model/{self.project.id}/')
        self.assertEqual(status.status_code, 200, msg=status.content)
        self.assertEqual(status.json()['status'], 'complete')
        self.assertEqual(status.json()['proj_id'], self.project.id)
        self.assertEqual(status.json()['dataset_len'], 4)

    def test_string_false_runs_synchronously(self):
        with patch('api.utils.get_medcat', return_value=_fake_cat()):
            resp = self.client.post(
                '/api/prepare-documents-bg/',
                {'project_id': self.project.id, 'background': 'false'},
                format='json',
            )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.assertEqual(resp.json()['status'], 'complete')
        self.assertFalse(Task.objects.filter(queue='doc_prep').exists())

    def test_stop_removes_the_queued_task(self):
        started = self.client.post('/api/run-model/', {'project_id': self.project.id}, format='json')
        self.assertEqual(started.status_code, 200)
        status = self.client.get(f'/api/prep-docs-bg-tasks/{self.project.id}/')
        self.assertEqual(status.json()['status'], 'running')
        self.assertEqual(status.json()['bg_job_id'], started.json()['bg_job_id'])

        stopped = self.client.delete(f'/api/run-model/{self.project.id}/')
        self.assertEqual(stopped.status_code, 200, msg=stopped.content)
        self.assertEqual(stopped.json()['status'], 'stopped')
        self.assertFalse(Task.objects.filter(queue='doc_prep').exists())

        missing = self.client.delete(f'/api/run-model/{self.project.id}/')
        self.assertEqual(missing.status_code, 400)

        idle = self.client.get(f'/api/run-model/{self.project.id}/')
        self.assertEqual(idle.json()['status'], 'idle')
        self.assertEqual(idle.json()['documents_remaining'], 1)

    def test_anonymous_and_non_members_cannot_start_a_run(self):
        anon = APIClient()
        denied = anon.post('/api/run-model/', {'project_id': self.project.id}, format='json')
        self.assertIn(denied.status_code, (401, 403))

        outsider = create_user(username='outsider')
        resp = _auth_client(outsider).post(
            '/api/run-model/', {'project_id': self.project.id}, format='json',
        )
        self.assertEqual(resp.status_code, 403)

        member = create_user(username='member')
        self.project.members.add(member)
        allowed = _auth_client(member).post(
            '/api/run-model/', {'project_id': self.project.id}, format='json',
        )
        self.assertEqual(allowed.status_code, 200, msg=allowed.content)

    def test_missing_project_is_404(self):
        resp = self.client.post('/api/run-model/', {'project_id': 999999}, format='json')
        self.assertEqual(resp.status_code, 404)
        missing = self.client.get('/api/run-model/999999/')
        self.assertEqual(missing.status_code, 404)
        no_id = self.client.post('/api/run-model/', {}, format='json')
        self.assertEqual(no_id.status_code, 400)

    @patch('api.utils.call_remote_model_service')
    def test_remote_model_service_run(self, mock_remote):
        remote = ProjectAnnotateEntities.objects.create(
            name='remote-run-proj',
            dataset=self.project.dataset,
            use_model_service=True,
            model_service_url='http://medcat-service:8000',
            cuis='',
        )
        # The shared dataset's other documents are already annotated, validated, or prepared
        # on self.project only. This project has its own annotation state, so every dataset
        # document is eligible.
        mock_remote.return_value = _Doc([_Ent('asthma', 'C0004096', 0, 6)])
        resp = self.client.post(
            '/api/run-model/',
            {'project_id': remote.id, 'background': 0},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.assertEqual(resp.json()['documents_prepared'], Document.objects.filter(dataset=remote.dataset).count())
        self.assertGreater(mock_remote.call_count, 0)
        self.assertTrue(AnnotatedEntity.objects.filter(project=remote, entity__label='C0004096').exists())

    @patch('api.utils.get_medcat')
    def test_sync_run_with_nothing_left_does_not_load_the_model(self, mock_get_medcat):
        self.project.prepared_documents.add(self.pending)
        resp = self.client.post(
            '/api/run-model/',
            {'project_id': self.project.id, 'background': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.assertEqual(resp.json()['documents_queued'], 0)
        self.assertEqual(resp.json()['status'], 'complete')
        mock_get_medcat.assert_not_called()

    @patch('api.utils.get_medcat', side_effect=RuntimeError('model failed to load'))
    def test_sync_run_reports_model_errors(self, _mock_get_medcat):
        resp = self.client.post(
            '/api/run-model/',
            {'project_id': self.project.id, 'background': False},
            format='json',
        )
        self.assertEqual(resp.status_code, 500, msg=resp.content)
        self.assertEqual(resp.json()['status'], 'failed')
        self.assertIn('model failed to load', resp.json()['message'])
