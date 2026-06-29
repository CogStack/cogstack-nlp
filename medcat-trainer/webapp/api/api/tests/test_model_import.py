import os
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from api.extensions import model_pack_imported
from api.model_import import ImportModelPackError, import_model_pack
from api.models import ConceptDB, ModelPack


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImportModelPackTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='importer', password='pass')
        self.src_zip = os.path.join(settings.MEDIA_ROOT, 'incoming.zip')
        with open(self.src_zip, 'wb') as fh:
            fh.write(b'fake-model-pack-zip')

    def test_rejects_empty_name(self):
        with self.assertRaises(ImportModelPackError):
            import_model_pack(self.src_zip, name='   ')

    def test_rejects_duplicate_name(self):
        existing = ModelPack(name='snomed-v1')
        existing.save(skip_load=True)
        with self.assertRaises(ImportModelPackError):
            import_model_pack(self.src_zip, name='snomed-v1')

    @patch('api.model_import.dispatch')
    def test_import_from_path_registers_model_pack(self, mock_dispatch):
        from django.db import models as django_models

        def fake_save(self, *args, **kwargs):
            """Stand in for ModelPack.save() without unpacking a real archive."""
            cdb = ConceptDB(name=f'{self.name}_CDB', cdb_file='imported/cdb.dat')
            cdb.save(skip_load=True)
            self.concept_db = cdb
            django_models.Model.save(self)

        with patch.object(ModelPack, 'save', autospec=True, side_effect=fake_save):
            model_pack = import_model_pack(
                self.src_zip,
                name='medcattery-snomed',
                user=self.user,
                description='Pulled from MedCATtery',
                source_uri='https://medcattery.example/models/snomed/3',
            )

        self.assertEqual(model_pack.name, 'medcattery-snomed')
        self.assertEqual(model_pack.last_modified_by, self.user)
        self.assertTrue(model_pack.model_pack.name.startswith('modelpacks/medcattery-snomed-'))
        self.assertTrue(os.path.exists(model_pack.model_pack.path))
        mock_dispatch.assert_called_once()
        signal, kwargs = mock_dispatch.call_args.args[0], mock_dispatch.call_args.kwargs
        self.assertIs(signal, model_pack_imported)
        self.assertEqual(kwargs['model_pack'], model_pack)
        self.assertEqual(kwargs['user'], self.user)
        self.assertEqual(kwargs['description'], 'Pulled from MedCATtery')
        self.assertEqual(kwargs['source_uri'], 'https://medcattery.example/models/snomed/3')
