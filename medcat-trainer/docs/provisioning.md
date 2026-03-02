# Provisioning guide

On startup, MedCAT Trainer can create example projects, datasets, and (optionally) model packs from a YAML config. The script `load_examples.py` runs after the API is up and only runs if the API has no existing projects/datasets/model packs.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `LOAD_EXAMPLES` | Yes (to enable) | Set to `1`, `true`, `t`, `y` to run provisioning. Any other value or unset skips loading. |
| `API_URL` | No | Base API URL (e.g. `http://localhost:8001/api/`). Default: `http://localhost:8001/api/`. |
| `PROVISIONING_CONFIG_PATH` | No | Path to the provisioning YAML file. Default: `scripts/provisioning/example_projects.provisioning.yaml`. |

When using OIDC auth, set `USE_OIDC` to a truthy value; the script will use Keycloak (`KEYCLOAK_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_USERNAME`, `KEYCLOAK_PASSWORD`) for the bearer token instead of DRF token auth.

## YAML format

Top-level key is `projects`, a list of project specs. Each item is **either** a model-pack project **or** a remote-model-service project.

### Option 1: Model pack (upload a .zip)

```yaml
projects:
  - modelPack:
      name: "Example Model Pack"
      url: "https://example.com/path/to/model_pack.zip"
    dataset:
      name: "My Dataset"
      url: "https://example.com/dataset.csv"
      description: "Short description of the dataset"
    project:
      name: "Example Project"
      description: "Project description"
      annotationGuidelineLink: "https://example.com/guidelines"
```

- `modelPack`: `name` (display name), `url` (URL of a .zip to download and upload to the API).
- `dataset`: `name`, `url` (CSV URL), `description`.
- `project`: `name`, `description`, `annotationGuidelineLink`.

### Option 2: Remote MedCAT service (no model pack)

Use a remote MedCAT service API for document processing instead of uploading a model pack. Set `useModelService` and `modelServiceUrl` on the **project** object; do **not** set `modelPack` on the spec.

```yaml
projects:
  - dataset:
      name: "My Dataset"
      url: "https://example.com/dataset.csv"
      description: "Short description"
    project:
      name: "Example Project - Remote"
      description: "Uses remote MedCAT service"
      annotationGuidelineLink: "https://example.com/guidelines"
      useModelService: true
      modelServiceUrl: "http://medcat-service:8000"
```

- Under `project`: `useModelService`: `true`, `modelServiceUrl`: base URL of the MedCAT service API (e.g. `http://medcat-service:8000`).
- Do **not** set top-level `modelPack` when using `useModelService: true`.

YAML keys are **camelCase** (e.g. `modelPack`, `annotationGuidelineLink`, `useModelService`, `modelServiceUrl`).
