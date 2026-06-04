"""Unit tests for api.serializers."""

import json
import os
import tempfile

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from ..models import (
    AnnotatedEntity,
    ConceptDB,
    Dataset,
    Document,
    Entity,
    ProjectAnnotateEntities,
    ProjectGroup,
    Vocabulary,
)
from ..serializers import (
    AnnotatedEntitySerializer,
    DatasetSerializer,
    DocumentSerializer,
    EntitySerializer,
    ProjectAnnotateEntitiesSerializer,
    ProjectGroupSerializer,
    UserSerializer,
)
from ._helpers import create_dataset


@override_settings(MEDIA_ROOT='/tmp/mct-tests-serializers')
class UserSerializerTests(TestCase):
    def test_serializes_expected_fields(self):
        user = User.objects.create_user(username='alice', email='a@x.com', password='pw')
        data = UserSerializer(user, context={'request': None}).data
        self.assertEqual(data['username'], 'alice')
        self.assertEqual(data['email'], 'a@x.com')
        self.assertIn('id', data)
        self.assertIn('is_staff', data)
        self.assertIn('is_superuser', data)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-serializers')
class EntitySerializerTests(TestCase):
    def test_serializes_entity_label(self):
        ent = Entity.objects.create(label='C123')
        data = EntitySerializer(ent).data
        self.assertEqual(data['label'], 'C123')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-serializers')
class DocumentAndAnnotationSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='annu', password='pw')
        cdb = ConceptDB(name='ser_cdb', cdb_file='ser_cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='ser_vocab', vocab_file='ser_vocab.dat')
        vocab.save(skip_load=True)
        cls.dataset = create_dataset(name='ser_ds', file_name='ser_ds.csv')
        cls.document = Document.objects.create(name='doc', text='hello', dataset=cls.dataset)

        cls.project = ProjectAnnotateEntities()
        cls.project.name = 'ser-proj'
        cls.project.dataset = cls.dataset
        cls.project.concept_db = cdb
        cls.project.vocab = vocab
        cls.project.cuis = ''
        cls.project.save()

        cls.entity = Entity.objects.create(label='C001')

    def test_document_serializer(self):
        data = DocumentSerializer(self.document).data
        self.assertEqual(data['name'], 'doc')
        self.assertEqual(data['text'], 'hello')
        self.assertEqual(data['dataset'], self.dataset.id)

    def test_annotated_entity_serializer(self):
        ann = AnnotatedEntity.objects.create(
            user=self.user,
            project=self.project,
            document=self.document,
            entity=self.entity,
            value='hello',
            start_ind=0,
            end_ind=5,
            acc=0.5,
        )
        data = AnnotatedEntitySerializer(ann).data
        self.assertEqual(data['value'], 'hello')
        self.assertEqual(data['start_ind'], 0)
        self.assertEqual(data['end_ind'], 5)
        self.assertEqual(data['acc'], 0.5)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-serializers')
class ProjectAnnotateEntitiesSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cdb = ConceptDB(name='pas_cdb', cdb_file='pas_cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='pas_vocab', vocab_file='pas_vocab.dat')
        vocab.save(skip_load=True)
        cls.dataset = create_dataset(name='pas_ds', file_name='pas_ds.csv')

        cls.project = ProjectAnnotateEntities()
        cls.project.name = 'pas-proj'
        cls.project.dataset = cls.dataset
        cls.project.concept_db = cdb
        cls.project.vocab = vocab
        cls.project.cuis = 'A,B,C'
        cls.project.save()

    def test_to_representation_includes_inline_cuis_only_when_no_file(self):
        data = ProjectAnnotateEntitiesSerializer(self.project).data
        # Should contain the original CUIs separated by ','
        self.assertEqual(set(data['cuis'].split(',')), {'A', 'B', 'C'})

    def test_to_representation_merges_cuis_from_file(self):
        media_root = '/tmp/mct-tests-serializers'
        os.makedirs(media_root, exist_ok=True)
        rel_path = 'pas_cuis_file.json'
        abs_path = os.path.join(media_root, rel_path)
        with open(abs_path, 'w') as f:
            json.dump(['X', 'Y'], f)
        try:
            self.project.cuis_file.name = rel_path
            self.project.save()

            data = ProjectAnnotateEntitiesSerializer(self.project).data
            self.assertEqual(set(data['cuis'].split(',')), {'A', 'B', 'C', 'X', 'Y'})
        finally:
            if os.path.isfile(abs_path):
                os.unlink(abs_path)

    def test_to_representation_handles_missing_cuis_file_gracefully(self):
        # Do not save() — post_save would try to read cuis_file on disk.
        self.project.cuis_file.name = 'missing_cuis_file.json'

        data = ProjectAnnotateEntitiesSerializer(self.project).data
        self.assertEqual(set(data['cuis'].split(',')), {'A', 'B', 'C'})


@override_settings(MEDIA_ROOT='/tmp/mct-tests-serializers')
class ProjectGroupSerializerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cdb = ConceptDB(name='pg_cdb', cdb_file='pg_cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='pg_vocab', vocab_file='pg_vocab.dat')
        vocab.save(skip_load=True)
        cls.dataset = create_dataset(name='pg_ds', file_name='pg_ds.csv')
        cls.cdb = cdb
        cls.vocab = vocab

    def test_last_modified_is_null_when_group_has_no_projects(self):
        group = ProjectGroup.objects.create(
            name='empty-group',
            dataset=self.dataset,
            concept_db=self.cdb,
            vocab=self.vocab,
            cuis='',
        )
        data = ProjectGroupSerializer(group).data
        self.assertIsNone(data['last_modified'])

    def test_last_modified_is_set_to_latest_project_in_group(self):
        group = ProjectGroup.objects.create(
            name='active-group',
            dataset=self.dataset,
            concept_db=self.cdb,
            vocab=self.vocab,
            cuis='',
        )
        p = ProjectAnnotateEntities()
        p.name = 'p-in-group'
        p.dataset = self.dataset
        p.cuis = ''
        p.concept_db = self.cdb
        p.vocab = self.vocab
        p.group = group
        p.save()

        data = ProjectGroupSerializer(group).data
        self.assertIsNotNone(data['last_modified'])


@override_settings(MEDIA_ROOT='/tmp/mct-tests-serializers')
class DatasetSerializerTests(TestCase):
    def test_serializes_dataset(self):
        dataset = create_dataset(name='ds-test', file_name='ds-test.csv')
        data = DatasetSerializer(dataset).data
        self.assertEqual(data['name'], 'ds-test')
        self.assertIn('original_file', data)
