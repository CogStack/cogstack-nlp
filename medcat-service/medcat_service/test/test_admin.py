import unittest

from fastapi.testclient import TestClient

from medcat_service.main import app
from medcat_service.test.common import setup_medcat_processor


class TestAdminApi(unittest.TestCase):
    ENDPOINT_INFO_ENDPOINT = "/api/info"

    def setUp(self):
        setup_medcat_processor()
        self.client = TestClient(app)

    def testGetInfo(self):
        response = self.client.get(self.ENDPOINT_INFO_ENDPOINT)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
