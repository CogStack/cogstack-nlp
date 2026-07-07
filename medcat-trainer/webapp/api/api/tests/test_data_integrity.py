import json
import os
from unittest.mock import patch

from django.test import TestCase
from django.core.files.base import ContentFile
from rest_framework.test import APIClient
from api.models import Dataset, Document, ModelPack

from ._helpers import create_user


PROBLEM_PAYLOAD = {
    "projects": [
        {
            "id": 1,
            "name": "HTML-Tag-Challenge-Project",
            "cuis": "",
            "tuis": "",
            "documents": [
                {
                    "id": 50,
                    "name": "Document_With_HTML",
                    # The saboteur string: contains <br> tags
                    "text": "Patient presented with <br> acute chest pain.",
                    "annotations": [
                        {
                            "cui": "12345",
                            "value": "chest pain",
                            "start": 29,  # This may shift if tags are stripped early
                            "end": 39,
                            "correct": True,
                            "validated": True,
                            "deleted": False,
                            "alternative": False,
                            "killed": False,
                            "manually_created": False,
                            "acc": 1.0,
                            "user": "admin",
                            "meta_anns": {}
                        }
                    ]
                }
            ]
        }
    ]
}

class MedCatTrainerImportTests(TestCase):

    def _prepare_model_pack(self, name="data-integrity-test", mp_id: int = 10):
        """Create a ModelPack with a fake unpacked dir (cdb dir + vocab file)."""
        model_pack = ModelPack(name=name, id=mp_id)
        model_pack.model_pack.save(f"{name}.zip", ContentFile(b"fake"), save=False)
        unpacked = model_pack.model_pack.path[: -len(".zip")]
        os.makedirs(os.path.join(unpacked, "cdb"), exist_ok=True)
        with open(os.path.join(unpacked, "vocab"), "w", encoding="utf-8") as fh:
            fh.write("")
        self._register_model_pack(model_pack)
        return model_pack, unpacked

    def _register_model_pack(self, model_pack):
        with patch("api.models.CAT.attempt_unpack"), \
                patch("api.models.CDB.load"), \
                patch("api.models.Vocab.load"), \
                patch("api.utils._load_global_cnf_addon_cnfs", return_value=[]):
            model_pack.save()

    def setUp(self):
        # 1. Create required database dependencies for the import
        self.user = create_user(username='admin', password='password', is_staff=True)
        self.client = APIClient()
        self.client.force_login(self.user)

        self.model_pack, self.unpacked = self._prepare_model_pack()

    def test_upload_project_with_html_tags_in_text(self):
        """
        Ensures that importing a project containing document text with HTML tags 
        succeeds without throwing a NotNullViolation/IntegrityError.
        """
        # Define a project layout mirroring your 'bad' dataset payload structure

        # Build the exact wrapper format expected by the API view / Admin form data
        post_data = {
            "exported_projects": PROBLEM_PAYLOAD,
            "modelpack_id": self.model_pack.id,
            "project_name_suffix": " TEST_IMPORT"
        }
        print("MP ID", self.model_pack.id)

        # Target the API view directly (or change URL to test your Admin /add/ view form submission)
        url = "/api/upload-deployment/"

        print("\n🚀 Executing import payload containing HTML formatting breaks...")

        # Fire the request
        response = self.client.post(
            url, 
            data=json.dumps(post_data), 
            content_type="application/json",
        )

        # 2. Assertions
        # If the bug is active, this will catch a 500 status code with an IntegrityError traceback
        self.assertEqual(
            response.status_code, 200, 
            msg=f"Upload failed! Server responded with status {response.status_code}: {response.content}"
        )

        # Verify the database successfully managed to store the documents and annotations
        self.assertTrue(Dataset.objects.filter(name__contains="HTML-Tag-Challenge").exists())
        self.assertTrue(Document.objects.filter(text__contains="chest pain").exists())
