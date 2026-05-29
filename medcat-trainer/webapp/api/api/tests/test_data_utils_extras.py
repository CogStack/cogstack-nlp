"""Additional unit tests for api.data_utils functions not already covered by
test_data_utils.py.
"""

import os
import tempfile

import pandas as pd
from django.test import TestCase, override_settings

from ..data_utils import dataset_from_file, delete_orphan_docs, sanitise_input
from ..models import Document
from ._helpers import create_dataset, dataset_signals_disconnected, make_csv_file


class SanitiseInputTests(TestCase):
    def test_replaces_br_with_newline(self):
        self.assertEqual(sanitise_input('a<br>b'), 'a\nb')

    def test_replaces_paragraph_with_newline(self):
        self.assertEqual(sanitise_input('<p>hi</p>'), '\nhi\n')

    def test_strips_span_tags_keeping_content(self):
        self.assertEqual(sanitise_input('<span class="x">word</span>'), 'word')

    def test_replaces_div_tags_with_newlines(self):
        # Opening tag requires attributes in the regex; closing </div> becomes a newline.
        self.assertEqual(sanitise_input('<div class="x">part1</div>'), '\npart1\n')

    def test_strips_html_body_head(self):
        self.assertEqual(
            sanitise_input('<html><head></head><body>data</body></html>'),
            'data',
        )

    def test_plain_text_returned_unchanged(self):
        self.assertEqual(sanitise_input('just text'), 'just text')

    def test_multiple_tags_in_single_string(self):
        text = '<p>Line1</p><br><span>Line2</span>'
        self.assertEqual(sanitise_input(text), '\nLine1\n\nLine2')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-data-utils')
class DeleteOrphanDocsTests(TestCase):
    def test_removes_all_documents_for_dataset(self):
        ds = create_dataset(name='orphan-ds', file_name='orphan-ds.csv')
        Document.objects.create(name='a', text='x', dataset=ds)
        Document.objects.create(name='b', text='y', dataset=ds)

        self.assertEqual(Document.objects.filter(dataset=ds).count(), 2)

        delete_orphan_docs(ds)

        self.assertEqual(Document.objects.filter(dataset=ds).count(), 0)


class DatasetFromFileTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_dataset_with_file(self, name, csv_path):
        # Bypass the post_save signal that would re-trigger dataset_from_file
        with dataset_signals_disconnected():
            ds = create_dataset(name=name, file_name='ignored.csv')
        ds.original_file.name = csv_path
        return ds

    @override_settings(MEDIA_ROOT='/')
    def test_creates_documents_for_each_row_in_csv(self):
        csv_path = make_csv_file(
            self.tmp_dir,
            rows=[
                {'name': 'd1', 'text': 'first text'},
                {'name': 'd2', 'text': 'second text'},
            ],
            file_name='data.csv',
        )
        ds = self._make_dataset_with_file('dff-1', csv_path)

        dataset_from_file(ds)

        docs = Document.objects.filter(dataset=ds).order_by('name')
        self.assertEqual(docs.count(), 2)
        self.assertEqual(docs[0].name, 'd1')
        self.assertEqual(docs[0].text, 'first text')

    @override_settings(MEDIA_ROOT='/')
    def test_sanitises_html_in_text_column(self):
        csv_path = make_csv_file(
            self.tmp_dir,
            rows=[{'name': 'd1', 'text': '<p>hello</p>'}],
            file_name='data.csv',
        )
        ds = self._make_dataset_with_file('dff-2', csv_path)

        dataset_from_file(ds)

        doc = Document.objects.get(dataset=ds, name='d1')
        self.assertEqual(doc.text, '\nhello\n')

    @override_settings(MEDIA_ROOT='/')
    def test_raises_on_non_unique_names(self):
        csv_path = make_csv_file(
            self.tmp_dir,
            rows=[
                {'name': 'dup', 'text': 'a'},
                {'name': 'dup', 'text': 'b'},
            ],
            file_name='data.csv',
        )
        ds = self._make_dataset_with_file('dff-3', csv_path)

        with self.assertRaises(Exception) as ctx:
            dataset_from_file(ds)
        self.assertIn('name column', str(ctx.exception))

    @override_settings(MEDIA_ROOT='/')
    def test_raises_when_exceeding_max_size(self):
        old = os.environ.get('MAX_DATASET_SIZE')
        os.environ['MAX_DATASET_SIZE'] = '1'
        try:
            csv_path = make_csv_file(
                self.tmp_dir,
                rows=[
                    {'name': 'a', 'text': 't1'},
                    {'name': 'b', 'text': 't2'},
                ],
                file_name='data.csv',
            )
            ds = self._make_dataset_with_file('dff-4', csv_path)

            with self.assertRaises(Exception) as ctx:
                dataset_from_file(ds)
            self.assertIn('Max dataset size', str(ctx.exception))
        finally:
            if old is None:
                os.environ.pop('MAX_DATASET_SIZE', None)
            else:
                os.environ['MAX_DATASET_SIZE'] = old

    @override_settings(MEDIA_ROOT='/')
    def test_rejects_unsupported_extensions(self):
        # The original_file path must end with neither .csv nor .xlsx
        path = os.path.join(self.tmp_dir, 'bad_ext.tsv')
        with open(path, 'w') as f:
            f.write('name\ttext\n1\t2\n')
        ds = self._make_dataset_with_file('dff-5', path)

        with self.assertRaises(Exception) as ctx:
            dataset_from_file(ds)
        self.assertIn('.csv or .xlsx', str(ctx.exception))
