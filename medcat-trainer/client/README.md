
---

# MedCATtrainer Client

A Python client for interacting with a MedCATTrainer web application instance. This package allows you to manage datasets, concept databases, vocabularies, model packs, users, projects, and more via Python code or the command line.

## Features

- Manage datasets, concept databases, vocabularies, and model packs
- Create and manage users and projects
- Retrieve and upload project annotations
- Command-line interface (CLI) for automation

## Installation

```sh
pip install mctclient
```

Or, if installing from source:

```sh
cd client
python -m build
pip install dist/*.whl
```

## Python Usage

```sh
export MCTRAINER_USERNAME=<username>
export MCTRAINER_PASSWORD=<password>
```

```python
from mctclient import MedCATTrainerSession, KeycloakSettings, MCTDataset, MCTConceptDB, MCTVocab, MCTModelPack, MCTMetaTask, MCTRelTask, MCTUser, MCTProject

# Connect to your MedCATTrainer instance
session = MedCATTrainerSession(server="http://localhost:8001")

# List all projects
projects = session.get_projects()
for project in projects:
    print(project)

# Create a new dataset
dataset = session.create_dataset(name="My Dataset", dataset_file="path/to/data.csv")

# Create a new user
user = session.create_user(username="newuser", password="password123")

# Create a new project
project = session.create_project(
    name="My Project",
    description="A new annotation project",
    members=[user],
    dataset=dataset
)
```

## Authentication

### OIDC / Keycloak (optional)

You can pass a `KeycloakSettings` object to use OIDC Bearer auth. Any missing
fields fall back to environment variables
(`KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_USERNAME`, `KEYCLOAK_PASSWORD`)
and then the same defaults as `webapp/scripts/load_examples.py`.

```python
from mctclient import MedCATTrainerSession, KeycloakSettings

session = MedCATTrainerSession(
    server="http://localhost:8001",
    use_oidc=True,
    keycloak_settings=KeycloakSettings(
        keycloak_url="http://keycloak.cogstack.localhost",
        realm="cogstack-realm",
        client_id="cogstack-medcattrainer-frontend",
        username="admin",
        password="admin",
    ),
)
```

### MedCATTrainerSession Methods

- `create_project(name, description, members, dataset, cuis=[], cuis_file=None, concept_db=None, vocab=None, cdb_search_filter=None, modelpack=None, meta_tasks=[], rel_tasks=[])`
- `create_dataset(name, dataset_file)`
- `create_user(username, password)`
- `create_medcat_model(cdb, vocab)`
- `create_medcat_model_pack(model_pack)`
- `get_users()`
- `get_models()`
- `get_model_packs()`
- `get_meta_tasks()`
- `get_rel_tasks()`
- `get_projects()`
- `get_datasets()`
- `get_project_annos(projects)`

Each method returns the corresponding object or a list of objects.

## License

This project is licensed under the Apache 2.0 License.

## Developer Instructions

### Local dev setup (uv)

From the repo root:

```sh
cd medcat-trainer/client
uv venv
source .venv/bin/activate
uv pip install -e .
```

### Run unit tests

```sh
cd medcat-trainer/client
python -m unittest discover -s tests -p "test_*.py" -v
```

### Run integration test (real server)

```sh
cd medcat-trainer/client
export MCTRAINER_SERVER="http://localhost:8000"
export MCTRAINER_USERNAME="<username>"
export MCTRAINER_PASSWORD="<password>"
export MCTRAINER_EXPECTED_USERS="admin,alice,bob"  # optional
python -m unittest tests.integration.test_integration_mctclient -v
```

Optional: use OIDC / Keycloak Bearer token auth:

```sh
export MCTRAINER_USE_OIDC=1
export KEYCLOAK_URL="http://keycloak.cogstack.localhost"
export KEYCLOAK_REALM="cogstack"
export KEYCLOAK_CLIENT_ID="cogstack-medcattrainer-frontend"
# If set, the client will use client-credentials grant; otherwise password grant.
export KEYCLOAK_CLIENT_SECRET="<client_secret>"  # optional
export KEYCLOAK_USERNAME="<keycloak_username>"   # used if no client_secret
export KEYCLOAK_PASSWORD="<keycloak_password>"   # used if no client_secret
python -m unittest tests.integration.test_integration_mctclient -v
```

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.


