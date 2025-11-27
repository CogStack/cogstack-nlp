import json
import os
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from ..data_utils import upload_projects_export, InvalidParameterError
from ..models import (
    ProjectAnnotateEntities, ConceptDB, Vocabulary, ModelPack,
    Dataset, Document, Entity, AnnotatedEntity, MetaTask, MetaTaskValue,
    MetaAnnotation, Relation, EntityRelation
)


class UploadProjectsExportTestCase(TestCase):
    """Test cases for upload_projects_export function"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a test user
        self.user = User.objects.create_user(
            username='synthetic_reviewer',
            email='test@example.com',
            password='testpass123'
        )

        # Create test ConceptDB and Vocabulary with skip_load to avoid file validation
        self.cdb = ConceptDB(
            name='test_cdb',
            cdb_file='test_cdb.dat',
            use_for_training=True
        )
        self.cdb.save(skip_load=True)

        self.vocab = Vocabulary(
            name='test_vocab',
            vocab_file='test_vocab.dat'
        )
        self.vocab.save(skip_load=True)

        # Load example JSON from test fixtures
        example_json_path = os.path.join(
            os.path.dirname(__file__),
            'fixtures', 'example.json'
        )
        with open(example_json_path, 'r') as f:
            self.medcat_export = json.load(f)

    def _patch_media_root(self):
        """Helper method to patch MEDIA_ROOT in data_utils module"""
        from django.conf import settings
        from .. import data_utils
        original_media_root = data_utils.MEDIA_ROOT
        data_utils.MEDIA_ROOT = settings.MEDIA_ROOT
        return original_media_root

    def _restore_media_root(self, original_media_root):
        """Helper method to restore MEDIA_ROOT in data_utils module"""
        from .. import data_utils
        data_utils.MEDIA_ROOT = original_media_root

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_projects_export_with_cdb_vocab(self):
        """Test uploading projects export with CDB and Vocabulary"""
        original_media_root = self._patch_media_root()
        try:
            # Call the function
            upload_projects_export(
                medcat_export=self.medcat_export,
                cdb_id=str(self.cdb.id),
                vocab_id=str(self.vocab.id),
                modelpack_id=None
            )

            # Verify project was created
            project = ProjectAnnotateEntities.objects.get(
                name="SMAll_SYNT-EXAMPLE-AD IMPORTED"
            )
            self.assertIsNotNone(project)
            self.assertEqual(project.concept_db.id, self.cdb.id)
            self.assertEqual(project.vocab.id, self.vocab.id)

            # Verify dataset was created
            dataset = project.dataset
            self.assertIsNotNone(dataset)
            self.assertEqual(dataset.name, "SMAll_SYNT-EXAMPLE-AD IMPORTED_dataset")

            # Verify document was created
            document = Document.objects.filter(dataset=dataset).first()
            self.assertIsNotNone(document)
            self.assertIn("Patient reports increasing forgetfulness", document.text)

            # Verify entity was created
            entity = Entity.objects.get(label="26929004")
            self.assertIsNotNone(entity)

            # Verify annotated entity was created
            annotated_entity = AnnotatedEntity.objects.filter(
                project=project,
                document=document,
                entity=entity
            ).first()
            self.assertIsNotNone(annotated_entity)
            self.assertEqual(annotated_entity.value, "Neurodegenerative dementia")
            self.assertEqual(annotated_entity.start_ind, 265)
            self.assertEqual(annotated_entity.end_ind, 291)
            self.assertEqual(annotated_entity.user, self.user)
            self.assertTrue(annotated_entity.validated)
            self.assertTrue(annotated_entity.correct)
            self.assertFalse(annotated_entity.deleted)
            self.assertFalse(annotated_entity.alternative)
            self.assertFalse(annotated_entity.killed)
            self.assertFalse(annotated_entity.irrelevant)
            self.assertFalse(annotated_entity.manually_created)
            self.assertEqual(annotated_entity.acc, 1.0)

            # Verify meta tasks were created
            meta_task_presence = MetaTask.objects.get(name="Presence")
            meta_task_subject = MetaTask.objects.get(name="Subject")
            meta_task_time = MetaTask.objects.get(name="Time")
            self.assertIsNotNone(meta_task_presence)
            self.assertIsNotNone(meta_task_subject)
            self.assertIsNotNone(meta_task_time)

            # Verify meta task values were created
            meta_value_true = MetaTaskValue.objects.get(name="True")
            meta_value_patient = MetaTaskValue.objects.get(name="Patient")
            meta_value_recent = MetaTaskValue.objects.get(name="Recent")
            self.assertIsNotNone(meta_value_true)
            self.assertIsNotNone(meta_value_patient)
            self.assertIsNotNone(meta_value_recent)

            # Verify meta annotations were created
            meta_ann_presence = MetaAnnotation.objects.filter(
                annotated_entity=annotated_entity,
                meta_task=meta_task_presence
            ).first()
            self.assertIsNotNone(meta_ann_presence)
            self.assertEqual(meta_ann_presence.meta_task_value, meta_value_true)
            self.assertTrue(meta_ann_presence.validated)
            self.assertEqual(meta_ann_presence.acc, 1)

            meta_ann_subject = MetaAnnotation.objects.filter(
                annotated_entity=annotated_entity,
                meta_task=meta_task_subject
            ).first()
            self.assertIsNotNone(meta_ann_subject)
            self.assertEqual(meta_ann_subject.meta_task_value, meta_value_patient)

            meta_ann_time = MetaAnnotation.objects.filter(
                annotated_entity=annotated_entity,
                meta_task=meta_task_time
            ).first()
            self.assertIsNotNone(meta_ann_time)
            self.assertEqual(meta_ann_time.meta_task_value, meta_value_recent)
        finally:
            self._restore_media_root(original_media_root)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    @patch('api.models.CAT.attempt_unpack')
    @patch('api.models.CAT.load_cdb')
    @patch('api.models.CAT.load_addons')
    @patch('api.models.Vocab.load')
    @patch('os.path.exists')
    def test_upload_projects_export_with_modelpack(self, mock_exists, mock_vocab_load, mock_load_addons, mock_cdb_load, mock_unpack):
        """Test uploading projects export with ModelPack"""
        original_media_root = self._patch_media_root()
        try:
            # Mock all file operations
            mock_exists.return_value = False
            mock_load_addons.return_value = []
            # Create a model pack - the save will be mocked to avoid actual file operations
            from django.core.files.uploadedfile import SimpleUploadedFile
            modelpack = ModelPack(
                name='test_modelpack',
                model_pack=SimpleUploadedFile('test_modelpack.zip', b'fake zip')
            )
            # Save with mocked file operations - it will fail on file loading but that's ok
            try:
                modelpack.save()
            except (FileNotFoundError, Exception):
                # If save fails, create it directly in the database
                from django.utils import timezone
                ModelPack.objects.filter(name='test_modelpack').delete()
                modelpack = ModelPack.objects.create(
                    name='test_modelpack',
                    model_pack='test_modelpack.zip'
                )
                # Manually set the file field to avoid save() being called again
                ModelPack.objects.filter(id=modelpack.id).update(model_pack='test_modelpack.zip')
                modelpack.refresh_from_db()

            # Call the function
            upload_projects_export(
                medcat_export=self.medcat_export,
                cdb_id=None,
                vocab_id=None,
                modelpack_id=str(modelpack.id)
            )

            # Verify project was created with modelpack
            project = ProjectAnnotateEntities.objects.get(
                name="SMAll_SYNT-EXAMPLE-AD IMPORTED"
            )
            self.assertIsNotNone(project)
            self.assertEqual(project.model_pack.id, modelpack.id)
        finally:
            self._restore_media_root(original_media_root)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_projects_export_no_cdb_vocab_modelpack(self):
        """Test that InvalidParameterError is raised when no cdb/vocab/modelpack provided"""
        with self.assertRaises(InvalidParameterError) as context:
            upload_projects_export(
                medcat_export=self.medcat_export,
                cdb_id=None,
                vocab_id=None,
                modelpack_id=None
            )
        self.assertIn("No cdb, vocab, or modelpack provided", str(context.exception))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_projects_export_skips_empty_projects(self):
        """Test that projects with no documents are skipped"""
        original_media_root = self._patch_media_root()
        try:
            # Create export with empty project
            empty_export = {
                "projects": [
                    {
                        "name": "Empty Project",
                        "cuis": "",
                        "documents": []
                    }
                ]
            }

            upload_projects_export(
                medcat_export=empty_export,
                cdb_id=str(self.cdb.id),
                vocab_id=str(self.vocab.id),
                modelpack_id=None
            )

            # Verify no project was created
            self.assertFalse(
                ProjectAnnotateEntities.objects.filter(name__contains="Empty Project").exists()
            )
        finally:
            self._restore_media_root(original_media_root)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_projects_export_with_custom_suffix(self):
        """Test uploading with custom project name suffix"""
        original_media_root = self._patch_media_root()
        try:
            upload_projects_export(
                medcat_export=self.medcat_export,
                cdb_id=str(self.cdb.id),
                vocab_id=str(self.vocab.id),
                modelpack_id=None,
                project_name_suffix=' - CUSTOM'
            )

            # Verify project was created with custom suffix
            project = ProjectAnnotateEntities.objects.get(
                name="SMAll_SYNT-EXAMPLE-AD - CUSTOM"
            )
            self.assertIsNotNone(project)
        finally:
            self._restore_media_root(original_media_root)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_projects_export_with_members(self):
        """Test uploading with members"""
        original_media_root = self._patch_media_root()
        try:
            user2 = User.objects.create_user(
                username='user2',
                email='user2@example.com',
                password='testpass123'
            )

            upload_projects_export(
                medcat_export=self.medcat_export,
                cdb_id=str(self.cdb.id),
                vocab_id=str(self.vocab.id),
                modelpack_id=None,
                members=[str(self.user.id), str(user2.id)]
            )

            # Verify project was created with members
            project = ProjectAnnotateEntities.objects.get(
                name="SMAll_SYNT-EXAMPLE-AD IMPORTED"
            )
            self.assertIn(self.user, project.members.all())
            self.assertIn(user2, project.members.all())
        finally:
            self._restore_media_root(original_media_root)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_projects_export_with_set_validated_docs(self):
        """Test uploading with set_validated_docs=True"""
        original_media_root = self._patch_media_root()
        try:
            upload_projects_export(
                medcat_export=self.medcat_export,
                cdb_id=str(self.cdb.id),
                vocab_id=str(self.vocab.id),
                modelpack_id=None,
                set_validated_docs=True
            )

            # Verify project was created
            project = ProjectAnnotateEntities.objects.get(
                name="SMAll_SYNT-EXAMPLE-AD IMPORTED"
            )
            dataset = project.dataset
            documents = Document.objects.filter(dataset=dataset)

            # Verify all documents are in validated_documents
            for doc in documents:
                self.assertIn(doc, project.validated_documents.all())
        finally:
            self._restore_media_root(original_media_root)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_projects_export_with_unavailable_user(self):
        """Test that unavailable users cause KeyError when trying to create annotations"""
        original_media_root = self._patch_media_root()
        try:
            # Create export with non-existent user
            export_with_unknown_user = {
                "projects": [
                    {
                        "name": "Test Project",
                        "cuis": "",
                        "documents": [
                            {
                                "name": "Doc1",
                                "text": "Test text",
                                "annotations": [
                                    {
                                        "start": 0,
                                        "end": 4,
                                        "cui": "C123456",
                                        "value": "Test",
                                        "validated": True,
                                        "user": "nonexistent_user",
                                        "meta_anns": {},
                                        "correct": True,
                                        "deleted": False,
                                        "alternative": False,
                                        "killed": False,
                                        "irrelevant": False,
                                        "manually_created": False,
                                        "acc": 1.0
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }

            # This should raise a KeyError when trying to access the non-existent user
            with self.assertRaises(KeyError):
                upload_projects_export(
                    medcat_export=export_with_unknown_user,
                    cdb_id=str(self.cdb.id),
                    vocab_id=str(self.vocab.id),
                    modelpack_id=None
                )
        finally:
            self._restore_media_root(original_media_root)

