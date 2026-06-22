import os
from contextlib import contextmanager
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from medcat.cat import CAT

from api.models import ProjectAnnotateEntities, Document, ModelPack


RAW_MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "..",
    "medcat-test-models",
    "mct2_model_pack_train_true.zip"
)
MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "media", "fake_model_pack.zip"
)
os.symlink(
    RAW_MODEL_PATH,
    MODEL_PATH
)


class ModelInferenceTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Load once for the whole test class — it's expensive
        cls.cat = CAT.load_model_pack(MODEL_PATH)

    def setUp(self):
        # A real user — the view reads request.user
        self.user = User.objects.create_user(username="testuser", password="password")
        self.client.force_login(self.user)

        self.model_pack = ModelPack.objects.create(
            name='fake-model',
            model_pack=MODEL_PATH,
        )

        # Minimal project setup
        self.project = ProjectAnnotateEntities.objects.create(
            name="Test Project",
            model_pack=self.model_pack,
            cuis="",
            cuis_file=None,
            use_model_service=False,
            deid_model_annotation=False,
            dataset_id=-1,
        )

        # A document with some text the model can run on
        self.document = Document.objects.create(
            name="Test Doc",
            text="The patient had sever kidney failure.",
            dataset_id=-1,
        )

    @contextmanager
    def use_provided_model(self):
        with patch("api.views.get_medcat", return_value=self.cat):
            yield

    def test_can_use_model_for_inference(self):
        with self.use_provided_model():
            response = self.client.post(
                reverse("prepare_documents"),  # adjust to your actual URL name
                data={
                    "document_ids": [self.document.id],
                    "project_id": self.project.id,
                    "force": 0,
                    "update": 0,
                },
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Documents prepared successfully")

        # The document should now be in prepared_documents
        self.assertIn(self.document, self.project.prepared_documents.all())
