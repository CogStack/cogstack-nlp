"""Unit tests for api.admin.actions.

These tests focus on retrieve_project_data and the download_* helpers since
they back the JSON export feature that the upload tests already validate.
"""

import json

from django.test import TestCase, override_settings

from ..admin.actions import (
    download_projects_with_text,
    download_projects_without_text,
    retrieve_project_data,
)
from ..models import (
    AnnotatedEntity,
    EntityRelation,
    MetaAnnotation,
    MetaTask,
    MetaTaskValue,
    ProjectAnnotateEntities,
    Relation,
)
from ._helpers import (
    create_basic_project,
    create_document,
    create_entity,
    create_user,
)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-admin')
class RetrieveProjectDataTests(TestCase):
    def setUp(self):
        self.user = create_user(username='admin-actions-user')
        self.project = create_basic_project(name='admin-actions-proj')
        self.doc = create_document(self.project, name='doc-1', text='hello world')
        self.entity = create_entity(label='C100')
        self.entity_b = create_entity(label='C200')

        self.ann_a = AnnotatedEntity.objects.create(
            user=self.user, project=self.project, document=self.doc, entity=self.entity,
            value='hello', start_ind=0, end_ind=5, acc=0.9, validated=True, correct=True,
        )
        self.ann_b = AnnotatedEntity.objects.create(
            user=self.user, project=self.project, document=self.doc, entity=self.entity_b,
            value='world', start_ind=6, end_ind=11, acc=0.95, validated=True, correct=True,
        )

        self.task = MetaTask.objects.create(name='Presence')
        self.value = MetaTaskValue.objects.create(name='True')
        MetaAnnotation.objects.create(
            annotated_entity=self.ann_a,
            meta_task=self.task,
            meta_task_value=self.value,
            validated=True,
        )

        self.project.validated_documents.add(self.doc)

    def test_returns_basic_project_metadata(self):
        out = retrieve_project_data(ProjectAnnotateEntities.objects.filter(id=self.project.id))
        self.assertEqual(len(out['projects']), 1)
        proj = out['projects'][0]
        self.assertEqual(proj['name'], 'admin-actions-proj')
        self.assertEqual(proj['cuis'], self.project.cuis)
        self.assertEqual(proj['project_status'], 'A')
        self.assertEqual(len(proj['documents']), 1)

    def test_includes_annotation_text_and_indices(self):
        out = retrieve_project_data(ProjectAnnotateEntities.objects.filter(id=self.project.id))
        doc = out['projects'][0]['documents'][0]
        cuis = sorted(a['cui'] for a in doc['annotations'])
        self.assertEqual(cuis, ['C100', 'C200'])
        # check start/end indices match
        ann_a = next(a for a in doc['annotations'] if a['cui'] == 'C100')
        self.assertEqual(ann_a['start'], 0)
        self.assertEqual(ann_a['end'], 5)
        self.assertEqual(ann_a['value'], 'hello')
        self.assertTrue(ann_a['validated'])
        self.assertTrue(ann_a['correct'])

    def test_includes_meta_annotations(self):
        out = retrieve_project_data(ProjectAnnotateEntities.objects.filter(id=self.project.id))
        doc = out['projects'][0]['documents'][0]
        ann_a = next(a for a in doc['annotations'] if a['cui'] == 'C100')
        self.assertIn('Presence', ann_a['meta_anns'])
        self.assertEqual(ann_a['meta_anns']['Presence']['value'], 'True')

    def test_relations_included(self):
        rel = Relation.objects.create(label='hasFinding')
        EntityRelation.objects.create(
            user=self.user,
            project=self.project,
            document=self.doc,
            relation=rel,
            start_entity=self.ann_a,
            end_entity=self.ann_b,
            validated=True,
        )

        out = retrieve_project_data(ProjectAnnotateEntities.objects.filter(id=self.project.id))
        rels = out['projects'][0]['documents'][0]['relations']
        self.assertEqual(len(rels), 1)
        self.assertEqual(rels[0]['relation'], 'hasFinding')
        self.assertEqual(rels[0]['start_entity_cui'], 'C100')
        self.assertEqual(rels[0]['end_entity_cui'], 'C200')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-admin')
class DownloadProjectsTests(TestCase):
    def setUp(self):
        self.user = create_user(username='dl-action-user')
        self.project = create_basic_project(name='dl-action-proj')
        self.doc = create_document(self.project, name='doc-only', text='annotated text')
        ent = create_entity(label='C-DL')
        AnnotatedEntity.objects.create(
            user=self.user, project=self.project, document=self.doc, entity=ent,
            value='annotated', start_ind=0, end_ind=9, acc=1.0, validated=True, correct=True,
        )
        self.project.validated_documents.add(self.doc)

    def test_download_with_text_includes_document_text(self):
        resp = download_projects_with_text(
            ProjectAnnotateEntities.objects.filter(id=self.project.id)
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertEqual(body['projects'][0]['documents'][0]['text'], 'annotated text')

    def test_download_without_text_omits_document_text(self):
        resp = download_projects_without_text(
            ProjectAnnotateEntities.objects.filter(id=self.project.id),
            with_doc_name=False,
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        doc = body['projects'][0]['documents'][0]
        self.assertNotIn('text', doc)

    def test_download_without_text_with_doc_name_includes_name(self):
        resp = download_projects_without_text(
            ProjectAnnotateEntities.objects.filter(id=self.project.id),
            with_doc_name=True,
        )
        body = json.loads(resp.content)
        doc = body['projects'][0]['documents'][0]
        self.assertEqual(doc['name'], 'doc-only')
        self.assertNotIn('text', doc)
