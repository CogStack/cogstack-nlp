"""Tests for the concept-explorer view endpoints in api.views.

These endpoints all read from a cached MedCAT CDB. The CDB loading is mocked
via `api.views.get_cached_cdb` so the tests stay fast and don't require a real
model on disk.
"""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ._helpers import create_user


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class FakeCDB:
    """Minimal stand-in for a MedCAT CDB used by the concept endpoints."""

    def __init__(self, pt2ch=None, ch2pt=None, cui2info=None):
        self.addl_info = {}
        if pt2ch is not None:
            self.addl_info['pt2ch'] = pt2ch
        if ch2pt is not None:
            self.addl_info['ch2pt'] = ch2pt
        self.cui2info = cui2info or {}

    def get_name(self, cui):
        return self.cui2info.get(cui, {}).get('preferred_name', cui)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-concepts')
class CdbCuiChildrenTests(TestCase):
    def setUp(self):
        self.user = create_user(username='cui-children')
        self.client = _auth_client(self.user)

    def test_returns_flat_root_when_cdb_has_no_pt2ch(self):
        cdb = FakeCDB()
        with patch('api.views.get_cached_cdb', return_value=cdb):
            resp = self.client.get('/api/model-concept-children/1/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'], [
            {'cui': 'Root', 'pretty_name': 'All concepts'},
        ])

    def test_returns_flat_cdb_concepts_when_cdb_has_no_pt2ch(self):
        cdb = FakeCDB(cui2info={
            'C2': {'preferred_name': 'Concept Two'},
            'C1': {'preferred_name': 'Concept One'},
        })
        with patch('api.views.get_cached_cdb', return_value=cdb):
            resp = self.client.get('/api/model-concept-children/1/?parent_cui=Root')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'], [
            {'cui': 'C1', 'pretty_name': 'Concept One'},
            {'cui': 'C2', 'pretty_name': 'Concept Two'},
        ])

    def test_returns_root_term_when_no_parent_cui(self):
        cdb = FakeCDB(
            pt2ch={'138875005': ['100']},
            cui2info={'138875005': {'preferred_name': 'SNOMED CT Concept'}},
        )
        with patch('api.views.get_cached_cdb', return_value=cdb):
            resp = self.client.get('/api/model-concept-children/1/')
        self.assertEqual(resp.status_code, 200)
        results = resp.json()['results']
        self.assertEqual(results, [{'cui': '138875005', 'pretty_name': 'SNOMED CT Concept'}])

    def test_returns_children_for_parent_cui(self):
        cdb = FakeCDB(
            pt2ch={'138875005': ['100'], '100': ['200', '201']},
            cui2info={
                '138875005': {'preferred_name': 'root'},
                '100': {'preferred_name': 'parent'},
                '200': {'preferred_name': 'child-a'},
                '201': {'preferred_name': 'child-b'},
            },
        )
        with patch('api.views.get_cached_cdb', return_value=cdb):
            resp = self.client.get('/api/model-concept-children/1/?parent_cui=100')
        self.assertEqual(resp.status_code, 200)
        cuis = {r['cui'] for r in resp.json()['results']}
        self.assertEqual(cuis, {'200', '201'})

    def test_returns_empty_results_on_unknown_parent(self):
        cdb = FakeCDB(
            pt2ch={'138875005': ['100']},
            cui2info={'138875005': {'preferred_name': 'root'}},
        )
        with patch('api.views.get_cached_cdb', return_value=cdb):
            resp = self.client.get('/api/model-concept-children/1/?parent_cui=does-not-exist')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'], [])


@override_settings(MEDIA_ROOT='/tmp/mct-tests-concepts')
class CdbConceptPathTests(TestCase):
    def setUp(self):
        self.user = create_user(username='concept-path')
        self.client = _auth_client(self.user)

    def test_returns_path_and_computes_ch2pt_when_missing(self):
        cdb = FakeCDB(pt2ch={'root': ['child']})
        with patch('api.views.get_cached_cdb', return_value=cdb), \
                patch('api.views.ch2pt_from_pt2ch', return_value={'child': ['root']}) as mock_ch2pt, \
                patch('api.views.snomed_ct_concept_path', return_value=[{'cui': 'child'}]) as mock_path:
            resp = self.client.get('/api/concept-path/?cdb_id=1&cui=child')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'], [{'cui': 'child'}])
        mock_ch2pt.assert_called_once()
        mock_path.assert_called_once()

    def test_reuses_existing_ch2pt(self):
        cdb = FakeCDB(pt2ch={'root': ['child']}, ch2pt={'child': ['root']})
        with patch('api.views.get_cached_cdb', return_value=cdb), \
                patch('api.views.ch2pt_from_pt2ch') as mock_ch2pt, \
                patch('api.views.snomed_ct_concept_path', return_value=[]):
            resp = self.client.get('/api/concept-path/?cdb_id=1&cui=child')
        self.assertEqual(resp.status_code, 200)
        mock_ch2pt.assert_not_called()

    def test_returns_flat_path_when_cdb_has_no_pt2ch(self):
        cdb = FakeCDB(cui2info={'C1': {'preferred_name': 'Concept One'}})
        with patch('api.views.get_cached_cdb', return_value=cdb):
            resp = self.client.get('/api/concept-path/?cdb_id=1&cui=C1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'], {
            'node_path': {
                'cui': 'Root',
                'pretty_name': 'All concepts',
                'children': [{'cui': 'C1', 'pretty_name': 'Concept One'}],
            },
            'links': [{'parent': 'Root', 'child': 'C1'}],
        })


@override_settings(MEDIA_ROOT='/tmp/mct-tests-concepts')
class GenerateConceptFilterFlatJsonTests(TestCase):
    def setUp(self):
        self.user = create_user(username='flat-json')
        self.client = _auth_client(self.user)

    def test_returns_400_when_params_missing(self):
        resp = self.client.post('/api/generate-concept-filter-json/', {'cuis': ['C1']}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_returns_downloadable_filter_json(self):
        with patch('api.views.get_cached_cdb', return_value=FakeCDB()), \
                patch('api.views.get_all_ch', return_value=['C1', 'C2', 'C3']):
            resp = self.client.post(
                '/api/generate-concept-filter-json/',
                {'cuis': ['C1'], 'cdb_id': 1, 'excluded_nodes': ['C3']},
                format='json',
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Disposition'], 'attachment; filename=filter.json')
        payload = json.loads(resp.content)
        self.assertEqual(set(payload), {'C1', 'C2'})


@override_settings(MEDIA_ROOT='/tmp/mct-tests-concepts')
class GenerateConceptFilterTests(TestCase):
    def setUp(self):
        self.user = create_user(username='gen-filter')
        self.client = _auth_client(self.user)

    def test_returns_400_when_params_missing(self):
        resp = self.client.post('/api/generate-concept-filter/', {'cdb_id': 1}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_returns_filter_summary(self):
        with patch('api.views.get_cached_cdb', return_value=FakeCDB()), \
                patch('api.views.get_all_ch', return_value=[]):
            resp = self.client.post(
                '/api/generate-concept-filter/',
                {'cuis': ['C1', 'C2'], 'cdb_id': 1},
                format='json',
            )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['filter_len'], 2)
        self.assertIn('filter', data)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-concepts')
class CuisToConceptsTests(TestCase):
    def setUp(self):
        self.user = create_user(username='cuis2concepts')
        self.client = _auth_client(self.user)
        self.cdb = FakeCDB(cui2info={
            'C1': {'preferred_name': 'Concept One'},
            'C2': {'preferred_name': 'Concept Two'},
        })

    def test_returns_400_when_cdb_id_missing(self):
        resp = self.client.post('/api/cuis-to-concepts/', {'cuis': ['C1']}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_returns_named_concepts_for_given_cuis(self):
        with patch('api.views.get_cached_cdb', return_value=self.cdb):
            resp = self.client.post(
                '/api/cuis-to-concepts/',
                {'cuis': ['C1'], 'cdb_id': 1},
                format='json',
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['concept_list'], [{'cui': 'C1', 'name': 'Concept One'}])

    def test_returns_all_concepts_when_no_cuis(self):
        with patch('api.views.get_cached_cdb', return_value=self.cdb):
            resp = self.client.post('/api/cuis-to-concepts/', {'cdb_id': 1}, format='json')
        self.assertEqual(resp.status_code, 200)
        names = {c['name'] for c in resp.json()['concept_list']}
        self.assertEqual(names, {'Concept One', 'Concept Two'})
