import sys
import unittest

from fastapi.testclient import TestClient

from medcat_service.config import ObservabilitySettings, Settings
from medcat_service.main import app, configure_observability
from medcat_service.test.common import setup_medcat_processor


class TestAdminApi(unittest.TestCase):
    ENDPOINT_INFO_ENDPOINT = "/api/info"
    METRICS_ENDPOINT = "/metrics"

    def _reload_app(self):
        """
        Reload the FastAPI app after env changes
        Used to fix this error when trying to change the observability
        "Cannot add middleware after an application has started"
        """
        # Clear cached imports so settings are re-evaluated
        for mod in list(sys.modules):
            if mod.startswith("medcat_service"):
                sys.modules.pop(mod)
        from medcat_service.main import app

        return app

    def setUp(self):
        setup_medcat_processor()
        self.client = TestClient(app)

    def testGetInfo(self):
        response = self.client.get(self.ENDPOINT_INFO_ENDPOINT)
        self.assertEqual(response.status_code, 200)

    def test_get_metrics_enabled(self):
        settings = Settings(observability=ObservabilitySettings(enable_metrics=True))
        app = self._reload_app()
        configure_observability(settings, app)
        client = TestClient(app)

        response = client.get(self.METRICS_ENDPOINT)
        self.assertEqual(response.status_code, 200)
        self.maxDiff = None
        self.assertTrue("http_requests_total" in response.text)

    def test_get_metrics_disabled(self):
        app = self._reload_app()
        settings = Settings(observability=ObservabilitySettings(enable_metrics=False))
        configure_observability(settings, app)
        self.client = TestClient(app)

        response = self.client.get(self.METRICS_ENDPOINT)
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
