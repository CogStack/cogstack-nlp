import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import User
from django.test import LiveServerTestCase, TestCase

# Allow importing webapp/scripts
WEBAPP_DIR = Path(__file__).resolve().parents[2].parent  # api/tests -> api -> api -> webapp
if str(WEBAPP_DIR) not in sys.path:
    sys.path.insert(0, str(WEBAPP_DIR))

# Paths for mocking S3 in tests
MEDCAT_TRAINER_ROOT = Path(__file__).resolve().parents[4]  # .../api/api/tests -> medcat-trainer
S3_MOCK_CARDIO_CSV = MEDCAT_TRAINER_ROOT / "notebook_docs" / "example_data" / "cardio.csv"
S3_MOCK_MODEL_PACK_ZIP = (
    MEDCAT_TRAINER_ROOT.parent / "medcat-service" / "models" / "examples" / "example-medcat-v2-model-pack.zip"
)

from scripts.load_examples import (  # noqa: E402
    EXAMPLE_DATASET_URL,
    EXAMPLE_MODEL_PACK_URL,
    EXAMPLE_PROJECT_NAME,
    main,
)


def get_medcat_trainer_token(api_url: str, username: str = "admin", password: str = "admin") -> str:
    """Get a DRF token for the MedCAT trainer API."""
    resp = requests.post(
        f"{api_url}api-token-auth/",
        json={"username": username, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["token"]


class LoadExamplesTestCase(TestCase):
    """Minimal test that load_examples.main can be imported and run."""

    def test_main_returns_when_load_examples_disabled(self):
        import os

        orig = os.environ.get("LOAD_EXAMPLES")
        os.environ["LOAD_EXAMPLES"] = "0"
        try:
            main()
        finally:
            if orig is None:
                os.environ.pop("LOAD_EXAMPLES", None)
            else:
                os.environ["LOAD_EXAMPLES"] = orig


class LoadExamplesLiveAPITestCase(LiveServerTestCase):
    """
    Run the live server and call load_examples.main against it.
    Sets API_URL to self.live_server_url + '/api/' so the script hits this test's server.
    """

    def setUp(self):
        super().setUp()
        User.objects.create_user(username="admin", password="admin", is_staff=True)

    def test_main_calls_live_api(self):
        import os

        api_url = self.live_server_url + "/api/"
        real_get = requests.get

        def mock_get(url, **kwargs):
            if url == EXAMPLE_MODEL_PACK_URL:
                resp = MagicMock()
                resp.content = S3_MOCK_MODEL_PACK_ZIP.read_bytes()
                resp.raise_for_status = lambda: None
                return resp
            if url == EXAMPLE_DATASET_URL:
                resp = MagicMock()
                resp.text = S3_MOCK_CARDIO_CSV.read_text()
                resp.raise_for_status = lambda: None
                return resp
            return real_get(url, **kwargs)

        with (
            tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as mp,
            tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as ds,
        ):
            mp.close()
            ds.close()
            try:
                orig_url = os.environ.get("API_URL")
                orig_load = os.environ.get("LOAD_EXAMPLES")
                os.environ["API_URL"] = api_url
                os.environ["LOAD_EXAMPLES"] = "1"
                try:
                    with patch("scripts.load_examples.requests.get", side_effect=mock_get):
                        main(
                            initial_wait=0,
                            model_pack_tmp_file=mp.name,
                            dataset_tmp_file=ds.name,
                        )
                finally:
                    if orig_url is None:
                        os.environ.pop("API_URL", None)
                    else:
                        os.environ["API_URL"] = orig_url
                    if orig_load is None:
                        os.environ.pop("LOAD_EXAMPLES", None)
                    else:
                        os.environ["LOAD_EXAMPLES"] = orig_load
            finally:
                Path(mp.name).unlink(missing_ok=True)
                Path(ds.name).unlink(missing_ok=True)

        # Assert the project was created: GET project-annotate-entities and check for the example project
        token = get_medcat_trainer_token(api_url)
        proj_resp = requests.get(
            f"{api_url}project-annotate-entities/",
            headers={"Authorization": f"Token {token}"},
        )
        proj_resp.raise_for_status()
        project_names = [p["name"] for p in proj_resp.json()["results"]]

        expected = EXAMPLE_PROJECT_NAME
        actual = next((n for n in project_names if n == expected), None)
        self.assertEqual(expected, actual, f"Project list: {project_names}")
