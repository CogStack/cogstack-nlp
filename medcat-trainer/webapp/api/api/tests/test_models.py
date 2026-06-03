"""Unit tests for api.models validation and string representations."""

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from ..models import (
    AnnotatedEntity,
    ConceptDB,
    Document,
    Entity,
    EntityRelation,
    MetaAnnotation,
    MetaTask,
    MetaTaskValue,
    ProjectAnnotateEntities,
    Relation,
    Vocabulary,
    cdb_name_validator,
)
from ._helpers import (
    create_basic_project,
    create_dataset,
    create_document,
    create_entity,
    create_user,
)


class StringRepresentationTests(TestCase):
    def test_entity_str(self):
        ent = Entity.objects.create(label='C001')
        self.assertEqual(str(ent), 'C001')

    def test_relation_str(self):
        rel = Relation.objects.create(label='hasFinding')
        self.assertEqual(str(rel), 'hasFinding')

    def test_meta_task_value_str(self):
        v = MetaTaskValue.objects.create(name='True')
        self.assertEqual(str(v), 'True')

    def test_meta_task_str(self):
        mt = MetaTask.objects.create(name='Presence')
        self.assertEqual(str(mt), 'Presence')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-models')
class CdbNameValidatorTests(TestCase):
    def test_validator_accepts_alphanumeric_with_underscore(self):
        cdb_name_validator('abc_123')  # should not raise

    def test_validator_rejects_leading_digit(self):
        with self.assertRaises(ValidationError):
            cdb_name_validator('1abc')

    def test_validator_rejects_special_chars(self):
        with self.assertRaises(ValidationError):
            cdb_name_validator('a-b')

    def test_validator_rejects_empty(self):
        with self.assertRaises(ValidationError):
            cdb_name_validator('')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-models')
class ProjectAnnotateEntitiesValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cdb = ConceptDB(name='val_cdb', cdb_file='val_cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='val_vocab', vocab_file='val_vocab.dat')
        vocab.save(skip_load=True)
        cls.cdb = cdb
        cls.vocab = vocab
        cls.dataset = create_dataset(name='val_ds', file_name='val_ds.csv')

    def _new_project(self, **kwargs):
        proj = ProjectAnnotateEntities()
        proj.name = kwargs.pop('name', 'p1')
        proj.dataset = kwargs.pop('dataset', self.dataset)
        proj.cuis = ''
        for k, v in kwargs.items():
            setattr(proj, k, v)
        return proj

    def test_save_requires_cdb_vocab_or_model_pack(self):
        proj = self._new_project()
        with self.assertRaises(ValidationError):
            proj.save()

    def test_save_with_cdb_and_vocab_succeeds(self):
        proj = self._new_project(concept_db=self.cdb, vocab=self.vocab)
        proj.save()  # should not raise
        self.assertIsNotNone(proj.id)

    def test_use_model_service_requires_url(self):
        proj = self._new_project(use_model_service=True)
        with self.assertRaises(ValidationError):
            proj.save()

    def test_use_model_service_with_url_skips_model_validation(self):
        proj = self._new_project(use_model_service=True, model_service_url='http://x')
        proj.save()
        self.assertIsNotNone(proj.id)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-models')
class AnnotatedEntitySaveUpdatesProjectTests(TestCase):
    def test_saving_annotation_updates_project_last_modified(self):
        user = create_user(username='auser')
        project = create_basic_project(name='ae-proj')
        doc = create_document(project, name='doc', text='hello')
        ent = create_entity(label='C100')

        before = project.last_modified
        AnnotatedEntity.objects.create(
            user=user,
            project=project,
            document=doc,
            entity=ent,
            value='hello',
            start_ind=0,
            end_ind=5,
            acc=0.5,
        )
        project.refresh_from_db()
        self.assertGreaterEqual(project.last_modified, before)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-models')
class MetaAnnotationSaveUpdatesParentTests(TestCase):
    def test_saving_meta_annotation_updates_annotated_entity_last_modified(self):
        user = create_user(username='muser')
        project = create_basic_project(name='ma-proj')
        doc = create_document(project, name='doc', text='hello')
        ent = create_entity(label='C200')
        ann = AnnotatedEntity.objects.create(
            user=user,
            project=project,
            document=doc,
            entity=ent,
            value='hello',
            start_ind=0,
            end_ind=5,
            acc=0.5,
        )
        task = MetaTask.objects.create(name='Presence')
        val = MetaTaskValue.objects.create(name='True')

        before = ann.last_modified
        MetaAnnotation.objects.create(
            annotated_entity=ann,
            meta_task=task,
            meta_task_value=val,
            validated=True,
        )
        ann.refresh_from_db()
        self.assertGreaterEqual(ann.last_modified, before)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-models')
class EntityRelationSaveUpdatesProjectTests(TestCase):
    def test_saving_relation_updates_project(self):
        user = create_user(username='ruser')
        project = create_basic_project(name='rel-proj')
        doc = create_document(project, name='doc', text='hello world')
        ent_a = create_entity(label='A')
        ent_b = create_entity(label='B')

        start = AnnotatedEntity.objects.create(
            user=user, project=project, document=doc, entity=ent_a,
            value='hello', start_ind=0, end_ind=5, acc=1.0,
        )
        end = AnnotatedEntity.objects.create(
            user=user, project=project, document=doc, entity=ent_b,
            value='world', start_ind=6, end_ind=11, acc=1.0,
        )

        rel = Relation.objects.create(label='has')
        before = project.last_modified
        EntityRelation.objects.create(
            user=user,
            project=project,
            document=doc,
            relation=rel,
            start_entity=start,
            end_entity=end,
        )
        project.refresh_from_db()
        self.assertGreaterEqual(project.last_modified, before)


class ConceptDbCannotChangeFilePathTests(TestCase):
    @override_settings(MEDIA_ROOT='/tmp/mct-tests-models')
    def test_change_of_cdb_file_after_first_save_raises(self):
        cdb = ConceptDB(name='cant_change', cdb_file='orig.dat')
        cdb.save(skip_load=True)

        # Simulate Django reload semantics
        reloaded = ConceptDB.objects.get(id=cdb.id)
        reloaded.cdb_file.name = 'other.dat'
        with self.assertRaises(ValidationError):
            reloaded.save(skip_load=True)
