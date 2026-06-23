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

from api.models import Document, ProjectAnnotateEntities, ModelPack


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
    MEDIA_PATH, "fake_model_pack.zip"
)


HAS_KNOWN_FAILURE = medcat.__version__ in ("2.8.0", "2.8.1", "2.8.2", "2.8.3")


class ModelInferenceTests(TestCase):

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

    def setUp(self):
        # A real user — the view reads request.user
        self.user = create_user(username="testuser", password="password", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.model_pack = ModelPack.objects.create(
            name='fake-model',
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
