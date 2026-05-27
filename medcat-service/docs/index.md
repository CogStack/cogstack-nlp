# Medcat service documentation

Medcat service is a REST API for serving [MedCAT](https://github.com/CogStack/cogstack-nlp/blob/main/medcat-v2/) models, allowing you to perform named entity resolution and deidentification of medical text over an API.

Feel free to ask questions on the github issue tracker or on our [discourse website](https://discourse.cogstack.org) which is frequently used by our development team!

## Demo
<video loop muted playsinline controls style="max-width: 100%; height: auto;">
  <source src="assets/demo-api.webm" type="video/webm">
</video>

## Features

### Clinical NLP over HTTP

- **Single-document processing** — `POST /api/process` accepts free-text clinical notes and returns entities with CUIs, types, spans, and meta-annotations (for example negation and subject).
- **Bulk processing** — `POST /api/process_bulk` processes many documents in one request, with parallel annotation via configurable worker threads (`APP_BULK_NPROC`).
- **Meta-annotation filtering** — Optional `meta_anns_filters` on `/api/process` let you return only entities that match selected meta-annotation values (for example affirmed presence or patient subject).
- **AnonCAT De-identification** - Detect and redact identifiable information in clinical text by loading an AnonCAT model. See [API examples](user-guide/api-example-use.md).

### Demo UI

- **Interactive model trial** — A user friendly UI to try out medcat models and see the results. See [Demo UI](user-guide/demo-ui.md).

### Operations and observability

- **Health endpoints** — Kubernetes-friendly liveness (`/api/health/live`) and readiness (`/api/health/ready`) checks that verify the model is loaded.
- **Service metadata** — `GET /api/info` returns application name, language, version, and loaded model details.
- **Metrics** — Optional prometheus metrics of the service on `/metrics` when `APP_ENABLE_METRICS=True`.
- **Tracing** — Distributed tracing export for production deployments. See [Configuration](setup/configuration.md#telemetry).


## Get started

| Topic | Guide |
|-------|-------|
| Install with Helm or Docker Compose | [Installation](setup/installation.md) |
| Environment variables and tuning | [Configuration](setup/configuration.md) |
| `curl` examples for process and bulk APIs | [API example use](user-guide/api-example-use.md) |
| Try models in the browser | [Demo UI](user-guide/demo-ui.md) |
