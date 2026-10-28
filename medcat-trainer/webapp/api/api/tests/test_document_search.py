"""Tests for the Solr backed document text search: indexing, the search endpoint and dataset signals.

Solr HTTP calls are mocked, except in ``LiveSolrDocumentSearchTests`` which runs against a real
SolrCloud instance when ``MCT_SOLR_LIVE_TESTS=1`` (host / port from CONCEPT_SEARCH_SERVICE_HOST / _PORT).
"""

import json
import os
import tempfile
import unittest
import uuid
from unittest.mock import MagicMock, patch

from background_task.models import Task
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .. import document_search
from ..models import Dataset, Document
from ._helpers import create_basic_project, create_document, create_user, make_csv_file

COLLECTION = document_search.DOCUMENT_SEARCH_COLLECTION


def _resp(status=200, body=None):
    return MagicMock(status_code=status, text=json.dumps(body or {}), json=lambda: body or {})


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class HighlightSegmentsTests(TestCase):
    def test_splits_marked_spans(self):
        pre, post = document_search.HIGHLIGHT_PRE, document_search.HIGHLIGHT_POST
        segments = document_search.highlight_segments(f'has {pre}chest pain{post} and {pre}fever{post}')
        self.assertEqual(segments, [
            {'text': 'has ', 'match': False},
            {'text': 'chest pain', 'match': True},
            {'text': ' and ', 'match': False},
            {'text': 'fever', 'match': True},
        ])

    def test_phrase_query_escapes_quotes_and_backslashes(self):
        self.assertEqual(document_search._phrase_query('say "hi" \\o/'), 'text:"say \\"hi\\" \\\\o/"')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-doc-search')
class IndexDatasetDocumentsTests(TestCase):
    def setUp(self):
        self.project = create_basic_project(name='index-proj')
        self.docs = [create_document(self.project, name=f'n{i}', text=f'text {i}') for i in range(3)]

    @patch('api.document_search.requests.post')
    @patch('api.document_search.requests.get')
    def test_creates_collection_and_fields_then_replaces_dataset_docs(self, mock_get, mock_post):
        def get_side_effect(url, params=None, **kwargs):
            if url.endswith('/admin/collections') and params['action'] == 'LIST':
                return _resp(body={'collections': []})
            if url.endswith('/admin/collections') and params['action'] == 'CREATE':
                return _resp()
            if url.endswith('/schema/fields'):
                return _resp(body={'fields': [{'name': 'id'}, {'name': 'name'}]})
            raise AssertionError(f'unexpected GET {url}')
        mock_get.side_effect = get_side_effect
        mock_post.return_value = _resp()

        with patch.object(document_search, 'INDEX_BATCH_SIZE', 2):
            total = document_search.index_dataset_documents(self.project.dataset.id)

        self.assertEqual(total, 3)
        create_call = [c for c in mock_get.call_args_list if c.kwargs.get('params', {}).get('action') == 'CREATE']
        self.assertEqual(create_call[0].kwargs['params']['name'], COLLECTION)

        posts = [(c.args[0], c.kwargs.get('json')) for c in mock_post.call_args_list]
        schema_url, schema_body = posts[0]
        self.assertTrue(schema_url.endswith(f'/{COLLECTION}/schema'))
        self.assertEqual([f['name'] for f in schema_body['add-field']], ['dataset_id', 'doc_id', 'text'])

        self.assertEqual(posts[1][1], {'delete': {'query': f'dataset_id:{self.project.dataset.id}'}})
        self.assertEqual([d['doc_id'] for d in posts[2][1]], [self.docs[0].id, self.docs[1].id])
        self.assertEqual([d['doc_id'] for d in posts[3][1]], [self.docs[2].id])
        self.assertEqual(posts[2][1][0], {
            'id': str(self.docs[0].id), 'doc_id': self.docs[0].id, 'dataset_id': self.project.dataset.id,
            'name': 'n0', 'text': 'text 0',
        })
        self.assertEqual(posts[4][1], {'commit': {}})

    @patch('api.document_search.requests.get')
    def test_raises_when_solr_cannot_list_collections(self, mock_get):
        mock_get.return_value = _resp(status=500)
        with self.assertRaises(document_search.DocumentSearchUnavailable):
            document_search.index_dataset_documents(self.project.dataset.id)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-doc-search')
class SearchDocumentsViewTests(TestCase):
    def setUp(self):
        self.client = _auth_client(create_user(username='searcher'))
        self.project = create_basic_project(name='search-proj')
        self.dataset_id = self.project.dataset.id
        self.d1 = create_document(self.project, name='n1', text='Patient has Chest Pain.')
        self.d2 = create_document(self.project, name='n2', text='No fever.')
        self.d3 = create_document(self.project, name='n3', text='chest pain resolved')

    def _get(self, **params):
        return self.client.get('/api/search-documents/', params)

    @patch('api.document_search.requests.get')
    def test_returns_solr_hits_in_solr_order_with_highlights(self, mock_get):
        pre, post = document_search.HIGHLIGHT_PRE, document_search.HIGHLIGHT_POST

        def side_effect(url, params=None, **kwargs):
            if params['q'] == '*:*':
                return _resp(body={'response': {'numFound': 3, 'docs': []}})
            self.assertEqual(params['q'], 'text:"chest pain"')
            self.assertEqual(params['fq'], f'dataset_id:{self.dataset_id}')
            return _resp(body={
                'response': {'numFound': 2, 'docs': [
                    {'id': str(self.d3.id), 'doc_id': self.d3.id},
                    {'id': str(self.d1.id), 'doc_id': self.d1.id},
                ]},
                'highlighting': {str(self.d3.id): {'text': [f'{pre}chest pain{post} resolved']}},
            })
        mock_get.side_effect = side_effect

        resp = self._get(dataset=self.dataset_id, text='chest pain')
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['search_backend'], 'solr')
        self.assertEqual(body['count'], 2)
        self.assertIsNone(body['next'])
        self.assertEqual([r['id'] for r in body['results']], [self.d3.id, self.d1.id])
        self.assertEqual(body['results'][0]['text'], 'chest pain resolved')
        self.assertEqual(body['results'][0]['highlight'][0], {'text': 'chest pain', 'match': True})
        self.assertIsNone(body['results'][1]['highlight'])

    @patch('api.document_search.requests.get')
    def test_paginates(self, mock_get):
        mock_get.side_effect = lambda url, params=None, **kw: _resp(body={
            'response': {'numFound': 3 if params['q'] == '*:*' else 120, 'docs': []}
        })
        body = self._get(dataset=self.dataset_id, text='pain', page=2).json()
        self.assertEqual(mock_get.call_args.kwargs['params']['start'], 50)
        self.assertEqual(body['next'], f'/api/search-documents/?dataset={self.dataset_id}&text=pain&page=3')
        self.assertEqual(body['previous'], f'/api/search-documents/?dataset={self.dataset_id}&text=pain&page=1')

    @patch('api.document_search.requests.get')
    def test_falls_back_to_db_when_dataset_not_fully_indexed(self, mock_get):
        mock_get.return_value = _resp(body={'response': {'numFound': 1, 'docs': []}})
        body = self._get(dataset=self.dataset_id, text='chest pain').json()
        self.assertEqual(body['search_backend'], 'db')
        self.assertEqual([r['id'] for r in body['results']], [self.d1.id, self.d3.id])

    @patch('api.document_search.requests.get')
    def test_falls_back_to_db_when_solr_unreachable(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError('down')
        body = self._get(dataset=self.dataset_id, text='FEVER').json()
        self.assertEqual(body['search_backend'], 'db')
        self.assertEqual([r['id'] for r in body['results']], [self.d2.id])

    def test_validates_params(self):
        self.assertEqual(self._get(dataset=self.dataset_id, text='  ').status_code, 400)
        self.assertEqual(self._get(dataset='abc', text='x').status_code, 400)

    def test_requires_authentication(self):
        resp = APIClient().get('/api/search-documents/', {'dataset': self.dataset_id, 'text': 'x'})
        self.assertIn(resp.status_code, (401, 403))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DatasetIndexSignalTests(TestCase):
    def _upload_dataset(self):
        csv_path = make_csv_file(tempfile.mkdtemp())
        with open(csv_path, 'rb') as fh:
            ds = Dataset(name='index-signal-ds')
            ds.original_file.save('index-signal-ds.csv', ContentFile(fh.read()))
        return ds

    def test_upload_schedules_index_task_on_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            ds = self._upload_dataset()
        tasks = Task.objects.filter(task_name='api.document_search.index_dataset_task')
        self.assertEqual(tasks.count(), 1)
        self.assertEqual(json.loads(tasks.get().task_params)[0], [ds.id])

    def test_delete_schedules_remove_task(self):
        ds = self._upload_dataset()
        with self.captureOnCommitCallbacks(execute=True):
            ds_id = ds.id
            ds.delete()
        task = Task.objects.get(task_name='api.document_search.remove_dataset_task')
        self.assertEqual(json.loads(task.task_params)[0], [ds_id])

    @patch('api.signals.DOCUMENT_SEARCH_INDEX_ENABLED', False)
    def test_no_task_when_indexing_disabled(self):
        with self.captureOnCommitCallbacks(execute=True):
            self._upload_dataset()
        self.assertFalse(Task.objects.filter(task_name__startswith='api.document_search').exists())


@unittest.skipUnless(os.environ.get('MCT_SOLR_LIVE_TESTS') == '1', 'requires a running SolrCloud')
@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LiveSolrDocumentSearchTests(TestCase):
    def setUp(self):
        self.collection = f'mct_test_docs_{uuid.uuid4().hex[:8]}'
        patcher = patch.object(document_search, 'DOCUMENT_SEARCH_COLLECTION', self.collection)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(lambda: document_search.requests.get(
            f'{document_search._base_url()}/admin/collections',
            params={'action': 'DELETE', 'name': self.collection}))
        self.client = _auth_client(create_user(username='live-searcher'))

    def _upload(self, name, rows):
        csv_path = make_csv_file(tempfile.mkdtemp(), rows=rows)
        with open(csv_path, 'rb') as fh:
            ds = Dataset(name=name)
            ds.original_file.save(f'{name}.csv', ContentFile(fh.read()))
        return ds

    def test_upload_index_and_search(self):
        with self.captureOnCommitCallbacks(execute=True):
            ds = self._upload('live-ds', [
                {'name': 'a', 'text': 'Patient reports CHEST pain, radiating to the left arm.'},
                {'name': 'b', 'text': 'No fever or cough. Pain in chest wall only.'},
                {'name': 'c', 'text': 'Chest pain resolved after GTN.'},
            ])
            other = self._upload('live-other', [{'name': 'x', 'text': 'chest pain elsewhere'}])
        scheduled = Task.objects.filter(task_name='api.document_search.index_dataset_task')
        self.assertEqual(scheduled.count(), 2)

        # run the scheduled tasks as the background worker would
        for task in scheduled:
            args, kwargs = json.loads(task.task_params)
            document_search.index_dataset_task.now(*args, **kwargs)

        body = self.client.get('/api/search-documents/', {'dataset': ds.id, 'text': 'chest pain'}).json()
        self.assertEqual(body['search_backend'], 'solr')
        names = sorted(r['name'] for r in body['results'])
        self.assertEqual(names, ['a', 'c'])
        for r in body['results']:
            matched = ''.join(s['text'] for s in r['highlight'] if s['match'])
            self.assertEqual(matched.lower(), 'chest pain')

        # re-indexing replaces rather than duplicates
        document_search.index_dataset_documents(ds.id)
        self.assertEqual(document_search.indexed_document_count(ds.id), 3)

        document_search.remove_dataset_documents(other.id)
        self.assertEqual(document_search.indexed_document_count(other.id), 0)
        self.assertEqual(document_search.indexed_document_count(ds.id), 3)
        self.assertEqual(Document.objects.filter(dataset=ds).count(), 3)
