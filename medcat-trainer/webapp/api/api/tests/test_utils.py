"""Unit tests for api.utils.

Covers the pure-Python helpers (RemoteEntity, RemoteSpacyDoc, SimpleFilters,
env_str_to_bool, call_remote_model_service_* and add_annotations/
remove_annotations/create_annotation) without spinning up MedCAT itself.
"""

import os
from unittest.mock import patch, MagicMock

import requests
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from .. import utils
from ..models import AnnotatedEntity, Entity


class RemoteEntityTests(TestCase):
    """Tests for the RemoteEntity helper that mirrors spaCy's entity shape."""

    def test_constructs_from_full_payload(self):
        ent = utils.RemoteEntity(
            {
                'cui': 'C001',
                'start': 5,
                'end': 12,
                'detected_name': 'fever',
                'context_similarity': 0.92,
                'meta_anns': {'Presence': {'value': 'True'}},
            },
            'patient has fever now',
        )
        self.assertEqual(ent.cui, 'C001')
        self.assertEqual(ent.start_char_index, 5)
        self.assertEqual(ent.end_char_index, 12)
        self.assertEqual(ent.text, 'fever')
        self.assertEqual(ent.context_similarity, 0.92)
        self.assertEqual(ent.get_addon_data('meta_cat_meta_anns'), {'Presence': {'value': 'True'}})

    def test_falls_back_to_source_value_and_acc(self):
        ent = utils.RemoteEntity(
            {'cui': 'C002', 'source_value': 'cough', 'acc': 0.42},
            'cough',
        )
        self.assertEqual(ent.text, 'cough')
        self.assertEqual(ent.context_similarity, 0.42)
        self.assertEqual(ent.start_char_index, 0)
        self.assertEqual(ent.end_char_index, 0)

    def test_unknown_addon_key_returns_empty_dict(self):
        ent = utils.RemoteEntity({'cui': 'C003'}, 'text')
        self.assertEqual(ent.get_addon_data('some_other_key'), {})

    def test_defaults_when_payload_empty(self):
        ent = utils.RemoteEntity({}, '')
        self.assertEqual(ent.cui, '')
        self.assertEqual(ent.text, '')
        self.assertEqual(ent.context_similarity, 0.0)


class RemoteSpacyDocTests(TestCase):
    def test_wraps_linked_ents(self):
        ents = [utils.RemoteEntity({'cui': 'A'}, 'text'), utils.RemoteEntity({'cui': 'B'}, 'text')]
        doc = utils.RemoteSpacyDoc(ents)
        self.assertEqual(doc.linked_ents, ents)


class SimpleFiltersTests(TestCase):
    def test_default_empty_filters(self):
        f = utils.SimpleFilters()
        self.assertEqual(f.cuis, set())
        self.assertEqual(f.cuis_exclude, set())

    def test_custom_filters_preserved(self):
        f = utils.SimpleFilters(cuis={'X'}, cuis_exclude={'Y'})
        self.assertEqual(f.cuis, {'X'})
        self.assertEqual(f.cuis_exclude, {'Y'})


class EnvStrToBoolTests(TestCase):
    def _set_env(self, value):
        os.environ['__MCT_TEST_FLAG__'] = value
        self.addCleanup(os.environ.pop, '__MCT_TEST_FLAG__', None)

    def test_truthy_string_values(self):
        for v in ('1', 'true', 't', 'y', 'TRUE', 'True'):
            self._set_env(v)
            self.assertIs(utils.env_str_to_bool('__MCT_TEST_FLAG__', False), True, f'Expected True for {v}')

    def test_falsy_string_values(self):
        for v in ('0', 'false', 'f', 'n', 'False'):
            self._set_env(v)
            self.assertIs(utils.env_str_to_bool('__MCT_TEST_FLAG__', True), False, f'Expected False for {v}')

    def test_unknown_string_returns_value_unchanged(self):
        self._set_env('maybe')
        self.assertEqual(utils.env_str_to_bool('__MCT_TEST_FLAG__', True), 'maybe')

    def test_uses_default_when_not_set(self):
        os.environ.pop('__MCT_TEST_FLAG__', None)
        self.assertTrue(utils.env_str_to_bool('__MCT_TEST_FLAG__', True))
        self.assertFalse(utils.env_str_to_bool('__MCT_TEST_FLAG__', False))


class CallRemoteModelServiceSpacyTests(TestCase):
    """Tests for utils.call_remote_model_service_spacy with mocked requests."""

    @patch('api.utils.requests.post')
    def test_parses_spacy_response_into_remote_entities(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'entities': {
                    '0': {
                        'cui': 'C001',
                        'start': 0,
                        'end': 5,
                        'detected_name': 'fever',
                        'context_similarity': 0.9,
                    },
                    '1': {
                        'cui': 'C002',
                        'start': 6,
                        'end': 12,
                        'detected_name': 'cough',
                        'context_similarity': 0.8,
                    },
                }
            },
            raise_for_status=lambda: None,
        )

        doc = utils.call_remote_model_service_spacy('http://service:8000/', 'fever cough')
        self.assertEqual(len(doc.linked_ents), 2)
        cui_set = {e.cui for e in doc.linked_ents}
        self.assertEqual(cui_set, {'C001', 'C002'})

        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertEqual(call_args[0], 'http://service:8000/api/process')
        self.assertEqual(call_kwargs['json'], {'text': 'fever cough'})

    @patch('api.utils.requests.post')
    def test_request_failure_is_re_raised(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError('boom')
        with self.assertRaises(Exception) as ctx:
            utils.call_remote_model_service_spacy('http://service:8000', 'text')
        self.assertIn('Failed to call remote model service', str(ctx.exception))


class CallRemoteModelServiceMedcatTests(TestCase):
    @patch('api.utils.requests.post')
    def test_parses_medcat_response_into_remote_entities(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                'medcat_info': {'version': '1.0'},
                'result': {
                    'text': 'fever cough',
                    'annotations': [
                        {
                            '0': {'cui': 'C001', 'start': 0, 'end': 5, 'detected_name': 'fever', 'context_similarity': 0.9},
                            '1': {'cui': 'C002', 'start': 6, 'end': 12, 'detected_name': 'cough', 'context_similarity': 0.8},
                        }
                    ],
                },
            },
            raise_for_status=lambda: None,
        )
        doc = utils.call_remote_model_service_medcat('http://service:8000', 'fever cough')
        self.assertEqual(len(doc.linked_ents), 2)

    @patch('api.utils.requests.post')
    def test_raises_when_result_missing(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'medcat_info': {}},
            raise_for_status=lambda: None,
        )
        with self.assertRaises(Exception) as ctx:
            utils.call_remote_model_service_medcat('http://service:8000', 'text')
        self.assertIn("missing 'result'", str(ctx.exception))

    @patch('api.utils.requests.post')
    def test_raises_when_result_contains_errors(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {'result': {'errors': ['bad input']}},
            raise_for_status=lambda: None,
        )
        with self.assertRaises(Exception) as ctx:
            utils.call_remote_model_service_medcat('http://service:8000', 'text')
        self.assertIn('errors', str(ctx.exception))


class CallRemoteModelServiceDispatchTests(TestCase):
    """Top-level dispatcher should route by REMOTE_MODEL_SERVICE_TYPE."""

    def setUp(self):
        # Ensure we don't leak across tests
        self._original = os.environ.get('REMOTE_MODEL_SERVICE_TYPE')

    def tearDown(self):
        if self._original is None:
            os.environ.pop('REMOTE_MODEL_SERVICE_TYPE', None)
        else:
            os.environ['REMOTE_MODEL_SERVICE_TYPE'] = self._original

    @patch('api.utils.call_remote_model_service_spacy')
    def test_dispatches_to_spacy_by_default(self, mock_spacy):
        mock_spacy.return_value = 'doc'
        os.environ.pop('REMOTE_MODEL_SERVICE_TYPE', None)
        result = utils.call_remote_model_service('http://x', 'text')
        mock_spacy.assert_called_once_with('http://x', 'text')
        self.assertEqual(result, 'doc')

    @patch('api.utils.call_remote_model_service_medcat')
    def test_dispatches_to_medcat_when_configured(self, mock_mc):
        mock_mc.return_value = 'doc'
        os.environ['REMOTE_MODEL_SERVICE_TYPE'] = 'medcat'
        result = utils.call_remote_model_service('http://x', 'text')
        mock_mc.assert_called_once_with('http://x', 'text')
        self.assertEqual(result, 'doc')

    def test_unknown_service_type_raises(self):
        os.environ['REMOTE_MODEL_SERVICE_TYPE'] = 'unknown'
        with self.assertRaises(ValueError):
            utils.call_remote_model_service('http://x', 'text')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-utils')
class DbHelperTests(TestCase):
    """Tests for DB-backed helpers (remove_annotations / create_annotation /
    add_annotations) using lightweight in-memory fixtures.
    """

    def setUp(self):
        from ._helpers import create_basic_project, create_document, create_entity, create_user

        self.user = create_user(username='ann-user')
        self.project = create_basic_project(name='utils-test-project')
        self.document = create_document(self.project, name='doc1', text='fever and cough')
        self.entity = create_entity(label='C001')

    def _make_ann(self, validated=False):
        ann = AnnotatedEntity(
            user=self.user,
            project=self.project,
            document=self.document,
            entity=self.entity,
            value='fever',
            start_ind=0,
            end_ind=5,
            acc=0.9,
            validated=validated,
        )
        ann.save()
        return ann

    def test_remove_annotations_full_clears_all(self):
        self._make_ann(validated=True)
        self._make_ann(validated=False)
        utils.remove_annotations(self.document, self.project, partial=False)
        self.assertFalse(
            AnnotatedEntity.objects.filter(project=self.project, document=self.document).exists()
        )

    def test_remove_annotations_partial_keeps_validated(self):
        kept = self._make_ann(validated=True)
        unvalidated = self._make_ann(validated=False)

        utils.remove_annotations(self.document, self.project, partial=True)

        remaining = AnnotatedEntity.objects.filter(project=self.project, document=self.document)
        ids = {a.id for a in remaining}
        self.assertIn(kept.id, ids)
        self.assertNotIn(unvalidated.id, ids)

    def test_create_annotation_persists_manually_created(self):
        ann_id = utils.create_annotation(
            source_val='fever',
            selection_occurrence_index=0,
            cui='C001',
            user=self.user,
            project=self.project,
            document=self.document,
        )
        self.assertIsNotNone(ann_id)
        ann = AnnotatedEntity.objects.get(id=ann_id)
        self.assertEqual(ann.start_ind, 0)
        self.assertEqual(ann.end_ind, 5)
        self.assertTrue(ann.manually_created)
        self.assertTrue(ann.validated)
        self.assertTrue(ann.correct)

    def test_create_annotation_creates_new_entity_when_missing(self):
        self.assertFalse(Entity.objects.filter(label='C999').exists())
        utils.create_annotation(
            source_val='cough',
            selection_occurrence_index=0,
            cui='C999',
            user=self.user,
            project=self.project,
            document=self.document,
        )
        self.assertTrue(Entity.objects.filter(label='C999').exists())

    def test_create_annotation_returns_none_for_empty_cui(self):
        ann_id = utils.create_annotation(
            source_val='fever',
            selection_occurrence_index=0,
            cui='',
            user=self.user,
            project=self.project,
            document=self.document,
        )
        self.assertIsNone(ann_id)

    def test_add_annotations_with_simple_filters(self):
        spacy_doc = utils.RemoteSpacyDoc([
            utils.RemoteEntity({'cui': 'C001', 'start': 0, 'end': 5, 'detected_name': 'fever',
                                'context_similarity': 0.9}, 'fever and cough'),
            utils.RemoteEntity({'cui': 'C002', 'start': 10, 'end': 15, 'detected_name': 'cough',
                                'context_similarity': 0.85}, 'fever and cough'),
        ])

        utils.add_annotations(
            spacy_doc=spacy_doc,
            user=self.user,
            project=self.project,
            document=self.document,
            existing_annotations=[],
            cat=None,
            filters=utils.SimpleFilters(cuis={'C001'}),
            similarity_threshold=0.5,
        )

        anns = list(AnnotatedEntity.objects.filter(project=self.project, document=self.document))
        self.assertEqual(len(anns), 1)
        self.assertEqual(anns[0].entity.label, 'C001')

    def test_add_annotations_marks_low_acc_as_deleted(self):
        spacy_doc = utils.RemoteSpacyDoc([
            utils.RemoteEntity({'cui': 'C100', 'start': 0, 'end': 5, 'detected_name': 'fever',
                                'context_similarity': 0.1}, 'fever and cough'),
        ])

        utils.add_annotations(
            spacy_doc=spacy_doc,
            user=self.user,
            project=self.project,
            document=self.document,
            existing_annotations=[],
            cat=None,
            filters=utils.SimpleFilters(),
            similarity_threshold=0.3,
        )

        ann = AnnotatedEntity.objects.get(entity__label='C100')
        self.assertTrue(ann.deleted)
        self.assertTrue(ann.validated)

    def test_add_annotations_respects_excludes(self):
        spacy_doc = utils.RemoteSpacyDoc([
            utils.RemoteEntity({'cui': 'C200', 'start': 0, 'end': 5, 'detected_name': 'fever',
                                'context_similarity': 0.9}, 'fever and cough'),
            utils.RemoteEntity({'cui': 'C201', 'start': 10, 'end': 15, 'detected_name': 'cough',
                                'context_similarity': 0.9}, 'fever and cough'),
        ])

        utils.add_annotations(
            spacy_doc=spacy_doc,
            user=self.user,
            project=self.project,
            document=self.document,
            existing_annotations=[],
            cat=None,
            filters=utils.SimpleFilters(cuis_exclude={'C200'}),
            similarity_threshold=0.5,
        )

        labels = {a.entity.label for a in AnnotatedEntity.objects.filter(project=self.project,
                                                                          document=self.document)}
        self.assertIn('C201', labels)
        self.assertNotIn('C200', labels)
