import os
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

CDN_SWAGGER_JS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"
CDN_SWAGGER_CSS = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
CDN_REDOC_JS = "https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js"


class TestSwaggerDocs(unittest.TestCase):
    def _reload_app(self):
        """
        Reload the FastAPI app after env changes
        """
        # Clear cached imports so settings are re-evaluated
        for mod in list(sys.modules):
            if mod.startswith("medcat_service"):
                sys.modules.pop(mod)
        from medcat_service.main import app

        return app

    def tearDown(self):
        self._reload_app()

    @patch.dict(os.environ, {"APP_USE_CDN": "true"}, clear=False)
    def test_cdn_mode_serves_docs_from_cdn(self):
        app = self._reload_app()
        client = TestClient(app)

        docs = client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn(CDN_SWAGGER_JS, docs.text)
        self.assertIn(CDN_SWAGGER_CSS, docs.text)
        self.assertNotIn("/static/swagger-ui-bundle.js", docs.text)

        redoc = client.get("/redoc")
        self.assertEqual(redoc.status_code, 200)
        self.assertIn(CDN_REDOC_JS, redoc.text)
        self.assertNotIn("/static/redoc.standalone.js", redoc.text)

        static = client.get("/static/swagger-ui-bundle.js")
        self.assertEqual(static.status_code, 404)

    @patch.dict(os.environ, {"APP_USE_CDN": "false"}, clear=False)
    def test_self_hosted_mode_serves_docs_from_static(self):
        app = self._reload_app()
        client = TestClient(app)

        docs = client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn("/static/swagger-ui-bundle.js", docs.text)
        self.assertIn("/static/swagger-ui.css", docs.text)
        self.assertNotIn(CDN_SWAGGER_JS, docs.text)

        redoc = client.get("/redoc")
        self.assertEqual(redoc.status_code, 200)
        self.assertIn("/static/redoc.standalone.js", redoc.text)
        self.assertNotIn(CDN_REDOC_JS, redoc.text)

        static = client.get("/static/swagger-ui-bundle.js")
        self.assertEqual(static.status_code, 200)
        self.assertTrue(static.text.startswith("/*!"))

    @patch.dict(
        os.environ,
        {"APP_USE_CDN": "false", "APP_ROOT_PATH": "/medcat-service"},
        clear=False,
    )
    def test_self_hosted_mode_prefixes_urls_with_root_path(self):
        app = self._reload_app()
        client = TestClient(app)

        docs = client.get("/docs")
        self.assertEqual(docs.status_code, 200)
        self.assertIn("/medcat-service/static/swagger-ui-bundle.js", docs.text)
        self.assertIn("/medcat-service/openapi.json", docs.text)

        redoc = client.get("/redoc")
        self.assertEqual(redoc.status_code, 200)
        self.assertIn("/medcat-service/static/redoc.standalone.js", redoc.text)
        self.assertIn("/medcat-service/openapi.json", redoc.text)


if __name__ == "__main__":
    unittest.main()
