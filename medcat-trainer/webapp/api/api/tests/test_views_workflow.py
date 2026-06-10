"""Tests for the annotation-workflow view endpoints in api.views.

Endpoints that only touch the database (add_annotation, update_meta_annotation,
create_dataset, submit_document without training) are exercised end-to-end.
Endpoints that need a loaded MedCAT model mock `api.views.get_medcat` /
`api.views.get_medcat_from_model_pack_id` so no model is loaded from disk.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ..models import (
    AnnotatedEntity,
    Dataset,
    Document,
    MetaAnnotation,
    MetaTask,
    MetaTaskValue,
    ModelPack,
)
from ._helpers import (
    create_basic_project,
    create_document,
    create_entity,
    create_user,
)


MEDIA_ROOT = '/tmp/mct-tests-workflow'


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AddAnnotationTests(TestCase):
    def setUp(self):
        self.user = create_user(username='annotator')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='add-anno-proj')
        self.document = create_document(self.project, name='doc', text='patient has asthma')

    def test_creates_annotation_for_source_value(self):
        resp = self.client.post(
            '/api/add-annotation/',
            {
                'project_id': self.project.id,
                'document_id': self.document.id,
                'source_value': 'asthma',
                'selection_occur_idx': 0,
                'cui': 'C100',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        ann_id = resp.json()['id']
        self.assertIsNotNone(ann_id)
        ann = AnnotatedEntity.objects.get(id=ann_id)
        self.assertEqual(ann.entity.label, 'C100')
        self.assertEqual(ann.value, 'asthma')


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class UpdateMetaAnnotationTests(TestCase):
    def setUp(self):
        self.user = create_user(username='meta-annotator')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='meta-proj')
        self.document = create_document(self.project, name='doc', text='hello world')
        self.entity = create_entity(label='C200')
        self.annotation = AnnotatedEntity.objects.create(
            user=self.user, project=self.project, document=self.document,
            entity=self.entity, value='hello', start_ind=0, end_ind=5, acc=1.0,
        )
        self.task = MetaTask.objects.create(name='Presence')
        self.value = MetaTaskValue.objects.create(name='True')

    def test_creates_meta_annotation_and_validates(self):
        resp = self.client.post(
            '/api/update-meta-annotation/',
            {
                'project_id': self.project.id,
                'entity_id': self.entity.id,
                'document_id': self.document.id,
                'meta_task_id': self.task.id,
                'meta_task_value': self.value.id,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.annotation.refresh_from_db()
        self.assertTrue(self.annotation.validated)
        self.assertTrue(self.annotation.correct)
        meta = MetaAnnotation.objects.get(annotated_entity=self.annotation)
        self.assertEqual(meta.meta_task_id, self.task.id)
        self.assertEqual(meta.meta_task_value_id, self.value.id)

    def test_updates_existing_meta_annotation(self):
        other_value = MetaTaskValue.objects.create(name='False')
        MetaAnnotation.objects.create(
            annotated_entity=self.annotation, meta_task=self.task,
            meta_task_value=other_value,
        )
        resp = self.client.post(
            '/api/update-meta-annotation/',
            {
                'project_id': self.project.id,
                'entity_id': self.entity.id,
                'document_id': self.document.id,
                'meta_task_id': self.task.id,
                'meta_task_value': self.value.id,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(MetaAnnotation.objects.filter(annotated_entity=self.annotation).count(), 1)
        meta = MetaAnnotation.objects.get(annotated_entity=self.annotation)
        self.assertEqual(meta.meta_task_value_id, self.value.id)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class CreateDatasetTests(TestCase):
    def setUp(self):
        self.user = create_user(username='dataset-creator')
        self.client = _auth_client(self.user)

    def test_creates_dataset_and_documents(self):
        resp = self.client.post(
            '/api/create-dataset/',
            {
                'dataset_name': 'my-dataset',
                'description': 'a test dataset',
                'dataset': {
                    'name': ['doc-1', 'doc-2'],
                    'text': ['first text', 'second text'],
                },
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        ds_id = resp.json()['dataset_id']
        ds = Dataset.objects.get(id=ds_id)
        self.assertEqual(ds.name, 'my-dataset')
        self.assertEqual(Document.objects.filter(dataset=ds).count(), 2)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SubmitDocumentTests(TestCase):
    def setUp(self):
        self.user = create_user(username='submitter')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='submit-proj')
        self.document = create_document(self.project, name='doc', text='hello world')

    def test_submit_without_training(self):
        self.project.train_model_on_submit = False
        self.project.save()
        resp = self.client.post(
            '/api/submit-document/',
            {'project_id': self.project.id, 'document_id': self.document.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.assertEqual(resp.json()['message'], 'Document submited successfully')

    def test_submit_with_training_invokes_medcat(self):
        with patch('api.views.get_medcat') as mock_get_medcat, \
                patch('api.views.train_medcat') as mock_train:
            mock_get_medcat.return_value = MagicMock()
            resp = self.client.post(
                '/api/submit-document/',
                {'project_id': self.project.id, 'document_id': self.document.id},
                format='json',
            )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        mock_train.assert_called_once()

    def test_submit_returns_500_on_error(self):
        with patch('api.views.get_medcat', side_effect=Exception('boom')):
            resp = self.client.post(
                '/api/submit-document/',
                {'project_id': self.project.id, 'document_id': self.document.id},
                format='json',
            )
        self.assertEqual(resp.status_code, 500)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SaveModelsTests(TestCase):
    def setUp(self):
        self.user = create_user(username='model-saver')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='save-proj')

    def test_save_models_persists_cdb(self):
        fake_cat = MagicMock()
        with patch('api.views.get_medcat', return_value=fake_cat):
            resp = self.client.post(
                '/api/save-models/',
                {'project_id': self.project.id},
                format='json',
            )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.assertEqual(resp.json()['message'], 'Models saved')
        fake_cat.cdb.save.assert_called_once()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AddConceptTests(TestCase):
    def setUp(self):
        self.user = create_user(username='concept-adder')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='add-concept-proj')
        self.document = create_document(self.project, name='doc', text='patient has asthma')

    def _payload(self, **overrides):
        payload = {
            'project_id': self.project.id,
            'document_id': self.document.id,
            'source_value': 'asthma',
            'selection_occur_idx': 0,
            'name': 'Asthma',
            'cui': 'C300',
            'context': '',
            'desc': '',
            'type_ids': [],
            'type': '',
            'synonyms': [],
        }
        payload.update(overrides)
        return payload

    def test_adds_new_concept_and_annotation(self):
        fake_cat = MagicMock()
        fake_cat.cdb.cui2info = {}
        fake_doc = MagicMock()
        fake_doc.text = self.document.text
        fake_doc.__iter__.return_value = iter([])
        fake_cat.return_value = fake_doc

        with patch('api.views.get_medcat', return_value=fake_cat), \
                patch('api.views.ensure_concept_searchable'):
            resp = self.client.post('/api/add-concept/', self._payload(), format='json')

        self.assertEqual(resp.status_code, 200, msg=resp.content)
        self.assertIn('id', resp.json())
        fake_cat.trainer.add_and_train_concept.assert_called_once()

    def test_rejects_existing_cui(self):
        fake_cat = MagicMock()
        fake_cat.cdb.cui2info = {'C300': {'preferred_name': 'Existing'}}

        with patch('api.views.get_medcat', return_value=fake_cat), \
                patch('api.views.ensure_concept_searchable'):
            resp = self.client.post('/api/add-concept/', self._payload(), format='json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('err', resp.json())


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class AnnotateTextTests(TestCase):
    def setUp(self):
        self.user = create_user(username='text-annotator')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='annotate-proj')

    def test_returns_400_without_message(self):
        resp = self.client.post(
            '/api/annotate-text/',
            {'project_id': self.project.id},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_modelpack_id_returns_400(self):
        with patch('api.views.get_medcat_from_model_pack_id', side_effect=ValueError):
            resp = self.client.post(
                '/api/annotate-text/',
                {'message': 'some text', 'modelpack_id': 'not-an-int'},
                format='json',
            )
        self.assertEqual(resp.status_code, 400)

    def test_missing_modelpack_returns_400(self):
        with patch('api.views.get_medcat_from_model_pack_id', side_effect=ModelPack.DoesNotExist):
            resp = self.client.post(
                '/api/annotate-text/',
                {'message': 'some text', 'modelpack_id': 999},
                format='json',
            )
        self.assertEqual(resp.status_code, 400)

    def test_annotates_text_with_project_model(self):
        fake_cat = MagicMock()
        fake_doc = MagicMock()
        fake_doc.linked_ents = []
        fake_cat.return_value = fake_doc

        with patch('api.views.get_medcat', return_value=fake_cat), \
                patch('api.views.temp_changed_config'):
            resp = self.client.post(
                '/api/annotate-text/',
                {'message': 'patient has asthma', 'project_id': self.project.id},
                format='json',
            )
        self.assertEqual(resp.status_code, 200, msg=resp.content)
        data = resp.json()
        self.assertEqual(data['message'], 'patient has asthma')
        self.assertEqual(data['entities'], [])
