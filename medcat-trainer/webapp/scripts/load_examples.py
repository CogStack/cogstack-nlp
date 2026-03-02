import os
import sys
import logging

import pandas as pd
import requests
from time import sleep
import json

# Set up logging with prefix including process ID
pid = os.getpid()
logging.basicConfig(
    level=logging.INFO,
    format=f'[load_examples.py pid:{pid}] %(message)s'
)
logger = logging.getLogger(__name__)

# Example data URLs (S3)
EXAMPLE_MODEL_PACK_URL = 'https://trainer-example-data.s3.eu-north-1.amazonaws.com/medcat2_model_pack_0f66077250cc2957.zip'
EXAMPLE_DATASET_URL = 'https://trainer-example-data.s3.eu-north-1.amazonaws.com/dr_notes.csv'

# Example project defaults for create_example_project
EXAMPLE_DATASET_NAME = 'M-IV_NeuroNotes'
EXAMPLE_PROJECT_NAME = 'Example Project - Model Pack (Diseases / Symptoms / Findings)'
EXAMPLE_MODEL_PACK_NAME = 'Example Model Pack'
EXAMPLE_DATASET_DESCRIPTION = 'Clinical texts from MIMIC-IV'
EXAMPLE_PROJECT_DESCRIPTION = (
    'Example projects using example psychiatric clinical notes from '
    'https://www.mtsamples.com/'
)
EXAMPLE_ANNOTATION_GUIDELINE_LINK = (
    'https://docs.google.com/document/d/1xxelBOYbyVzJ7vLlztP2q1Kw9F5Vr1pRwblgrXPS7QM/edit?usp=sharing'
)


def get_keycloak_access_token():
    logger.info('Getting Keycloak access token...')
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
        "scope": "openid profile email"
    }

    resp = requests.post(token_url, data=data)
    resp.raise_for_status()
    return resp.json()["access_token"]


def wait_for_api_ready(api_url: str, max_wait_seconds: int = 300, interval: int = 5) -> None:
    """Poll api_url/health/ready/?format=json until 200 or max_wait_seconds. Exits with 1 on timeout."""
    health_ready_url = f'{api_url}health/ready/?format=json'
    waited = 0
    while waited < max_wait_seconds:
        try:
            if requests.get(health_ready_url).status_code == 200:
                logger.info('API health/ready returned 200')
                return
        except (ConnectionRefusedError, requests.exceptions.ConnectionError):
            pass
        logger.info(f'API not ready yet, retrying in {interval}s ({waited + interval}/{max_wait_seconds})')
        sleep(interval)
        waited += interval
    logger.error(f'FATAL - API ${health_ready_url} did not return 200 within {max_wait_seconds}s. Exiting.')
    sys.exit(1)


def get_headers(url: str) -> dict:
    """
    Return auth headers for the API: Bearer token (OIDC) if USE_OIDC is set,
    otherwise Token from DRF api-token-auth. Returns None if DRF auth fails.
    """
    use_oidc = os.environ.get('USE_OIDC')
    logger.info('Checking for environment variable USE_OIDC...')
    if use_oidc is not None and use_oidc in '1':
        logger.info('Found environment variable USE_OIDC is set to truthy value. Will load data using JWT')
        token = get_keycloak_access_token()
        return {'Authorization': f'Bearer {token}'}
    logger.info('Getting DRF auth token ...')
    payload = {"username": "admin", "password": "admin"}
    resp = requests.post(f"{url}api-token-auth/", json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to get DRF auth token: {resp.status_code} {resp.text}")
    return {'Authorization': f'Token {json.loads(resp.text)["token"]}'}


def main(port=8001,
         model_pack_tmp_file='/home/model_pack.zip',
         dataset_tmp_file='/home/ds.csv',
         initial_wait=15):

    logger.info('Checking for environment variable LOAD_EXAMPLES...')
    val = os.environ.get('LOAD_EXAMPLES')
    if val is not None and val not in ('1', 'true', 't', 'y'):
        logger.info('Found Env Var LOAD_EXAMPLES is False, not loading example data, cdb, vocab and project')
        return

    logger.info('Found Env Var LOAD_EXAMPLES, waiting for API to be ready...')
    URL = os.environ.get('API_URL', f'http://localhost:{port}/api/')
    sleep(initial_wait)
    wait_for_api_ready(URL)

    logger.info('Checking for default projects / datasets / CDBs / Vocabs')
    max_retries = 60  # 60 retries = 5 minutes
    retry_count = 0
    while retry_count < max_retries:
        try:
            headers = get_headers(URL)

            # check concepts DB, vocab, datasets and projects are empty
            resp_model_packs = requests.get(f'{URL}modelpacks/', headers=headers)
            resp_ds = requests.get(f'{URL}datasets/', headers=headers)
            resp_projs = requests.get(f'{URL}project-annotate-entities/', headers=headers)
            all_resps = [resp_model_packs, resp_ds, resp_projs]

            codes = [r.status_code == 200 for r in all_resps]

            if not(all(codes) and all(len(r.text) > 0 and json.loads(r.text)['count'] == 0 for r in all_resps)):
                logger.info('Found at least one object amongst model packs, datasets & projects. Skipping example creation')
                break
            else:
                logger.info("Found No Objects. Populating Example: Model Pack, Dataset and Project...")
                # download example model pack and dataset
                logger.info(f"Downloading example model pack from {EXAMPLE_MODEL_PACK_URL}")
                model_pack_file = requests.get(EXAMPLE_MODEL_PACK_URL)
                with open(model_pack_tmp_file, 'wb') as f:
                    f.write(model_pack_file.content)

                logger.info(f"Downloading example dataset from {EXAMPLE_DATASET_URL}")
                ds = requests.get(EXAMPLE_DATASET_URL)
                with open(dataset_tmp_file, 'w') as f:
                    f.write(ds.text)

                ds_dict = pd.read_csv(dataset_tmp_file).loc[:, ['name', 'text']].to_dict()
                create_example_project(
                    URL, headers, model_pack_tmp_file,
                    EXAMPLE_DATASET_NAME, ds_dict, EXAMPLE_PROJECT_NAME,
                )

                # clean up temp files
                os.remove(model_pack_tmp_file)
                os.remove(dataset_tmp_file)
                break

        except ConnectionRefusedError:
            retry_count += 1
            if retry_count < max_retries:
                logger.info(
                    f'Loading examples - Connection refused to {URL}. Retrying in 5 seconds... (attempt {retry_count}/{max_retries})')
                sleep(5)
            continue
        except requests.exceptions.ConnectionError:
            retry_count += 1
            if retry_count < max_retries:
                logger.info(
                    f'Loading examples - Connection error to {URL}. Retrying in 5 seconds... (attempt {retry_count}/{max_retries})')
                sleep(5)
            continue

    # If we exited the loop due to max retries, exit with error code
    if retry_count >= max_retries:
        logger.error(f'FATAL - Error loading examples. Max retries ({max_retries}) reached. Exiting with code 1.')
        sys.exit(1)
    logger.info('Successfully loaded examples')


def create_example_project(url, headers, model_pack, ds_name, ds_dict, project_name):
    logger.info('Creating Model Pack / Dataset / Project in the Trainer')
    res_model_pack_mk = requests.post(
        f'{url}modelpacks/', headers=headers,
        data={'name': EXAMPLE_MODEL_PACK_NAME},
        files={'model_pack': open(model_pack, 'rb')},
    )
    model_pack_id = json.loads(res_model_pack_mk.text)['id']

    # Upload the dataset
    payload = {
        'dataset_name': ds_name,
        'dataset': ds_dict,
        'description': EXAMPLE_DATASET_DESCRIPTION,
    }
    resp = requests.post(f'{url}create-dataset/', json=payload, headers=headers)
    ds_id = json.loads(resp.text)['dataset_id']

    user_id = json.loads(requests.get(f'{url}users/', headers=headers).text)['results'][0]['id']

    # Create the project
    payload = {
        'name': project_name,
        'description': EXAMPLE_PROJECT_DESCRIPTION,
        'cuis': '',
        'annotation_guideline_link': EXAMPLE_ANNOTATION_GUIDELINE_LINK,
        'dataset': ds_id,
        'model_pack': model_pack_id,
        'members': [user_id],
    }
    requests.post(f'{url}project-annotate-entities/', json=payload, headers=headers)
    logger.info('Successfully created the example project')


if __name__ == '__main__':
    main()
