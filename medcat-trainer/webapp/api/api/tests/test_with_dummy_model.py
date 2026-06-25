import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
import shutil

from django.test import TestCase
import unittest
from rest_framework.test import APIClient
from ._helpers import create_dataset, create_user, create_document

import medcat
from medcat.cat import CAT
from medcat.components.addons.meta_cat import MetaCATAddon

from api.models import Document, ProjectAnnotateEntities, ModelPack
from api.model_import import import_model_pack


RAW_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "..",
    "medcat-test-models",
    "mct2_model_pack_train_true.zip"
)
MEDIA_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "media"
)
MODEL_PATH = os.path.join(
    MEDIA_PATH, "dummy_model_pack.zip"
)
MODEL_PATH_UNPACKED = MODEL_PATH.removesuffix(".zip")


HAS_KNOWN_FAILURE = medcat.__version__ in ("2.8.0", "2.8.1", "2.8.2", "2.8.3")


class BaseRealModelTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._copy_model()
        # Load once for the whole test class — it's expensive
        cls.cat = CAT.load_model_pack(MODEL_PATH)

    @classmethod
    def tearDownClass(cls):
        os.remove(MODEL_PATH)
        folder_path = MODEL_PATH.removesuffix(".zip")
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

    @classmethod
    def _copy_model(cls):
        shutil.copyfile(
            RAW_MODEL_PATH,
            MODEL_PATH
        )


class ModelInferenceTests(BaseRealModelTests):

    def setUp(self):
        # A real user — the view reads request.user
        self.user = create_user(username="testuser", password="password", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.model_pack = ModelPack.objects.create(
            name='test-model',
            model_pack=MODEL_PATH,
        )

        # dataset
        self.dataset = create_dataset("FAKE-ds")
        # NOTE: self.dataset will be used to map to the dataset
        self.document = create_document(self, "DOC1", "Patient has severe kidney failure")

        # Minimal project setup
        self.project = ProjectAnnotateEntities.objects.create(
            name="Test Project",
            model_pack=self.model_pack,
            cuis="",
            cuis_file=None,
            use_model_service=False,
            deid_model_annotation=False,
            dataset_id=self.dataset.id,
        )

    @contextmanager
    def use_provided_model(self):
        with patch("api.views.get_medcat", return_value=self.cat):
            yield

    @unittest.skipIf(HAS_KNOWN_FAILURE, "Known to fail in 2.8.* (<2.8.4), specfically")
    def test_can_use_model_for_inference(self):
        with self.use_provided_model():
            doc_ids = [doc.id for doc in Document.objects.all()]
            response = self.client.post(
                "/api/prepare-documents/",
                data={
                    "document_ids": doc_ids,
                    "project_id": self.project.id,
                    "force": 0,
                    "update": 0,
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Documents prepared successfully")

        # The document should now be in prepared_documents
        self.assertTrue(self.project.prepared_documents.all())
        self.assertEqual(len(self.project.prepared_documents.all()), len(doc_ids))


class ModelImportTests(BaseRealModelTests):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_meta_cat_for_model()

    # NOTE: if MetaCATAddons are going to be loaded,
    #       it would fail with this, but with previous
    #       code an attempt would have been made.
    @classmethod
    def _create_meta_cat_for_model(cls):
        # first, create the folder
        from api.utils import _PATH_TO_META_CAT_START, _PATH_TO_CNF_ON_DISK
        mc_path = os.path.join(MODEL_PATH_UNPACKED, _PATH_TO_META_CAT_START + "Subject")
        os.mkdir(os.path.dirname(mc_path))
        os.mkdir(mc_path)
        # then add .serialised_by
        sb_path = os.path.join(mc_path, ".serialised_by")
        with open(sb_path, 'w') as f:
            f.write("dill")
        # finally, add config
        from medcat.config.config_meta_cat import ConfigMetaCAT
        # create config
        cnf = ConfigMetaCAT()
        cnf.general.category_name = "Subject"
        # load off disk
        import dill
        gcnf_path = os.path.join(MODEL_PATH_UNPACKED, _PATH_TO_CNF_ON_DISK)
        with open(gcnf_path, 'rb') as f:
            data = dill.load(f)
        data['addons'] = [cnf]
        # save to disk
        with open(gcnf_path, 'wb') as f:
            dill.dump(data, f)

    def setUp(self):
        # A real user — the view reads request.user
        self.user = create_user(username="testuser", password="password", is_staff=True)

    # NOTE: mocking dispatch just so it won't complain about missing sender
    @patch('api.model_import.dispatch')
    def test_model_import_does_not_load_addons(self, mock_dispatch):
        with patch.object(MetaCATAddon, "__init__") as mock_init:
            import_model_pack(
                MODEL_PATH,
                name='test-model',
                user=self.user,
                description='Fake model!',
                source_uri='https://some/address',
            )
        mock_init.assert_not_called()


# class RealModelTests(TestCase):
#     MODEL_PATH = "../../../medcat-v2/.temp/20230227__kch_gstt_trained_model_f76d2121b77c3e9a/"

#     def test_can_read_from_real_model(self):
#         from api.utils import load_meta_cat_info_from_model_folder
#         infos = load_meta_cat_info_from_model_folder(self.MODEL_PATH)
#         self.assertEqual(len(infos), 3)
#         categories = {
#             cnf.general.category_name
#             for _, cnf in infos
#         }
#         self.assertEqual(
#             categories,
#             {"Presence", "Subject", "Time"}
#         )
