import unittest

from fastapi.testclient import TestClient

from medcat_service.dependencies import get_medcat_processor
from medcat_service.main import app
from medcat_service.test.common import setup_medcat_processor
from medcat_service.types import HealthCheckResponse


def override_processor():
    class StubProcessor:
        def is_ready(self):
            return HealthCheckResponse(name="MedCAT", status="DOWN")

    return StubProcessor()


class TestHealthApi(unittest.TestCase):
    ENDPOINT_HEALTH_LIVE = "/api/health/live"
    ENDPOINT_HEALTH_READY = "/api/health/ready"

    def setUp(self):
        setup_medcat_processor()
        self.client = TestClient(app)

    def testLiveness(self):
        response = self.client.get(self.ENDPOINT_HEALTH_LIVE)
        self.assertEqual(response.status_code, 200)

    def testReadinessIsOk(self):
        response = self.client.get(self.ENDPOINT_HEALTH_READY)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data, {"status": "UP", "checks": [{"name": "MedCAT", "status": "UP"}]})

    def testReadinessIsNotOk(self):
        app.dependency_overrides[get_medcat_processor] = override_processor

        response = self.client.get(self.ENDPOINT_HEALTH_READY)

        app.dependency_overrides = {}

        self.assertEqual(response.status_code, 503)
        data = response.json()
        self.assertEqual(data, {"status": "DOWN", "checks": [{"name": "MedCAT", "status": "DOWN"}]})


if __name__ == "__main__":
    unittest.main()
