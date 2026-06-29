# Django Admin

The **Django Admin** (`/admin`) provides advanced actions and low-level data
management that are not available in the Project Admin UI (`/project-admin`).

These include:



## Concept lookup index (Solr import)

Concept picker search requires CDB concepts to be imported into Solr.

1. Open `/admin`.
2. Go to **Concept Dbs**.
3. Select one or more CDBs.
4. Run **Import concepts** action.

![](_static/img/select-concept-dbs.png)

![](_static/img/import-concepts.png)

After import, project list shows whether concepts are indexed for the selected
`cdb_search_filter`.

![](_static/img/concepts-imported-status.png)


## Downloading annotations

From Django admin (`/admin` -> **Project annotate entities**), use bulk actions
to export annotations:

- with source text
- without source text
- without source text but with document names

![](_static/img/project_annotate_entities.png)

![](_static/img/download-annos.png)

Notebook examples for downstream processing are in:

- `notebook_docs/Processing_Annotations.ipynb`

## Saving and downloading model artifacts

For online-learning projects, admins can save current model state from the
project list. In general, offline retraining from exported annotations is still
recommended for production model releases.

