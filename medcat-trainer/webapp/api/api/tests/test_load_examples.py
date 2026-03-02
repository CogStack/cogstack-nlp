import os
import sys
import tempfile
from contextlib import contextmanager
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

from scripts.load_examples import _DEFAULT_PROVISIONING_PATH, main, run_provisioning  # noqa: E402
from scripts.provisioning import load_example_projects_config  # noqa: E402
from scripts.provisioning.model import (  # noqa: E402
    DatasetSpec,
    ModelPackSpec,
    ProjectSpec,
    ProvisioningConfig,
    ProvisioningProjectSpec,
)


def get_medcat_trainer_token(api_url: str, username: str = "admin", password: str = "admin") -> str:
    """Get a DRF token for the MedCAT trainer API."""
    resp = requests.post(
        f"{api_url}api-token-auth/",
        json={"username": username, "password": password},
    )
    resp.raise_for_status()
    return resp.json()["token"]


def get_project_list(api_url: str) -> list[dict]:
    """Return list of projects from project-annotate-entities."""
    token = get_medcat_trainer_token(api_url)
    resp = requests.get(
        f"{api_url}project-annotate-entities/",
        headers={"Authorization": f"Token {token}"},
    )
    resp.raise_for_status()
    return resp.json()["results"]


def make_mock_get(url_responses: dict[str, tuple[Path, bool]], real_get=requests.get):
    """
    Build a mock requests.get that serves file content for given URLs.
    url_responses: url -> (file_path, as_bytes). as_bytes True => .content, False => .text.
    """

    def mock_get(url, **kwargs):
        if url in url_responses:
            path, as_bytes = url_responses[url]
            resp = MagicMock()
            if as_bytes:
                resp.content = path.read_bytes()
            else:
                resp.text = path.read_text()
            resp.raise_for_status = lambda: None
            return resp
        return real_get(url, **kwargs)

    return mock_get


@contextmanager
def provisioning_temp_files():
    """Yield (model_pack_path, dataset_path) and unlink both on exit."""
    mp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    mp.close()
    ds = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    ds.close()
    try:
        yield mp.name, ds.name
    finally:
        Path(mp.name).unlink(missing_ok=True)
        Path(ds.name).unlink(missing_ok=True)


@contextmanager
def env_set(**kwargs: str):
    """Set os.environ keys; restore previous values on exit."""
    orig = {k: os.environ.get(k) for k in kwargs}
    try:
        for k, v in kwargs.items():
            os.environ[k] = v
        yield
    finally:
        for k in orig:
            prev = orig[k]
            if prev is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = prev


class LoadExamplesTestCase(TestCase):
    """Minimal test that load_examples.main can be imported and run."""

    def test_main_returns_when_load_examples_disabled(self):
        with env_set(LOAD_EXAMPLES="0"):
            main()


class LoadExamplesLiveAPITestCase(LiveServerTestCase):
    """
    Run the live server and call load_examples.main against it.
    Sets API_URL to self.live_server_url + '/api/' so the script hits this test's server.
    """

    def setUp(self):
        super().setUp()
        User.objects.create_user(username="admin", password="admin", is_staff=True)

    def test_main_calls_live_api(self):
        api_url = self.live_server_url + "/api/"
        config = load_example_projects_config(_DEFAULT_PROVISIONING_PATH)
        spec = config.projects[0]
        assert spec.model_pack is not None  # default YAML uses model pack
        mock_get = make_mock_get({
            spec.model_pack.url: (S3_MOCK_MODEL_PACK_ZIP, True),
            spec.dataset.url: (S3_MOCK_CARDIO_CSV, False),
        })

        with env_set(API_URL=api_url, LOAD_EXAMPLES="1"):
            with provisioning_temp_files() as (mp_path, ds_path):
                with patch("scripts.load_examples.requests.get", side_effect=mock_get):
                    main(initial_wait=0, model_pack_tmp_file=mp_path, dataset_tmp_file=ds_path)

        projects = get_project_list(api_url)
        self.assertIn(
            spec.project.name, [p["name"] for p in projects], f"Project list: {[p['name'] for p in projects]}"
        )


def _spec_with_model_pack(project_name: str, model_pack_url: str, dataset_url: str) -> ProvisioningProjectSpec:
    return ProvisioningProjectSpec(
        model_pack=ModelPackSpec(name="Test Model Pack", url=model_pack_url),
        dataset=DatasetSpec(name="TestDataset", url=dataset_url, description="Test dataset"),
        project=ProjectSpec(
            name=project_name,
            description="Created from unit test (model pack).",
            annotation_guideline_link="https://example.com/guide",
        ),
    )


def _spec_with_remote_service(project_name: str, model_service_url: str, dataset_url: str) -> ProvisioningProjectSpec:
    return ProvisioningProjectSpec(
        dataset=DatasetSpec(name="RemoteDataset", url=dataset_url, description="Dataset for remote model test"),
        project=ProjectSpec(
            name=project_name,
            description="Created from unit test (remote model service).",
            annotation_guideline_link="https://example.com/guide",
            use_model_service=True,
            model_service_url=model_service_url,
        ),
    )


class RunProvisioningWithConfigTestCase(LiveServerTestCase):
    """
    Tests that call run_provisioning() with a programmatic ProvisioningConfig
    (no YAML file). Use the live server and mock only external HTTP (S3/dataset URLs).
    """

    def setUp(self):
        super().setUp()
        User.objects.create_user(username="admin", password="admin", is_staff=True)

    def test_run_provisioning_with_model_pack_creates_project(self):
        """ProvisioningConfig with use_model_service=False: mock S3, assert project is created."""
        api_url = self.live_server_url + "/api/"
        project_name = "Unit Test Project (Model Pack)"
        model_pack_url = "https://trainer-example-data.s3.example.com/test_model.zip"
        dataset_url = "https://trainer-example-data.s3.example.com/test_ds.csv"

        config = ProvisioningConfig(projects=[_spec_with_model_pack(project_name, model_pack_url, dataset_url)])
        mock_get = make_mock_get({
            model_pack_url: (S3_MOCK_MODEL_PACK_ZIP, True),
            dataset_url: (S3_MOCK_CARDIO_CSV, False),
        })

        with provisioning_temp_files() as (mp_path, ds_path):
            with patch("scripts.load_examples.requests.get", side_effect=mock_get):
                run_provisioning(config, api_url, model_pack_tmp_file=mp_path, dataset_tmp_file=ds_path)

        projects = get_project_list(api_url)
        self.assertIn(project_name, [p["name"] for p in projects], f"Project list: {[p['name'] for p in projects]}")

    def test_run_provisioning_with_model_service_url_creates_project(self):
        """ProvisioningConfig with use_model_service=True: no model pack download, assert project is created."""
        api_url = self.live_server_url + "/api/"
        project_name = "Unit Test Project (Remote Model Service)"
        model_service_url = "http://medcat-service:8000"
        dataset_url = "https://trainer-example-data.s3.example.com/remote_ds.csv"

        config = ProvisioningConfig(projects=[_spec_with_remote_service(project_name, model_service_url, dataset_url)])
        mock_get = make_mock_get({dataset_url: (S3_MOCK_CARDIO_CSV, False)})

        with provisioning_temp_files() as (mp_path, ds_path):
            with patch("scripts.load_examples.requests.get", side_effect=mock_get):
                run_provisioning(config, api_url, model_pack_tmp_file=mp_path, dataset_tmp_file=ds_path)

        projects = get_project_list(api_url)
        self.assertIn(project_name, [p["name"] for p in projects], f"Project list: {[p['name'] for p in projects]}")
        created = next(p for p in projects if p["name"] == project_name)
        self.assertTrue(created.get("use_model_service"), "Project should have use_model_service=True")
        self.assertEqual(created.get("model_service_url"), model_service_url)
