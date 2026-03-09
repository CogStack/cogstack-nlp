"""End-to-end happy-path test for projects using a remote MedCAT model service.

This test mirrors the UI flow when a user works with a remote-model project:
1. Set up a project configured with use_model_service=True and a dataset containing one document.
2. Call GET /api/cache-project-model/<id>/ and assert 200 (no local model to load; endpoint returns success).
3. Call POST /api/prepare-documents/ with project_id and document_ids; the view calls the remote
   MedCAT service to get annotations. Only the HTTP call to the remote service is stubbed (requests.post);
   the rest of the stack (auth, DB, add_annotations, prepared_documents) runs for real.

Assertions include: both endpoints return 200, the stub was called with the expected URL and document
text, and the document is added to the project's prepared_documents.
"""

import json
import os
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from ..models import Dataset, Document, ProjectAnnotateEntities


class RemoteModelServiceE2ETestCase(TestCase):
    """Single test: create remote project + dataset with one document, then call cache and prepare-documents."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        csv_content = b"name,text\ndoc1,Patient had acute kidney failure."
        self.dataset = Dataset(
            name="Test Remote Dataset",
            original_file=SimpleUploadedFile("test.csv", csv_content, content_type="text/csv"),
        )
        self.dataset.save()
        self.document = Document.objects.create(
            dataset=self.dataset,
            name="doc1",
            text="Patient had acute kidney failure.",
        )
        self.project = ProjectAnnotateEntities.objects.create(
            name="Test Remote Project",
            dataset=self.dataset,
            use_model_service=True,
            model_service_url="http://medcat-service:8000",
            cuis="",
        )
        self.project.members.add(self.user)

    def _run_cache_and_prepare_then_assert_annotated_entities(
        self, mock_json_return_value, expected_annotated_entities_str
    ):
        """Shared flow: stub medcat-service with given response, call cache + prepare-documents + annotated-entities, assert response matches expected JSON string."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = mock_json_return_value

        with patch.dict(os.environ, {"REMOTE_MODEL_SERVICE_TYPE": "medcat"}):
            with patch("api.utils.requests.post", return_value=mock_response) as mock_post:
                client = APIClient()
                client.force_authenticate(user=self.user)

                cache_resp = client.get(f"/api/cache-project-model/{self.project.id}/")
                self.assertEqual(cache_resp.status_code, 200)

                prepare_resp = client.post(
                    "/api/prepare-documents/",
                    data={"project_id": self.project.id, "document_ids": [self.document.id]},
                    format="json",
                )
                self.assertEqual(prepare_resp.status_code, 200)
                self.assertEqual(prepare_resp.json().get("message"), "Documents prepared successfully")

                mock_post.assert_called_once()
                call_args, call_kwargs = mock_post.call_args
                self.assertEqual(call_args[0], f"{self.project.model_service_url.rstrip('/')}/api/process")
                self.assertEqual(call_kwargs["json"], {"content": {"text": self.document.text}})
                self.assertIn("timeout", call_kwargs)

                self.project.refresh_from_db()
                self.assertIn(self.document, self.project.prepared_documents.all())

                ann_resp = client.get(
                    "/api/annotated-entities/",
                    data={"project": self.project.id, "document": self.document.id},
                )
                self.assertEqual(ann_resp.status_code, 200)
                expected = json.loads(expected_annotated_entities_str)
                actual = ann_resp.json()
                self.assertEqual(actual["count"], expected["count"])
                self.assertEqual(actual["next"], expected["next"])
                self.assertEqual(actual["previous"], expected["previous"])
                self.assertEqual(len(actual["results"]), len(expected["results"]))
                for i, exp_result in enumerate(expected["results"]):
                    for key in exp_result:
                        self.assertEqual(
                            actual["results"][i].get(key), exp_result[key], f"results[{i}].{key}"
                        )

    def test_cache_and_prepare_documents_remote_project_empty_annotations(self):
        """GET cache-project-model returns 200; POST prepare-documents with stubbed medcat-service returns 200."""
        mock_json = {
            "result": {
                "text": self.document.text,
                "annotations": [],
                "success": True,
                "timestamp": "",
                "elapsed_time": 0,
                "footer": None,
            }
        }
        expected_str = """
        {
            "count": 0,
            "next": null,
            "previous": null,
            "results": []
        }
        """
        self._run_cache_and_prepare_then_assert_annotated_entities(mock_json, expected_str)

    def test_cache_and_prepare_documents_remote_project_with_annotations(self):
        """Same flow but mock returns one annotation; assert annotated-entities list includes it."""
        mock_json = {
            "result": {
                "text": self.document.text,
                "annotations": [
                    {
                        "0": {
                            "cui": "C0022660",
                            "start": 10,
                            "end": 30,
                            "source_value": "acute kidney failure",
                            "detected_name": "acute~kidney~failure",
                            "acc": 0.99,
                            "context_similarity": 0.99,
                            "meta_anns": {},
                        }
                    }
                ],
                "success": True,
                "timestamp": "",
                "elapsed_time": 0,
                "footer": None,
            }
        }
        expected_str = """
        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "value": "acute~kidney~failure",
                    "start_ind": 10,
                    "end_ind": 30,
                    "acc": 0.99,
                    "comment": null,
                    "validated": false,
                    "correct": false,
                    "alternative": false,
                    "manually_created": false,
                    "deleted": false,
                    "killed": false,
                    "irrelevant": false
                }
            ]
        }
        """
        self._run_cache_and_prepare_then_assert_annotated_entities(mock_json, expected_str)
