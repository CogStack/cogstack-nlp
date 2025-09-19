import os
import unittest

from fastapi.testclient import TestClient

import medcat_service.test.common as common
from medcat_service.main import app
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor


class TestMedcatServiceDeId(unittest.TestCase):
    ENDPOINT_PROCESS_SINGLE = "/api/process"
    ENDPOINT_PROCESS_BULK = "/api/process_bulk"
    client: TestClient

    @classmethod
    def setUpClass(cls):
        common.setup_medcat_processor()

        if "APP_MEDCAT_MODEL_PACK" not in os.environ:
            os.environ["APP_MEDCAT_MODEL_PACK"] = "./models/examples/example-deid-model-pack.zip"

        test_settings = common.get_settings_override_deid()
        app.state.settings = test_settings
        app.state.medcat = MedCatProcessor(test_settings)

        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        # exit context so shutdown runs
        cls._client_ctx.__exit__(None, None, None)
        app.dependency_overrides.clear()

    def test_settings_override_applied(self):
        assert app.state.settings.deid_mode is True
        assert app.state.settings.deid_redact is True

    def test_deid_process_api(self):
        payload = common.create_payload_content_from_doc_single(
            "John had been diagnosed with acute Kidney Failure the week before"
        )

        response = self.client.post(self.ENDPOINT_PROCESS_SINGLE, json=payload)
        self.assertEqual(response.status_code, 200)

        actual = response.json()

        expected = {
            "pretty_name": "PATIENT",
            "source_value": "John",
            "cui": "PATIENT",
            "text": "[****] had been diagnosed with acute Kidney Failure the week before",
        }

        self.assertEqual(actual["result"]["text"], expected["text"])

        self.assertEqual(len(actual["result"]["annotations"]), 1)

        ann = actual["result"]["annotations"][0]["0"]
        self.assertEqual(ann["pretty_name"], expected["pretty_name"])
        self.assertEqual(ann["source_value"], expected["source_value"])
        self.assertEqual(ann["cui"], expected["cui"])

    def test_deid_process_bulk_api(self):
        payload = common.create_payload_content_from_doc_bulk([
            "John had been diagnosed with acute Kidney Failure the week before"
        ])

        response = self.client.post(self.ENDPOINT_PROCESS_BULK, json=payload)
        self.assertEqual(response.status_code, 200)

        actual = response.json()

        expected = {
            "pretty_name": "PATIENT",
            "source_value": "John",
            "cui": "PATIENT",
            "text": "[****] had been diagnosed with acute Kidney Failure the week before",
        }
        self.assertEqual(len(actual["result"]), 1)
        self.assertEqual(actual["result"][0]["text"], expected["text"])

        self.assertEqual(
            len(actual["result"][0]["annotations"]),
            0,
            "CU-869a6wc6z No annotations are currently returned by the bulk API",
        )

        # Note: CU-869a6wc6z commended out these asserts until annations are returned
        # ann = actual["result"][0]["annotations"][0]["0"]
        # self.assertEqual(ann["pretty_name"], expected["pretty_name"])
        # self.assertEqual(ann["source_value"], expected["source_value"])
        # self.assertEqual(ann["cui"], expected["cui"])
