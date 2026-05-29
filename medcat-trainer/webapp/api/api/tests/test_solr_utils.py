"""Unit tests for api.solr_utils using mocked HTTP calls."""

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from .. import solr_utils
from ..models import ConceptDB
from ._helpers import dataset_signals_disconnected  # noqa: F401  (ensures helper module imports)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-solr')
class CollectionsAvailableTests(TestCase):
    def setUp(self):
        # Clear schema cache to avoid leakage between tests
        solr_utils.SOLR_INDEX_SCHEMA.clear()

    @patch('api.solr_utils.requests.get')
    def test_returns_imported_map_when_cdbs_provided(self, mock_get):
        # First call: list collections; subsequent: schema
        def side_effect(url, *args, **kwargs):
            if 'admin/collections' in url:
                return MagicMock(status_code=200, text=json.dumps({'collections': ['my_id_1']}))
            if 'schema' in url:
                return MagicMock(text=json.dumps({'schema': {'fields': [{'name': 'cui', 'type': 'string'}]}}))
            return MagicMock(status_code=404, text='')

        mock_get.side_effect = side_effect

        response = solr_utils.collections_available(['1', '2'])
        self.assertEqual(response.status_code, 200)
        body = response.data
        self.assertTrue(body['results']['1'])
        self.assertFalse(body['results']['2'])

    @patch('api.solr_utils.requests.get')
    def test_returns_full_collection_info_when_no_cdbs(self, mock_get):
        def side_effect(url, *args, **kwargs):
            if 'admin/collections' in url:
                return MagicMock(status_code=200, text=json.dumps({'collections': ['my_id_1']}))
            return MagicMock(text=json.dumps({'schema': {'fields': [{'name': 'cui', 'type': 'string'}]}}))

        mock_get.side_effect = side_effect

        response = solr_utils.collections_available([])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results']['1']['index_name'], 'my_id_1')

    @patch('api.solr_utils.requests.get')
    def test_returns_500_when_solr_admin_unavailable(self, mock_get):
        mock_get.return_value = MagicMock(status_code=500, text='boom')
        response = solr_utils.collections_available(['1'])
        self.assertEqual(response.status_code, 500)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-solr')
class SearchCollectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cdb = ConceptDB(name='solrcdb', cdb_file='solrcdb.dat')
        cdb.save(skip_load=True)
        cls.cdb = cdb

    def setUp(self):
        solr_utils.SOLR_INDEX_SCHEMA.clear()
        solr_utils.SOLR_INDEX_SCHEMA[f'solrcdb_id_{self.cdb.id}'] = {'cui': 'string'}

    def test_empty_query_returns_empty_results(self):
        response = solr_utils.search_collection([self.cdb.id], '')
        self.assertEqual(response.data, {'results': []})

    @patch('api.solr_utils.requests.get')
    def test_returns_documents_for_text_query(self, mock_get):
        mock_get.return_value = MagicMock(
            text=json.dumps({
                'response': {
                    'docs': [
                        {
                            'cui': ['C001'],
                            'pretty_name': ['Concept 1'],
                            'type_ids': ['T001'],
                            'synonyms': ['c1', 'c-one'],
                        },
                        {
                            'cui': ['C002'],
                            'pretty_name': ['Concept 2'],
                            'type_ids': ['T002'],
                            'synonyms': ['c2'],
                        },
                    ]
                }
            })
        )

        response = solr_utils.search_collection([self.cdb.id], 'foo')
        results = response.data['results']
        cuis = sorted(r['cui'] for r in results)
        self.assertEqual(cuis, ['C001', 'C002'])

    @patch('api.solr_utils.requests.get')
    def test_falls_back_to_wildcard_when_no_results(self, mock_get):
        calls = []

        def fake_get(url, *args, **kwargs):
            calls.append(url)
            if len(calls) == 1:
                return MagicMock(text=json.dumps({'response': {'docs': []}}))
            return MagicMock(text=json.dumps({
                'response': {
                    'docs': [{
                        'cui': ['C999'],
                        'pretty_name': ['Wildcard match'],
                        'type_ids': [],
                        'synonyms': ['wm'],
                    }]
                }
            }))

        mock_get.side_effect = fake_get

        response = solr_utils.search_collection([self.cdb.id], 'foo')
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['cui'], 'C999')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-solr')
class HelperFunctionTests(TestCase):
    def test_process_result_response_deduplicates_by_cui(self):
        resp = {
            'response': {
                'docs': [
                    {'cui': ['C001'], 'pretty_name': ['a'], 'type_ids': ['T1'], 'synonyms': ['x']},
                    {'cui': ['C001'], 'pretty_name': ['a-dup'], 'type_ids': ['T1'], 'synonyms': ['x']},
                    {'cui': ['C002'], 'pretty_name': ['b'], 'type_ids': [], 'synonyms': []},
                ]
            }
        }
        result_map = solr_utils._process_result_repsonse(resp)
        self.assertEqual(set(result_map.keys()), {'C001', 'C002'})

    def test_concept_dct_uses_pretty_name_when_no_synonyms(self):
        cdb = MagicMock()
        cdb.get_name.return_value = 'Pretty (qualifier)'
        info = {'original_names': [], 'type_ids': ['T1'], 'description': 'desc'}
        out = solr_utils._concept_dct('C001', cdb, info)
        self.assertEqual(out['cui'], 'C001')
        # synonyms fall back to pretty name when original_names is empty
        self.assertEqual(out['synonyms'], ['Pretty (qualifier)'])
        # parenthesised qualifier removed in `name`
        self.assertEqual(out['name'], 'Pretty')

    def test_concept_dct_uses_original_names_as_synonyms(self):
        cdb = MagicMock()
        cdb.get_name.return_value = 'Hypertension'
        info = {'original_names': {'HTN', 'High blood pressure'}, 'type_ids': ['T'], 'description': 'd'}
        out = solr_utils._concept_dct('C100', cdb, info)
        self.assertSetEqual(set(out['synonyms']), {'HTN', 'High blood pressure'})


@override_settings(MEDIA_ROOT='/tmp/mct-tests-solr')
class DropCollectionTests(TestCase):
    @patch('api.solr_utils.requests.get')
    def test_drop_collection_calls_delete_endpoint(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200, text='{}')
        cdb = ConceptDB(name='drop_cdb', cdb_file='drop_cdb.dat')
        cdb.save(skip_load=True)
        solr_utils.drop_collection(cdb)
        # Should call the DELETE action URL
        call_url = mock_get.call_args[0][0]
        self.assertIn(f'name=drop_cdb_id_{cdb.id}', call_url)
        self.assertIn('action=DELETE', call_url)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-solr')
class EnsureConceptSearchableTests(TestCase):
    @patch('api.solr_utils.requests.post')
    @patch('api.solr_utils.requests.get')
    def test_uploads_concept_when_collection_exists(self, mock_get, mock_post):
        cdb = ConceptDB(name='ecs_cdb', cdb_file='ecs_cdb.dat')
        cdb.save(skip_load=True)

        mock_get.return_value = MagicMock(
            status_code=200,
            text=json.dumps({'collections': [f'ecs_cdb_id_{cdb.id}']}),
        )
        mock_post.return_value = MagicMock(status_code=200, text='{}')

        mc_cdb = MagicMock()
        mc_cdb.get_name.return_value = 'X'
        mc_cdb.cui2info = {'C': {'original_names': [], 'type_ids': [], 'description': ''}}

        solr_utils.ensure_concept_searchable('C', mc_cdb, cdb)
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs.get('json')
        self.assertEqual(payload[0]['cui'], 'C')

    @patch('api.solr_utils.requests.post')
    @patch('api.solr_utils.requests.get')
    def test_does_not_upload_when_collection_missing(self, mock_get, mock_post):
        cdb = ConceptDB(name='ecs_cdb2', cdb_file='ecs_cdb2.dat')
        cdb.save(skip_load=True)
        mock_get.return_value = MagicMock(
            status_code=200,
            text=json.dumps({'collections': []}),
        )
        mc_cdb = MagicMock()
        mc_cdb.get_name.return_value = 'X'
        mc_cdb.cui2info = {'C': {'original_names': [], 'type_ids': [], 'description': ''}}

        solr_utils.ensure_concept_searchable('C', mc_cdb, cdb)
        mock_post.assert_not_called()
