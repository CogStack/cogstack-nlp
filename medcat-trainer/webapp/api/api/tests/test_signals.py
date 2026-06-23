"""Tests for api.signals dataset / export / model-pack signal handlers."""

import json
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from .. import signals as api_signals
from ..models import (
    ConceptDB,
    Dataset,
    Document,
    ExportedProject,
    MetaCATModel,
    MetaTask,
    ModelPack,
    ProjectAnnotateEntities,
    ProjectAnnotateEntitiesFields,
    Vocabulary,
)
from ._helpers import (
    create_basic_project,
    create_dataset,
    create_user,
    dataset_signals_disconnected,
    make_csv_file,
)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class DatasetSignalTests(TestCase):
    def test_post_save_creates_documents_from_csv(self):
        tmp_dir = tempfile.mkdtemp()
        csv_path = make_csv_file(tmp_dir, rows=[
            {'name': 'sig-doc-1', 'text': 'hello'},
            {'name': 'sig-doc-2', 'text': 'world'},
        ])
        with open(csv_path, 'rb') as fh:
            ds = Dataset(name='signal-ds')
            ds.original_file.save('signal-ds.csv', ContentFile(fh.read()))
        self.assertEqual(Document.objects.filter(dataset=ds).count(), 2)

    def test_pre_save_removes_orphan_documents(self):
        ds = create_dataset(name='orphan-signal-ds', file_name='orphan.csv')
        doc = Document.objects.create(name='old-doc', text='x', dataset=ds)
        self.assertTrue(Document.objects.filter(id=doc.id).exists())

        with dataset_signals_disconnected():
            ds.name = 'orphan-signal-ds-updated'
            ds.save()

        api_signals.pre_save_dataset(sender=Dataset, instance=ds)
        self.assertFalse(Document.objects.filter(id=doc.id).exists())

    def test_post_delete_removes_dataset_file(self):
        tmp_dir = tempfile.mkdtemp()
        csv_path = make_csv_file(tmp_dir)
        with open(csv_path, 'rb') as fh:
            ds = Dataset(name='delete-file-ds')
            ds.original_file.save('delete-file-ds.csv', ContentFile(fh.read()))
        file_path = ds.original_file.path
        self.assertTrue(os.path.isfile(file_path))

        ds_id = ds.id
        Dataset.objects.filter(id=ds_id).delete()
        self.assertFalse(os.path.isfile(file_path))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ExportedProjectSignalTests(TestCase):
    def setUp(self):
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'example.json')
        with open(fixture_path, 'rb') as fh:
            self.export_json = fh.read()

    @patch('api.signals.upload_projects_export')
    def test_post_save_triggers_upload(self, mock_upload):
        cdb = ConceptDB(name='exp-cdb', cdb_file='exp-cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='exp-vocab', vocab_file='exp-vocab.dat')
        vocab.save(skip_load=True)

        exported = ExportedProject(cdb_id=cdb, vocab_id=vocab)
        # FileField.save() persists the ExportedProject and fires post_save once.
        exported.trainer_export_file.save('export.json', ContentFile(self.export_json))

        mock_upload.assert_called_once()
        payload = mock_upload.call_args[0][0]
        self.assertIn('projects', payload)

    def test_post_save_rejects_non_json_extension(self):
        exported = ExportedProject()
        with self.assertRaises(Exception) as ctx:
            exported.trainer_export_file.save('export.txt', ContentFile(b'not json'))
        self.assertIn('.json', str(ctx.exception))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ModelPackSignalTests(TestCase):
    def setUp(self):
        self.cdb = ConceptDB(name='mp-cdb', cdb_file='mp-cdb.dat')
        self.cdb.save(skip_load=True)
        self.vocab = Vocabulary(name='mp-vocab', vocab_file='mp-vocab.dat')
        self.vocab.save(skip_load=True)

    def _create_model_pack(self, name, filename):
        """Create a ModelPack row with a file on disk, without loading the pack."""
        mp = ModelPack(name=name, concept_db=self.cdb, vocab=self.vocab)
        mp.save(skip_load=True)
        path = os.path.join(settings.MEDIA_ROOT, filename)
        with open(path, 'wb') as fh:
            fh.write(b'fake-zip')
        ModelPack.objects.filter(pk=mp.pk).update(model_pack=filename)
        mp.refresh_from_db()
        return mp

    @patch('api.signals.shutil.rmtree')
    @patch('api.signals.os.remove')
    def test_post_delete_removes_pack_assets(self, mock_remove, mock_rmtree):
        mp = self._create_model_pack('pack-to-delete', 'pack.zip')
        pack_path = mp.model_pack.path

        mp.delete()
        mock_rmtree.assert_called_once_with(pack_path.replace('.zip', ''))
        mock_remove.assert_called_once_with(pack_path)

    def test_pre_delete_removes_linked_meta_cat_models(self):
        meta_cat = MetaCATModel.objects.create(name='mc-1', meta_cat_dir='/tmp/mc')
        mp = self._create_model_pack('pack-meta', 'pack-meta.zip')
        mp.meta_cats.add(meta_cat)
        meta_cat_id = meta_cat.id

        mp.delete()
        self.assertFalse(MetaCATModel.objects.filter(id=meta_cat_id).exists())


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ProjectTasksChangedSignalTests(TestCase):
    def test_syncs_tasks_from_model_pack_meta_cats(self):
        meta_cat = MetaCATModel.objects.create(name='sync-mc', meta_cat_dir='/tmp/sync')
        task = MetaTask.objects.create(name='SyncTask', prediction_model=meta_cat)

        cdb = ConceptDB(name='sync-cdb', cdb_file='sync-cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='sync-vocab', vocab_file='sync-vocab.dat')
        vocab.save(skip_load=True)
        mp = ModelPack(name='sync-pack', concept_db=cdb, vocab=vocab)
        mp.save(skip_load=True)
        sync_path = os.path.join(settings.MEDIA_ROOT, 'sync.zip')
        with open(sync_path, 'wb') as fh:
            fh.write(b'fake-zip')
        ModelPack.objects.filter(pk=mp.pk).update(model_pack='sync.zip')
        mp.refresh_from_db()
        mp.meta_cats.add(meta_cat)

        project = create_basic_project(name='sync-proj')
        project.model_pack = mp
        project.concept_db = None
        project.vocab = None
        project.save()

        api_signals.project_tasks_changed(
            sender=ProjectAnnotateEntitiesFields.tasks.through,
            instance=project,
            action='post_add',
        )
        self.assertIn(task, project.tasks.all())

    def test_manual_tasks_persist_when_model_pack_has_no_meta_cats(self):
        # 1. Create a manual task not tied to any automated prediction model
        manual_task = MetaTask.objects.create(name='ManualPresenceTask')

        # 2. Build a lightweight ModelPack that does NOT contain any meta_cats
        cdb = ConceptDB(name='manual-cdb', cdb_file='manual-cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='manual-vocab', vocab_file='manual-vocab.dat')
        vocab.save(skip_load=True)

        mp = ModelPack(name='base-ner-pack', concept_db=cdb, vocab=vocab)
        mp.save(skip_load=True)

        # Write a dummy zip file onto the filesystem so model_pack file validation passes
        pack_path = os.path.join(settings.MEDIA_ROOT, 'manual_base.zip')
        with open(pack_path, 'wb') as fh:
            fh.write(b'fake-zip')
        ModelPack.objects.filter(pk=mp.pk).update(model_pack='manual_base.zip')
        mp.refresh_from_db()

        # 3. Create a project and attach this empty ModelPack
        project = create_basic_project(name='manual-tasks-proj')
        project.model_pack = mp
        project.concept_db = None
        project.vocab = None
        project.save()

        # 4. Add the manual task to the project's many-to-many field
        project.tasks.add(manual_task)

        # 5. Manually trigger the signal matching a Django admin 'post_add' save operation
        api_signals.project_tasks_changed(
            sender=ProjectAnnotateEntitiesFields.tasks.through,
            instance=project,
            action='post_add',
        )

        # 6. Assert that our manual task survived the signal handler execution
        self.assertIn(manual_task, project.tasks.all())
        self.assertEqual(project.tasks.count(), 1)
