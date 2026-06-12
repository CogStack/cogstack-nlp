# Annotation Project Creation and Management

An annotation project requires 4 elements:

| Element         | Description                                                                              |
|-----------------|------------------------------------------------------------------------------------------|
| Project setup   | Define the project’s name, purpose, and configuration settings.                          |
| Model           | Manage the available MedCAT models or connect to a remote model service for annotation projects   |
| Dataset         | Select or upload collections of documents to be annotated in projects             |
| Users           | Manage admins, annotators and superusers who can participate in annotation projects.            |

MedCATtrainer supports two management surfaces to create, update, delete these elements.

- **Project Admin UI** (`/project-admin`) for most project operations.
- **Django Admin** (`/admin`) for advanced actions and low-level data management.

The following user guide covers. `/project-admin`

## Project Administration

1. Open `/project-admin`.
2. Go to the **Projects** tab and select **+ Create New Project**. To edit an existing project select the project row.
3. Complete the forms for your project. Specifics of each field are discussed below.
4. Save.

### Basic Settings

| Field                        | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| **Project Name**             | Enter a name for your project.                                              |
| **Dataset**                  | Select an existing dataset or [upload a new one](#dataset-administration) to associate with the project. |
| **Description**              | Optionally provide a short summary describing your project.                 |
| **Guideline Link**           | (Optional) Add a URL to annotation guidelines for annotators.               |

### Project Settings
| Field                        | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| **Project Status** | Sets the current lifecycle stage of the project. Options are:<br>**Annotating** – Active annotation is ongoing;<br>**Complete** – Annotation is finished; further changes are prevented.<br>**Discontinued** – The project is no longer active and closed for annotation. |
| **Project Locked** | Locks project from further annotation edits. |
| **Annotation classification**        | **Checked**: Annotations are relevant for a 'global' model<br>**Unchecked**: Annotations are specific to this specific project and should not be used for further model training or fine-tuning |


### Model Configuration Settings
Available MedCAT models are shown here. If this is empty, first [add a local model pack](#model-pack-administration).

Pick one of:
1. **Local Model Pack** (recommended), or
2. **Use Concept DB + Vocabulary** pair. is a legacy MedCAT v1 option.

- **Remote model service** (`use_model_service`) can be used where model inference is available at a remote url.
  `model_service_url`.

!!! tip
    - Remote model service projects do not support interim train-on-submit updates.
    - You cannot set Model Pack and CDB/Vocab at the same time.

### Annotation Settings
| Field                        | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| **Require entity validation**        | If enabled, model suggestions must be explicitly reviewed before submit.|
| **Train on submit**                  | If enabled, validated annotations are used for incremental training on submit. |
| **Add new entities**               | Allows users to add brand-new concepts. Should be used with caution as most concept Dbs will be relatively complete for most use cases. |
| **Restrict concept lookup** | Restricts concept search to project CUI filters. |
| **Terminate available** | Shows terminate action in annotation toolbar. |
| **Irrelevant available** | Shows irrelevant action in annotation toolbar. |
| **Entity annotation comments** | Enables free-text comments per annotation. |

### Concept Filtering
| Field                        | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| **Incl. Sub-concepts**         | Include all concepts that are descendants to the selected concepts below.
| **Concept filter (optional)**| Add concept filters to limit available concepts for annotation by specifying a list of CUIs (Concept Unique Identifiers). Only these concepts will be available when annotating. |

### Member Setting
| Field                        | Description                                                                 |
|------------------------------|-----------------------------------------------------------------------------|
| **Members**                  | Add users to the project as annotators, administrators, or reviewers, controlling their access and editing permissions for this project. |


## Model Pack Administration
Manage the available local MedCAT models that can be configured into annotation projects

1. Open `/project-admin`.
2. Go to the **Model Packs** tab and select **+ Add Model Pack** OR a row to edit an existing model pack entry.
3. Complete the forms for your project. Specifics of each field are discussed below.
4. Save.

To delete a model pack, use the action button.

!!! tip
    - Only model packs are shown here. Legacy ConceptDB, Vocabulary models are not availabe from `/project-admin/`, they are only available from `/admin/`.
    - remote model service endpoints are directly entered as URLs within annotation projects


## Dataset Administration
Manage the availalbe datasets that can be configured into annotation projects.

1. Open `/project-admin`.
2. Go to the **Datasets** tab and select **+ Add Dataset** OR a row to edit a dataset entry.
3. Complete the forms for your project. Specifics of each field are discussed below.
4. Save.

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

