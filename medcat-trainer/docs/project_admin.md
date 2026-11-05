# Project Administration

The cog icon in the top-right of the header opens **Project Administration**
at `/project-admin`. Use it to set up the pieces an annotation campaign needs:
users, a dataset, a model, and then either one annotation project or a
project group.

Staff and superuser accounts see the cog. With username/password login that
is any user marked **Staff** or **Superuser**. With OIDC it is users who have
the `medcattrainer_superuser` realm role. Annotators do not see the icon and
are sent back to the home page if they open `/project-admin` directly.

Django Admin (`/admin`) is still used for low-level actions that this screen
does not cover. See [Django Admin](django_admin.md).

## Screen layout

The page has four tabs:

| Tab | Use it to |
| --- | --- |
| **Projects** | Create and edit annotation projects, and create project groups. |
| **Model Packs** | Upload a MedCAT model pack, or register a legacy Concept DB and vocabulary pair. |
| **Datasets** | Upload the documents that projects annotate. |
| **Users** | Add annotators and administrators. |

The button at the top right changes with the tab: **Create**, **Add Model
Pack**, **Add Dataset**, or **Add User**.

A practical order for a new deployment:

1. Add users.
2. Upload a dataset.
3. Upload a model pack.
4. Create a project, or a project group.

## Projects

The **Projects** tab lists annotation projects you belong to, and projects in
groups you administer. It does not list every project on the server. Saving
a new project adds you as a member, so projects you create appear here
afterwards.

Each row shows the title, description, status, mode, dataset, and created and
modified dates. Description is hidden on narrower windows. The list is sorted
by last modified, newest first. Click a column heading to sort by title,
created date, or modified date. Filter the title box, or use the **Status**
and **Mode** dropdowns. **Clear filters** appears when nothing matches.

| Mode badge | Meaning |
| --- | --- |
| **Annotate** | **Require Entity Validation** is on. Model suggestions must be reviewed before submit. |
| **Validate** | **Require Entity Validation** is off. Suggestions are not held for review. |

| Status badge | Meaning |
| --- | --- |
| **Annotating** | Collection is in progress. |
| **Complete** | Collection has finished. |
| **Discontinued** | The project was stopped. |

Click a row to edit that project. The row actions are:

| Action | Effect |
| --- | --- |
| **Clone** | Copies the project configuration, members, concept search filter, meta tasks, and relations under a new name. Annotations are not copied. The suggested name is `<project name> (Clone)`. |
| **Reset** | Deletes every annotation on the project and clears its validated and prepared documents. Settings, dataset, and model stay as they are. |
| **Delete** | Deletes the project. This cannot be undone. |

An empty list offers **Create Your First Project** and **Create a Project
Group**.

### Create a project

1. Open the cog icon, stay on **Projects**, and click **Create**.
2. Leave the switch on **Project**.
3. Fill in the form. Required fields are marked with `*`.
4. Click **Save Project**.

The same form is used to edit an existing project. Click **Back** to return
to the list without saving.

### Create a project group

A project group stores one shared configuration and, by default, creates one
annotation project per annotator. Use a group for double annotation,
agreement metrics, or adjudication, where each annotator should see the same
dataset and the same settings.

1. Open the cog icon and click **Create** (or **Create a Project Group** on an empty list).
2. Switch the form to **Project Group**.
3. Leave **Create an annotation project for each annotator** checked unless you only want the group record.
4. Fill in the shared settings. Select at least one annotator when the checkbox above is on.
5. Click **Save Project Group**.

The banner on the group form reads: shared settings across annotators, used
for agreement metrics and adjudication.

With the checkbox on, MedCATtrainer creates one project per selected
annotator:

- Name: `<group name> - <annotator username>`
- Members: every selected administrator, the annotator for that project, and you
- Settings: the dataset, model, filters, tasks, and annotation options from the form

You are added as a group administrator even if you did not select yourself.
Generated projects show up as normal rows on this tab and on the home
**Projects** list. The group itself is opened from the home **Project
Groups** tab. See [Project Groups](project_group_admin.md).

Uncheck **Create an annotation project for each annotator** to save the group
without creating projects. The settings are still stored on the group. Attach
existing projects to it later from Django admin. The checkbox only applies
when the group is first saved. This screen does not edit a group after that.
To change the shared template, or to push those changes down into the child
projects, use Django admin (`/admin` -> **Project groups**). Editing one
generated project here changes only that project.

For an agreement study, turn **Train Model on Submit** off so each annotator
reviews the same model output.

The same setup can be scripted with `mctclient`. See
[Python Client](client.md).

## Project and group form

Projects and project groups share the sections below. The members section
changes when **Project Group** is selected.

### Basic Information

| Field | Description |
| --- | --- |
| **Project Name** * | Name shown in project lists. Must be unique. For a group, this is the group name; each generated project appends the annotator username. |
| **Dataset** * | Documents to annotate. Upload one on the **Datasets** tab if the list is empty. |
| **Description** | Short note on what is being collected and why. |
| **Annotation Guideline Link** | Optional URL, for example a Google Doc or SharePoint page, shown to annotators. |
| **Use Default Guideline** | Fills the link with the built-in example guideline and locks the URL field. Clear the box to enter your own link. |

### Project Settings

| Field | Description |
| --- | --- |
| **Project Status** | **Annotating** (default), **Complete**, or **Discontinued (Fail)**. |
| **Project Locked** | Marks collection as finished. Leave unchecked while annotators are still working. |
| **Annotation Classification** | Checked when the labels are suitable for a general-purpose model. Leave unchecked when the labels are local to this clinical area or use case. If in doubt, leave it unchecked. |

### Model Configuration

Pick one model source:

1. **Local Model Pack** (recommended). Upload the pack on the **Model Packs** tab first.
2. **Use Concept DB / Vocabulary pair**, for a legacy MedCAT v1 concept database and vocabulary.
3. **Use remote MedCAT service API**, and enter **Remote Model Service URL** (for example `http://medcat-service:8000`).

A project must have a model pack, or both a Concept DB and a vocabulary,
unless it uses a remote service. A model pack and a Concept DB / vocabulary
pair cannot be set together. Choosing a remote service turns off the local
model pack selector.

!!! tip
    Remote model service projects do not apply train-on-submit updates.
    Interim training needs a local model pack.

Choosing a model pack that includes MetaCAT models pre-selects the meta
annotation tasks linked to those models.

### Annotation Settings

| Field | Default | Description |
| --- | --- | --- |
| **Require Entity Validation** | On | Suggestions start unvalidated and must be marked before the document can be submitted. This is the **Annotate** mode in the project list. |
| **Train Model on Submit** | On | Each submission incrementally trains the local model. Has no effect on a remote model service. Turn this off for agreement studies. |
| **Add New Entities** | Off | Lets annotators create concepts that are not already in the concept database. Leave off unless the database is known to be missing terms you intend to add. |
| **Restrict Concept Lookup** | Off | Limits concept search to the CUI filter below. Has no effect when that filter is empty. |
| **Terminate Available** | On | Shows **Terminate** in the annotation toolbar. |
| **Irrelevant Available** | Off | Shows **Irrelevant** in the annotation toolbar. |
| **Enable Entity Annotation Comments** | Off | Shows a free-text comment on each annotation. |

### Concept Filtering

Limit the concepts annotators can use by building a CUI list.

- Select a model pack, or a Concept DB via the legacy option, then search with the concept picker. Each pick is added as a pill.
- **Paste CUIs (optional)** accepts identifiers separated by commas, semicolons, or new lines.

An empty filter means every concept in the model is available. **Restrict
Concept Lookup** only searches within this list.

Saving a project or group sets the concept-lookup database to the Concept DB
inside the selected model pack, or to the Concept DB chosen in the legacy
pair.

### Meta Annotation & Relation Tasks

| Field | Description |
| --- | --- |
| **Meta Annotation Tasks** | Tasks such as Temporality or Experiencer, shown in the annotator sidebar for Correct and Alternative concepts. Hold Ctrl (Cmd on macOS) to select more than one. |
| **Relation Tasks** | Relation types that can be marked between annotated concepts. |

If both lists are empty, create the tasks in Django admin (`/admin`, under
**Meta tasks** and **Relations**), or upload a model pack that already links
MetaCAT models. Task values are defined in Django admin. See
[Meta Annotations](meta_annotations.md).

### Members

For a single project, **Project Members** are the users who can open it.
Hold Ctrl (Cmd on macOS) to select more than one. You are added if you are
not already in the list.

For a project group the section is **Group Members**:

| Field | Description |
| --- | --- |
| **Administrators** | Users who can see and manage every project in the group. You are added automatically. |
| **Annotators** * | Required while **Create an annotation project for each annotator** is checked. One project is created for each username selected here. |

## Concept lookup index (Solr import)

Concept search in the annotator sidebar reads a Solr index of the project's
concept database. Saving a project or project group checks that index. If it
is missing, MedCATtrainer starts an import in the background and shows
"Started importing concepts for the selected model." Large databases take a
few minutes. The home project list then shows whether concepts are imported.

If the sidebar never shows concept details, the import has not finished or
did not start. You can run it yourself from Django admin. See
[Concept lookup index (Solr import)](django_admin.md#concept-lookup-index-solr-import).

## Model Packs

1. Open the **Model Packs** tab.
2. Click **Add Model Pack**, or click a row to edit one.
3. Enter a name and choose a `.zip` model pack.
4. Click **Save Model Pack**.

**Legacy model upload (CBD & Vocab)** switches the form to an existing
Concept DB and vocabulary instead of a zip file. Both are required in that
mode. Those files themselves are uploaded from Django admin, not from this
tab.

The trash icon deletes a model pack. Projects that were using it no longer
have a model and need another one before annotation can continue.

## Datasets

1. Open the **Datasets** tab.
2. Click **Add Dataset**, or click a row to edit the name and description or to replace the file.
3. Click **Save Dataset**.

The file is `.csv` or `.xlsx` and must include:

| name | text |
| --- | --- |
| unique-doc-id | document text to annotate |

`name` is the document id and must be unique inside the dataset. `text` is
the text annotators see. Any other columns are ignored.

Example:

```csv
name,text
doc001,"This is the first document to annotate."
doc002,"This is the second document with medical text."
```

The file is required when the dataset is created. The trash icon deletes the
dataset and its file.

## Users

1. Open the **Users** tab.
2. Click **Add User**, or click a row to edit username, email, and flags.
3. Click **Save User**.

| Field | Description |
| --- | --- |
| **Username** * | Sign-in name. |
| **Email** | Optional. |
| **Password** | Shown when adding a user. It is not saved from this screen. Set the password in Django admin (`/admin` -> **Users**) or with the password-reset flow before the person signs in. |
| **Staff** | Lets the user open this screen from the cog icon. |
| **Superuser (Admin)** | Full platform access, including Django admin. |

Annotators only need a username and a password set in Django admin. Leave
**Staff** and **Superuser (Admin)** off for them. This tab does not delete
users.

## Where to go next

- Annotate from the home **Projects** list. See [Annotator Guide](annotator_guide.md).
- Open a group from the home **Project Groups** tab. See [Project Groups](project_group_admin.md).
- Export annotations, import concepts by hand, and edit a group after creation in [Django Admin](django_admin.md).
