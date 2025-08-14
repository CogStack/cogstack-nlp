import unittest

from fastapi.testclient import TestClient

import medcat_service.test.common as common


class TestMedcatServiceDeId(unittest.TestCase):
    """
    Implementation of test cases for MedCAT service
    """

    # Available endpoints
    #
    ENDPOINT_PROCESS_SINGLE = "/api/process"
    ENDPOINT_PROCESS_BULK = "/api/process_bulk"
    client: TestClient

    # Static initialization methods
    #
    @classmethod
    def setUpClass(cls):
        pass
        # Enable when test enabled. Complexity around env vars being shared accross tests,
        # Should instead move to use pydantic settings for easy test overrides.

        # common.setup_medcat_processor()
        # os.environ["DEID_MODE"] = "True"
        # os.environ["DEID_REDACT"] = "True"

        # if "APP_MEDCAT_MODEL_PACK" not in os.environ:
        #     os.environ["APP_MEDCAT_MODEL_PACK"] = "./models/example-deid-model-pack.zip"

        # cls.client = TestClient(app)

    @unittest.skip("Disabled until deid model is committed")
    def testDeidProcess(self):
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
