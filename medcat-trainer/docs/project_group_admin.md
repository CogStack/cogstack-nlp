# Annotation Project Groups

Project Groups help coordinate multi-annotator projects at scale.

They allow admins to define shared configuration once and apply it across a set
of associated annotation projects.

## When to use Project Groups

Use a group when you need:

- one project per annotator over the same dataset/configuration,
- centralized settings management for those projects, or
- grouped visibility in the home screen.

## Creating a Project Group

Prefer **Project Admin** (`/project-admin`) for day-to-day group creation.

1. Open `/project-admin` and go to the **Projects** tab.
2. Select **+ Create New Project**, then switch the form type to **Project Group**.
3. Configure shared settings (dataset, model, concept filters, tasks, and so on).
4. Under **Group Members**:
   - **Administrators** can see and manage every project in the group (you are added automatically).
   - **Annotators** each receive their own annotation project when associated projects are created.
5. Leave **Create an annotation project for each annotator** checked unless you only want the group shell.
6. Save.

You can still create or edit groups in Django admin (`/admin` -> **Project groups**) when you need low-level control.

### `create_associated_projects = true` (default)

On save, MedCATtrainer automatically creates one
`ProjectAnnotateEntities` per selected annotator.

Naming pattern:

- `<Project Group Name> - <Annotator Username>`

Administrators are added to each generated project, plus the corresponding
annotator.

### `create_associated_projects = false`

No child projects are created automatically. Use this if you already have
projects and want to group them manually.

## Updating a group

When associated projects exist and remain aligned, group-level edits propagate
to child project settings (for example CUI filters, model settings, tasks).

If child projects were manually added/removed outside the expected structure,
automatic propagation may fail and projects should then be edited individually.

## Using groups in the UI

Admins can switch between **Single Projects** and **Project Groups** from the
home page and inspect projects within each group.

Regular annotators typically work with individual projects and may not need the
group view.

## Automating with the Python client

`mctclient` can create and list project groups for provisioning scripts and CI.
See [Python Client](client.md).

## Best practices

- For inter-annotator agreement studies, disable `train_model_on_submit` in
  all group projects.
- Keep naming conventions consistent for easy report comparison.
- Prefer one shared configuration template per annotation campaign.
