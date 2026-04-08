import os
import sys
import logging
from pathlib import Path

import pandas as pd
import requests
from time import sleep
import json

# Ensure the parent directory of the `scripts` package is on sys.path so that
# `from scripts....` imports work both when running as a module
# (python -m scripts.load_examples) and when executing the file directly
# (python /path/to/scripts/load_examples.py).
# SCRIPTS_PARENT = Path(__file__).resolve().parent.parent
# if str(SCRIPTS_PARENT) not in sys.path:
#     sys.path.insert(0, str(SCRIPTS_PARENT))

from scripts.provisioning import load_example_projects_config, ProvisioningConfig
from scripts.provisioning.model import ProvisioningProjectSpec

# Set up logging with prefix including process ID
pid = os.getpid()
logging.basicConfig(level=logging.INFO, format=f"[load_examples.py pid:{pid}] %(message)s")
logger = logging.getLogger(__name__)

# Default path to provisioning YAML (when LOAD_EXAMPLES_CONFIG is not set).
_DEFAULT_PROVISIONING_PATH = Path(__file__).resolve().parent / "provisioning" / "example_projects.provisioning.yaml"


def get_keycloak_access_token():
    logger.info("Getting Keycloak access token...")
    keycloak_url = os.environ.get("KEYCLOAK_URL", "http://keycloak.cogstack.localhost")
    realm = os.environ.get("KEYCLOAK_REALM", "cogstack-realm")
    client_id = os.environ.get("KEYCLOAK_CLIENT_ID", "cogstack-medcattrainer-frontend")
    username = os.environ.get("KEYCLOAK_USERNAME", "admin")
    password = os.environ.get("KEYCLOAK_PASSWORD", "admin")

    token_url = f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"

    data = {
        "grant_type": "password",
        "client_id": client_id,
        "username": username,
        "password": password,
        "scope": "openid profile email",
    }

    resp = requests.post(token_url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]


def wait_for_api_ready(api_url: str, max_wait_seconds: int = 300, interval: int = 5) -> None:
    """Poll api_url/health/ready/?format=json until 200 or max_wait_seconds. Exits with 1 on timeout."""
    health_ready_url = f"{api_url}health/ready/?format=json"
    waited = 0
    while waited < max_wait_seconds:
        try:
            if requests.get(health_ready_url).status_code == 200:
                logger.info("API health/ready returned 200")
                return
        except (ConnectionRefusedError, requests.exceptions.ConnectionError):
            pass
        logger.info(
            f"API {health_ready_url} not ready yet, retrying in {interval}s ({waited + interval}/{max_wait_seconds})")
        sleep(interval)
        waited += interval
    logger.error(f"FATAL - API ${health_ready_url} did not return 200 within {max_wait_seconds}s. Exiting.")
    sys.exit(1)


def get_headers(url: str) -> dict:
    """
    Return auth headers for the API: Bearer token (OIDC) if USE_OIDC is set,
    otherwise Token from DRF api-token-auth. Returns None if DRF auth fails.
    """
    use_oidc = os.environ.get("USE_OIDC")
    logger.debug("Checking for environment variable USE_OIDC...")
    if use_oidc is not None and use_oidc in "1":
        logger.info("Found environment variable USE_OIDC is set to truthy value. Will load data using JWT")
        token = get_keycloak_access_token()
        return {"Authorization": f"Bearer {token}"}
    logger.info("Getting DRF auth token ...")
    payload = {"username": "admin", "password": "admin"}
    resp = requests.post(f"{url}api-token-auth/", json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to get DRF auth token: {resp.status_code} {resp.text}")
    return {"Authorization": f"Token {json.loads(resp.text)['token']}"}


def run_provisioning(
    provisioning_config: ProvisioningConfig,
    api_url: str,
    model_pack_tmp_file: str = "/home/model_pack.zip",
    dataset_tmp_file: str = "/home/ds.csv",
) -> None:
    """
    Wait for the API, then create projects from provisioning_config.
    Exits with code 1 on max retries or API not ready. Unit tests can call this
    with a ProvisioningConfig instance instead of reading from file.
    """
    wait_for_api_ready(api_url)

    logger.info("Checking for default projects / datasets / CDBs / Vocabs")
    max_retries = 60  # 60 retries = 5 minutes
    retry_count = 0
    while retry_count < max_retries:
        try:
            headers = get_headers(api_url)

            resp_model_packs = requests.get(f"{api_url}modelpacks/", headers=headers)
            resp_ds = requests.get(f"{api_url}datasets/", headers=headers)
            resp_projs = requests.get(f"{api_url}project-annotate-entities/", headers=headers)
            all_resps = [resp_model_packs, resp_ds, resp_projs]
            codes = [r.status_code == 200 for r in all_resps]

            if not (all(codes) and all(len(r.text) > 0 and json.loads(r.text)["count"] == 0 for r in all_resps)):
                logger.info(
                    "Found at least one object amongst model packs, datasets & projects. Skipping example creation"
                )
                break

            logger.info("Found No Objects. Populating Example: Model Pack, Dataset and Project...")
            for spec in provisioning_config.projects:
                if not spec.project.use_model_service:
                    logger.info(f"Downloading example model pack from {spec.model_pack.url}")
                    model_pack_file = requests.get(spec.model_pack.url)
                    with open(model_pack_tmp_file, "wb") as f:
                        f.write(model_pack_file.content)

                logger.info(f"Downloading example dataset from {spec.dataset.url}")
                ds = requests.get(spec.dataset.url)
                with open(dataset_tmp_file, "w") as f:
                    f.write(ds.text)

                ds_dict = pd.read_csv(dataset_tmp_file).loc[:, ["name", "text"]].to_dict()
                create_example_project(api_url, headers, spec, model_pack_tmp_file, ds_dict)

                if not spec.project.use_model_service:
                    os.remove(model_pack_tmp_file)
                os.remove(dataset_tmp_file)
            break

        except ConnectionRefusedError:
            retry_count += 1
            if retry_count < max_retries:
                logger.info(
                    f"Loading examples - Connection refused to {api_url}. Retrying in 5 seconds... (attempt {retry_count}/{max_retries})"
                )
                sleep(5)
            continue
        except requests.exceptions.ConnectionError:
            retry_count += 1
            if retry_count < max_retries:
                logger.info(
                    f"Loading examples - Connection error to {api_url}. Retrying in 5 seconds... (attempt {retry_count}/{max_retries})"
                )
                sleep(5)
            continue

    if retry_count >= max_retries:
        logger.error(f"FATAL - Error loading examples. Max retries ({max_retries}) reached. Exiting with code 1.")
        sys.exit(1)
    logger.info("Successfully loaded examples")


def create_example_project(url, headers, spec: ProvisioningProjectSpec, model_pack_tmp_file, ds_dict):
    """Create dataset and project. Branch only on spec.project.use_model_service."""
    if not spec.project.use_model_service:
        logger.info("Creating Model Pack / Dataset / Project in the Trainer")
        res_model_pack_mk = requests.post(
            f"{url}modelpacks/",
            headers=headers,
            data={"name": spec.model_pack.name},
            files={"model_pack": open(model_pack_tmp_file, "rb")},
        )
        model_pack_id = json.loads(res_model_pack_mk.text)["id"]
    else:
        logger.info("Creating Dataset / Project (remote model service) in the Trainer")
        model_pack_id = None

    payload = {
        "dataset_name": spec.dataset.name,
        "dataset": ds_dict,
        "description": spec.dataset.description,
    }
    resp = requests.post(f"{url}create-dataset/", json=payload, headers=headers)
    ds_id = json.loads(resp.text)["dataset_id"]

    user_id = json.loads(requests.get(f"{url}users/", headers=headers).text)["results"][0]["id"]

    payload = {
        "name": spec.project.name,
        "description": spec.project.description,
        "cuis": "",
        "annotation_guideline_link": spec.project.annotation_guideline_link,
        "dataset": ds_id,
        "members": [user_id],
    }
    if not spec.project.use_model_service:
        payload["model_pack"] = model_pack_id
    else:
        payload["use_model_service"] = True
        payload["model_service_url"] = spec.project.model_service_url

    requests.post(f"{url}project-annotate-entities/", json=payload, headers=headers)
    logger.info("Successfully created the example project")


def main(
    port: int = 8001,
    model_pack_tmp_file: str = "/home/model_pack.zip",
    dataset_tmp_file: str = "/home/ds.csv",
) -> None:
    """Entrypoint: check LOAD_EXAMPLES, load config from file, then run_provisioning."""
    logger.info("Checking for environment variable LOAD_EXAMPLES...")
    val = os.environ.get("LOAD_EXAMPLES")
    if val is not None and val not in ("1", "true", "t", "y"):
        logger.info("Found Env Var LOAD_EXAMPLES is False, not loading example data, cdb, vocab and project")
        return

    config_path = Path(os.environ.get("PROVISIONING_CONFIG_PATH") or _DEFAULT_PROVISIONING_PATH)
    if not config_path.is_file():
        logger.error(
            f"FATAL - Provisioning config not found: {config_path}. Set PROVISIONING_CONFIG_PATH or add the YAML file."
        )
        sys.exit(1)
    provisioning_config = load_example_projects_config(config_path)
    logger.info(f"Loaded provisioning config from {config_path} ({len(provisioning_config.projects)} project(s))")

    api_url = os.environ.get("API_URL") or f"http://localhost:{port}/api/"
    logger.info("Found Env Var LOAD_EXAMPLES, waiting for API to be ready...")

    run_provisioning(provisioning_config, api_url, model_pack_tmp_file, dataset_tmp_file)


if __name__ == "__main__":
    main()
