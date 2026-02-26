# Annotation Project Creation and Management

MedCATtrainer supports two management surfaces:

- **Project Admin UI** (`/project-admin`) for most project operations.
- **Django Admin** (`/admin`) for advanced actions and low-level data management.

## Create a project (Project Admin UI)

1. Open `/project-admin`.
2. Go to the **Projects** tab and select **Create New Project**.
3. Fill in:
   - **Basic information** (name, dataset, description, guideline link)
   - **Model configuration**
   - **Annotation settings**
   - **Concept filter (optional)**
   - **Members**
4. Save.

### Model configuration options

Pick exactly one of:

1. **Model Pack** (recommended), or
2. **Concept DB + Vocabulary** pair.

You may also enable:

- **Remote model service** (`use_model_service`) and provide
  `model_service_url`.

Notes:

- Remote model service projects do not support interim train-on-submit updates.
- You cannot set Model Pack and CDB/Vocab at the same time.

### Key project settings

| Setting | Description |
|---|---|
| `require_entity_validation` | If enabled, model suggestions must be explicitly reviewed before submit. |
| `train_model_on_submit` | If enabled, validated annotations are used for incremental training on submit. |
| `add_new_entities` | Allows users to add brand-new concepts. |
| `restrict_concept_lookup` | Restricts concept search to project CUI filters. |
| `terminate_available` | Shows terminate action in annotation toolbar. |
| `irrelevant_available` | Shows irrelevant action in annotation toolbar. |
| `enable_entity_annotation_comments` | Enables free-text comments per annotation. |
| `tasks` | Meta annotation tasks available in the annotator UI. |
| `relations` | Relation labels available for relation annotation. |
| `project_locked` | Locks project from further annotation edits. |
| `project_status` | Annotating / Complete / Discontinued. |

## Dataset format

Upload CSV or XLSX with at least:

| name | text |
|---|---|
| unique-doc-id | document text to annotate |

`name` should be unique per dataset.

## Project list operations

From the home **Projects** table:

- Open and annotate a project.
- Run document preparation in the background.
- View model-loaded state and clear model cache.
- Save current model state.
- Select compatible projects and submit a metrics report.

## Concept lookup index (Solr import)

Concept picker search requires CDB concepts to be imported into Solr.

1. Open `/admin`.
2. Go to **Concept Dbs**.
3. Select one or more CDBs.
4. Run **Import concepts** action.

After import, project list shows whether concepts are indexed for the selected
`cdb_search_filter`.

## Clone, reset, and delete

### In Project Admin UI

- **Clone**: duplicate project configuration under a new name.
- **Reset**: remove annotations and clear prepared/validated document state.
- **Delete**: permanently remove the project.

### In Django Admin

Equivalent bulk actions are available under **Project annotate entities**.

## Downloading annotations

From Django admin (`/admin` -> **Project annotate entities**), use bulk actions
to export annotations:

- with source text
- without source text
- without source text but with document names

Notebook examples for downstream processing are in:

- `notebook_docs/Processing_Annotations.ipynb`

## Saving and downloading model artifacts

For online-learning projects, admins can save current model state from the
project list. In general, offline retraining from exported annotations is still
recommended for production model releases.
