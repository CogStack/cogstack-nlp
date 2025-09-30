#!/usr/bin/env python

import logging
import unittest

from fastapi.testclient import TestClient

import medcat_service.test.common as common
from medcat_service.main import app


class TestMedcatService(unittest.TestCase):
    """
    Implementation of test cases for MedCAT service
    """

    # Available endpoints
    #
    ENDPOINT_PROCESS_SINGLE = '/api/process'
    ENDPOINT_PROCESS_BULK = '/api/process_bulk'
    client: TestClient

    # Static initialization methods
    #
    @classmethod
    def setUpClass(cls):
        """
        Initializes the resources before all the tests are run. It is run only once.
        The Flask app instance is created only once when starting all the unit tests.
        :return:
        """
        cls._setup_logging(cls)
        common.setup_medcat_processor()
        cls.client = TestClient(app)

    @staticmethod
    def _setup_logging(cls):
        log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
        logging.basicConfig(format=log_format, level=logging.INFO)
        cls.log = logging.getLogger(__name__)

    # unit test helper methods
    #
    def _testProcessSingleDoc(self, doc):
        """
            Tests processing a single document as:
            - create a JSON payload given the input doc
            - post the payload to the single processing endpoing
            - parse the response and check the returned result
            :param doc: input document to be processed (string)
            :return:
        """
        payload = common.create_payload_content_from_doc_single(doc)
        response = self.client.post(self.ENDPOINT_PROCESS_SINGLE, json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertGreater(len(data["result"]["annotations"]), 0)

    def _testProcessBulkMultipleDocs(self, docs, multiply_sizes):
        """
            Tests processing a bulk of document in sets of multiple batches, where, per each:
            - create a JSON payload given the input doc
            - post the payload to the single processing endpoing
            - parse the response and check the returned result
            :param docs: input document to be processed (string)
            :param: multiply_sizes: array of different bulk sizes to be tested
            :return:
        """
        for n in multiply_sizes:
            req_docs = docs * n
            payload = common.create_payload_content_from_doc_bulk(req_docs)

            response = self.client.post(self.ENDPOINT_PROCESS_BULK, json=payload)
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertEqual(len(data["result"]), n * len(docs))

            for res in data["result"]:
                self.assertGreater(len(res["annotations"]), 0)

    def __init__(self, *args, **kwargs):
        super(TestMedcatService, self).__init__(*args, **kwargs)

    # the actual unit tests
    #
    def testProcessSingleShortDoc(self):
        doc = common.get_example_short_document()
        self._testProcessSingleDoc(doc)

        # TODO: check the returned annotations

    def testProcessSingleLongDoc(self):
        doc = common.get_example_long_document()
        self._testProcessSingleDoc(doc)

        # TODO: check the returned annotations

    def testProcessSingleBlankDocs(self):
        for doc in common.get_blank_documents():
            payload = common.create_payload_content_from_doc_single(doc)

            response = self.client.post(self.ENDPOINT_PROCESS_SINGLE, json=payload)
            self.assertEqual(response.status_code, 200)

            data = response.json()
            self.assertEqual(len(data["result"]["annotations"][0]), 0)

    def testProcessBadRequest(self):
        payload = {"content": {"bad_request": "NA"}}
        response = self.client.post(self.ENDPOINT_PROCESS_SINGLE, json=payload)
        self.assertEqual(response.status_code, 422)

    def testProcessMetaAnnsFilter(self):
        payload = {
            "content": {
                "text": "< some clinical text>"
            },
            "meta_anns_filters": [
                ["Presence", ["True"]],
                ["Subject", ["Patient", "Family"]],
                ["Time", ["Recent"]]
            ]
        }

        a_client = TestClient(app, raise_server_exceptions=False)
        response = a_client.post(self.ENDPOINT_PROCESS_SINGLE, json=payload)
        self.assertEqual(
            response.status_code, 200,
            """
            This test currently shows that there is a bug with the meta anns filter.
            Correct version should return 200.
            KeyError: 'Presence' on all(e['meta_anns'][task]['vaue'] in filter_values"
            """)

    def testProcessBulkBlankDocs(self):
        docs = common.get_blank_documents()
        payload = common.create_payload_content_from_doc_bulk(docs)

        response = self.client.post(self.ENDPOINT_PROCESS_BULK, json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        for res in data["result"]:
            self.assertEqual(len(res["annotations"]), 0)

    def testProcessBulkMultipleShortDocs(self):
        multiply_sizes = [1, 5, 10, 30, 100]
        doc = common.get_example_long_document()
        self._testProcessBulkMultipleDocs([doc], multiply_sizes)

        # TODO: check annotations

    def testProcessBulkMultipleLongDocs(self):
        multiply_sizes = [1, 5, 10, 30, 100]
        doc = common.get_example_long_document()
        self._testProcessBulkMultipleDocs([doc], multiply_sizes)

        # TODO: check annotations

    def testProcessBulkLongShortDocs(self):
        request_sizes = [1, 5, 10, 30, 100]
        docs = [common.get_example_short_document(), common.get_example_long_document()]
        self._testProcessBulkMultipleDocs(docs, request_sizes)

        # TODO: check annotations


if __name__ == "__main__":
    unittest.main()
