import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
import requests
from django.contrib.auth.models import User
from django.test import LiveServerTestCase, TestCase

# Allow importing webapp/scripts
WEBAPP_DIR = Path(__file__).resolve().parents[2].parent  # api/tests -> api -> api -> webapp
if str(WEBAPP_DIR) not in sys.path:
    sys.path.insert(0, str(WEBAPP_DIR))

# GitHub permalinks for test data (raw content). During CI this test runs in a docker container, so doesnt have access to these files.
CARDIO_CSV_URL = "https://raw.githubusercontent.com/CogStack/cogstack-nlp/051edf6cbd94fa83436fab807aff49d78dd68e59/medcat-trainer/notebook_docs/example_data/cardio.csv"
MODEL_PACK_ZIP_URL = "https://raw.githubusercontent.com/CogStack/cogstack-nlp/051edf6cbd94fa83436fab807aff49d78dd68e59/medcat-service/models/examples/example-medcat-v2-model-pack.zip"

from scripts.load_examples import main, run_provisioning  # noqa: E402
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
        # Use a temp YAML that points at GitHub permalinks so main() downloads without mocking
        config = ProvisioningConfig(
            projects=[
                ProvisioningProjectSpec(
                    model_pack=ModelPackSpec(name="Example Model Pack", url=MODEL_PACK_ZIP_URL),
                    dataset=DatasetSpec(
                        name="M-IV_NeuroNotes",
                        url=CARDIO_CSV_URL,
                        description="Clinical texts from MIMIC-IV",
                    ),
                    project=ProjectSpec(
                        name="Example Project - Model Pack (Diseases / Symptoms / Findings)",
                        description="Example project",
                        annotation_guideline_link="https://example.com/guide",
                    ),
                ),
            ],
        )
        spec = config.projects[0]
        assert spec.model_pack is not None
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            # Write YAML with GitHub permalink URLs (camelCase keys)
            f.write("projects:\n")
            f.write("  - modelPack:\n")
            f.write(f'      name: "{spec.model_pack.name}"\n')
            f.write(f'      url: "{MODEL_PACK_ZIP_URL}"\n')
            f.write("    dataset:\n")
            f.write(f'      name: "{spec.dataset.name}"\n')
            f.write(f'      url: "{CARDIO_CSV_URL}"\n')
            f.write(f'      description: "{spec.dataset.description}"\n')
            f.write("    project:\n")
            f.write(f'      name: "{spec.project.name}"\n')
            f.write(f'      description: "{spec.project.description}"\n')
            f.write(f'      annotationGuidelineLink: "{spec.project.annotation_guideline_link}"\n')
            config_path = f.name
        try:
            with env_set(API_URL=api_url, LOAD_EXAMPLES="1", PROVISIONING_CONFIG_PATH=config_path):
                with provisioning_temp_files() as (mp_path, ds_path):
                    main(model_pack_tmp_file=mp_path, dataset_tmp_file=ds_path)

            projects = get_project_list(api_url)
            self.assertIn(
                spec.project.name,
                [p["name"] for p in projects],
                f"Project list: {[p['name'] for p in projects]}",
            )
        finally:
            Path(config_path).unlink(missing_ok=True)


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
        """ProvisioningConfig with model pack: download from GitHub permalinks, assert project is created."""
        api_url = self.live_server_url + "/api/"
        project_name = "Unit Test Project (Model Pack)"

        config = ProvisioningConfig(projects=[_spec_with_model_pack(project_name, MODEL_PACK_ZIP_URL, CARDIO_CSV_URL)])
        with provisioning_temp_files() as (mp_path, ds_path):
            run_provisioning(config, api_url, model_pack_tmp_file=mp_path, dataset_tmp_file=ds_path)

        projects = get_project_list(api_url)
        self.assertIn(project_name, [p["name"] for p in projects], f"Project list: {[p['name'] for p in projects]}")

    def test_run_provisioning_with_model_service_url_creates_project(self):
        """ProvisioningConfig with use_model_service=True: dataset from GitHub permalink, assert project is created."""
        api_url = self.live_server_url + "/api/"
        project_name = "Unit Test Project (Remote Model Service)"
        model_service_url = "http://medcat-service:8000"

        config = ProvisioningConfig(
            projects=[_spec_with_remote_service(project_name, model_service_url, CARDIO_CSV_URL)]
        )
        with provisioning_temp_files() as (mp_path, ds_path):
            run_provisioning(config, api_url, model_pack_tmp_file=mp_path, dataset_tmp_file=ds_path)

        projects = get_project_list(api_url)
        self.assertIn(project_name, [p["name"] for p in projects], f"Project list: {[p['name'] for p in projects]}")
        created = next(p for p in projects if p["name"] == project_name)
        self.assertTrue(created.get("use_model_service"), "Project should have use_model_service=True")
        self.assertEqual(created.get("model_service_url"), model_service_url)
