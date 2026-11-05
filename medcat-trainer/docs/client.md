# MedCATtrainer Python Client

`mctclient` provides a Python wrapper over MedCATtrainer REST APIs for
automation and batch workflows.

## Install

```bash
pip install mctclient
```

## Authenticate

The client uses username/password API-token auth.

```bash
export MCTRAINER_USERNAME=<username>
export MCTRAINER_PASSWORD=<password>
```

## Minimal example

```python
from mctclient import (
    MedCATTrainerSession,
    MCTDataset,
    MCTConceptDB,
    MCTVocab,
    MCTModelPack,
    MCTUser,
)

session = MedCATTrainerSession(server="http://localhost:8001")

# Inspect existing resources
projects = session.get_projects()
model_packs = session.get_model_packs()

# Upload dataset
ds = session.create_dataset(name="Demo Dataset", dataset_file="data.csv")

# Create user (optional)
annotator = session.create_user(username="annotator_1", password="strong-password")

# Create project using model pack OR cdb+vocab
project = session.create_project(
    name="Demo Project",
    description="Automated setup",
    members=[annotator],
    dataset=ds,
    modelpack=model_packs[0],
)

# Run the project model over the dataset. Background runs need the
# MedCATTrainer process_tasks worker. background=False runs inside the request.
run = session.run_model(project, wait=True, timeout=3600)
print(run.status, run.prepared_docs, run.dataset_len)
```

## Common methods

- `create_project(...)`
- `create_dataset(name, dataset_file)`
- `create_user(username, password)`
- `create_medcat_model(cdb, vocab)`
- `create_medcat_model_pack(model_pack)`
- `get_users()`
- `get_models()`
- `get_concept_dbs()`
- `get_vocabs()`
- `get_model_packs()`
- `get_meta_tasks()`
- `get_rel_tasks()`
- `get_projects()`
- `get_datasets()`
- `get_project_annos(projects)`
- `upload_projects_export(...)`
- `run_model(project, background=True, wait=False, timeout=None)`
- `get_model_run(project)`
- `stop_model_run(project)`
- `get_model_runs()`

## Notes

- `create_project` expects **either** `modelpack` **or** `concept_db + vocab`.
- Wrapper objects (`MCTDataset`, `MCTConceptDB`, etc.) can often be passed by
  object or resolved by name.
- `run_model` accepts a project object, id, or unique name. It runs the
  configured model over dataset documents that are still unprepared.
  Submitted documents, documents that already have annotations, and documents
  that have already been prepared are left unchanged. `wait=True` polls until
  the background worker finishes.
