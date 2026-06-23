import os
from contextlib import contextmanager
from unittest.mock import patch
import shutil

import pandas as pd

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from medcat.cat import CAT

from api.models import Document, ProjectAnnotateEntities, ModelPack, Dataset


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


class ModelInferenceTests(TestCase):
    DS_FILE = os.path.join(MEDIA_PATH, "example_ds.csv")
    DS_CONTENT = (("T0", "The patient had severe kidney failure"),)
    DS_COLUMNS = ("name", "text")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._copy_model()
        cls._create_dataset_file()
        # Load once for the whole test class — it's expensive
        cls.cat = CAT.load_model_pack(MODEL_PATH)

    @classmethod
    def tearDownClass(cls):
        os.remove(MODEL_PATH)
        folder_path = MODEL_PATH.removesuffix(".zip")
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
        os.remove(cls.DS_FILE)

    @classmethod
    def _copy_model(cls):
        shutil.copyfile(
            RAW_MODEL_PATH,
            MODEL_PATH
        )

    @classmethod
    def _create_dataset_file(cls):
        df = pd.DataFrame(cls.DS_CONTENT, columns=cls.DS_COLUMNS)
        df.to_csv(cls.DS_FILE)

    def setUp(self):
        # A real user — the view reads request.user
        self.user = User.objects.create_user(username="testuser", password="password", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.model_pack = ModelPack.objects.create(
            name='fake-model',
            model_pack=MODEL_PATH,
        )

        # dataset
        self.dataset = Dataset.objects.create(
            name="fake_dataset",
            original_file=self.DS_FILE,
            description="Fake Dataset"
        )

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
