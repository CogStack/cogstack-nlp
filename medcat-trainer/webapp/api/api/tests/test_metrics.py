"""Unit tests for api.metrics.ProjectMetrics.

These tests exercise the pure-Python data-shaping logic in ProjectMetrics
using a synthetic MedCAT export. Code paths requiring an actual CAT model
are exercised by passing cat=None.
"""

import pandas as pd
from django.test import TestCase

from ..metrics import ProjectMetrics


def _build_export(num_projects=1, num_docs=2, num_anns=2):
    """Build a synthetic MedCAT trainer export structure used for metrics tests."""
    projects = []
    next_id = 1
    for p_idx in range(num_projects):
        proj = {
            'id': p_idx + 1,
            'name': f'proj-{p_idx + 1}',
            'meta_anno_defs': [
                {'name': 'Presence', 'values': ['True', 'False']},
            ],
            'documents': [],
        }
        for d_idx in range(num_docs):
            doc = {
                'id': next_id,
                'name': f'doc-{next_id}',
                'text': 'some clinical text',
                'annotations': [],
            }
            next_id += 1
            for a_idx in range(num_anns):
                doc['annotations'].append({
                    'id': 1000 + a_idx + d_idx * 10 + p_idx * 100,
                    'cui': 'C001' if a_idx % 2 == 0 else 'C002',
                    'value': 'token',
                    'start': a_idx * 10,
                    'end': a_idx * 10 + 5,
                    'validated': True,
                    'correct': True,
                    'deleted': False,
                    'alternative': False,
                    'killed': False,
                    'irrelevant': False,
                    'manually_created': False,
                    'acc': 1.0,
                    'user': f'user{a_idx % 2}',
                    'last_modified': '2024-01-01 10:00:00.000000',
                    'meta_anns': {
                        'Presence': {
                            'name': 'Presence',
                            'value': 'True' if a_idx % 2 == 0 else 'False',
                            'acc': 1.0,
                            'validated': True,
                        }
                    },
                })
            proj['documents'].append(doc)
        projects.append(proj)
    return {'projects': projects}


class ProjectMetricsInitTests(TestCase):
    def test_annotations_extracted_with_project_and_doc_metadata(self):
        export = _build_export(num_projects=1, num_docs=1, num_anns=2)
        pm = ProjectMetrics(export, cat=None)
        self.assertEqual(len(pm.annotations), 2)
        ann = pm.annotations[0]
        self.assertEqual(ann['project'], 'proj-1')
        self.assertEqual(ann['project_id'], 1)
        self.assertEqual(ann['document_name'], 'doc-1')
        self.assertEqual(ann['document_id'], 1)
        self.assertIn('Presence', ann)  # meta annotations flattened

    def test_projects2names_and_doc_maps_populated(self):
        export = _build_export(num_projects=2, num_docs=2, num_anns=1)
        pm = ProjectMetrics(export, cat=None)
        self.assertEqual(pm.projects2names[1], 'proj-1')
        self.assertEqual(pm.projects2names[2], 'proj-2')
        self.assertEqual(len(pm.projects2doc_ids[1]), 2)
        self.assertEqual(len(pm.projects2doc_ids[2]), 2)
        # docs2names contains all docs
        self.assertEqual(len(pm.docs2names), 4)

    def test_meta_annotation_values_flattened_per_annotation(self):
        export = _build_export(num_projects=1, num_docs=1, num_anns=2)
        pm = ProjectMetrics(export, cat=None)
        # Two annotations: one True, one False
        presence_values = sorted(a['Presence'] for a in pm.annotations)
        self.assertEqual(presence_values, ['False', 'True'])


class AnnotationDataFrameTests(TestCase):
    def test_annotation_df_without_cat_does_not_add_concept_name(self):
        export = _build_export(num_anns=2)
        pm = ProjectMetrics(export, cat=None)
        df = pm.annotation_df()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2 * 2)  # docs * anns
        self.assertNotIn('concept_name', df.columns)

    def test_concept_summary_without_cat_returns_basic_records(self):
        export = _build_export(num_anns=2)
        pm = ProjectMetrics(export, cat=None)
        summary = pm.concept_summary()
        self.assertIsInstance(summary, list)
        # All annotations are validated+correct, so all should appear
        cuis = {row['cui'] for row in summary}
        self.assertEqual(cuis, {'C001', 'C002'})

    def test_user_stats_groups_by_user(self):
        export = _build_export(num_docs=2, num_anns=2)
        pm = ProjectMetrics(export, cat=None)
        stats = pm.user_stats(by_user=True)
        self.assertIsInstance(stats, pd.DataFrame)
        users = set(stats['user'].tolist())
        self.assertEqual(users, {'user0', 'user1'})

    def test_user_stats_by_date_includes_date_column(self):
        export = _build_export(num_docs=1, num_anns=2)
        pm = ProjectMetrics(export, cat=None)
        stats = pm.user_stats(by_user=False)
        self.assertIn('date', stats.columns)
        self.assertIn('user', stats.columns)
        self.assertIn('count', stats.columns)


class RenameMetaAnnsTests(TestCase):
    def test_rename_meta_task_name(self):
        export = _build_export(num_docs=1, num_anns=1)
        pm = ProjectMetrics(export, cat=None)
        # The annotation initially has 'Presence' key.
        self.assertIn('Presence', pm.annotations[0])

        pm.rename_meta_anns(meta_anns2rename={'Presence': 'Existence'})

        # Original 'Presence' should be renamed to 'Existence'
        # Note: the rename happens on the underlying mct_export then _annotations()
        # is rebuilt. So check on the rebuilt annotations list.
        self.assertNotIn('Presence', pm.annotations[0])
        self.assertIn('Existence', pm.annotations[0])

    def test_rename_meta_value_when_specified(self):
        export = _build_export(num_docs=1, num_anns=1)
        pm = ProjectMetrics(export, cat=None)
        # Rename 'True' to 'Yes' inside the renamed task 'Existence'
        pm.rename_meta_anns(
            meta_anns2rename={'Presence': 'Existence'},
            meta_ann_values2rename={'Existence': {'True': 'Yes'}},
        )
        self.assertEqual(pm.annotations[0]['Existence'], 'Yes')


class EmptyExportTests(TestCase):
    def test_handles_empty_documents_without_error(self):
        export = {'projects': [{'id': 1, 'name': 'empty', 'documents': [],
                                'meta_anno_defs': []}]}
        pm = ProjectMetrics(export, cat=None)
        self.assertEqual(pm.annotations, [])
        # annotation_df on empty annotations raises; just check the helpers
        # that should still work.
        self.assertEqual(pm.projects2names[1], 'empty')
        self.assertEqual(pm.projects2doc_ids[1], [])
