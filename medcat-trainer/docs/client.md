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
```

## Project groups

Create one shared configuration and, by default, one annotation project per
annotator (named `<group name> - <username>`):

```python
group = session.create_project_group(
    name="Stroke IAA",
    description="Inter-annotator agreement campaign",
    annotators=[annotator],
    administrators=[],  # optional; the authenticated user is always an admin
    dataset=ds,
    modelpack=model_packs[0],
    create_associated_projects=True,
)

groups = session.get_project_groups()
```

Users, datasets, and model packs may be passed as wrapper objects or resolved
by name. Supply **either** `modelpack` **or** `concept_db` + `vocab`, not both.
With `create_associated_projects=True` (the default), at least one annotator is
required.

## Common methods

- `create_project(...)`
- `create_project_group(...)`
- `get_project_groups()`
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

## Notes

- `create_project` and `create_project_group` expect **either** `modelpack`
  **or** `concept_db + vocab`.
- Wrapper objects (`MCTDataset`, `MCTConceptDB`, etc.) can often be passed by
  object or resolved by name.
- See [Project Groups](project_group_admin.md) for the UI workflow these client
  calls mirror.
