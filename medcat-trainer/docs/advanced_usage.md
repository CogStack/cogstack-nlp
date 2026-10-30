# Advanced Usage

This page covers API-first workflows and power-user features.

## Notebook examples

The repository includes notebook examples:

- `notebook_docs/API_Examples.ipynb`
- `notebook_docs/Processing_Annotations.ipynb`

These are useful for bulk project creation, export processing, and automation.

## REST API basics

Base path: `/api/`

Common endpoints:

- `GET/POST /api/project-annotate-entities/`
- `GET/POST /api/datasets/`
- `GET/POST /api/modelpacks/`
- `GET/POST /api/concept-dbs/`
- `GET/POST /api/vocabs/`

### Authentication

- Local auth token: `POST /api/api-token-auth/`
- OIDC bearer token (if enabled): send `Authorization: Bearer <token>`

## Project Admin API endpoints

Modern project-admin UI uses dedicated endpoints:

- `GET /api/project-admin/projects/`
- `POST /api/project-admin/projects/create/`
- `GET/PUT/DELETE /api/project-admin/projects/<project_id>/`
- `POST /api/project-admin/projects/<project_id>/clone/`
- `POST /api/project-admin/projects/<project_id>/reset/`

## Project Group APIs

- `GET/POST /api/project-groups/`
- `GET/PUT/PATCH/DELETE /api/project-groups/<id>/`

`POST` accepts the shared project settings plus `annotators`,
`administrators`, and `create_associated_projects`. Prefer the
[Python client](client.md) helpers `create_project_group` /
`get_project_groups` for scripting.

## Metrics APIs

- `GET/POST /api/metrics-job/` (list jobs / submit new report)
- `DELETE /api/metrics-job/<report_id>/` (remove report job)
- `GET/PUT /api/metrics/<report_id>/` (fetch report / rename report)

Only compatible projects should be combined (same underlying model
configuration) when generating reports.

Concept Summary exclusion / low-F1 filtering in the UI is client-side over the
fetched report payload; there is no separate filter API. See
[Project Admin — Metrics reports](project_admin.md#metrics-reports).

## Document text search API

- `GET /api/search-documents/?dataset=<id>&text=<query>&page=<n>`

Returns DRF-style `{count, next, results}` pages (50 hits per page). Results
include document `id`, `name`, and `text`. Phrase search runs against the
dataset's indexed note text in the Solr collection named by
`DOCUMENT_SEARCH_COLLECTION`. When the dataset is not fully indexed or Solr is
unavailable, the endpoint falls back to a case-insensitive database contains
match.

## Concept exploration and filter export

Use the **Concepts** view (`/model-explore`) to:

- browse hierarchy paths,
- choose parent concepts,
- generate and export JSON filter lists for project CUI filters.

Related API endpoints:

- `POST /api/generate-concept-filter/`
- `POST /api/generate-concept-filter-json/`
- `GET /api/model-concept-children/<cdb_id>/`

## Remote model service projects

Projects can use a remote MedCAT model service instead of local model loading
by setting:

- `use_model_service = true`
- `model_service_url = <service-base-url>`

Operational note: train-on-submit updates are not applied for remote model
service projects.

## Python client

For scripting and CI pipelines, see [client.md](client.md) and the `mctclient`
package.
