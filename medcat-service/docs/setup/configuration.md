# Configuration

Medcat service can be configured with environment variables on startup.

## Service Environment vars



The following environment variables are available for tailoring the MedCAT Service `gunicorn` server:

- `SERVER_HOST` - specifies the host address (default: `0.0.0.0`),
- `SERVER_PORT` - the port number used (default: `5000`),
- `SERVER_WORKERS` - the number of workers serving the Flask app working in parallel (default: `1` ; only used in production server).
- `SERVER_WORKER_TIMEOUT` - the max timeout (in sec) for receiving response from worker (default: `300` ; only used with production server).
- `SERVER_GUNICORN_MAX_REQUESTS` - maximum number of requests a worker will process before restarting (default: `1000`),
- `SERVER_GUNICORN_MAX_REQUESTS_JITTER` - adds randomness to `MAX_REQUESTS` to avoid all workers restarting simultaneously (default: `50`),
- `SERVER_GUNICORN_EXTRA_ARGS` - any additional Gunicorn CLI arguments you want to pass (default: none). (Example value: "SERVER_GUNICORN_EXTRA_ARGS=--backlog 20")

The following environment variables are available for tailoring the MedCAT Service wrapper:

- `APP_MODEL_NAME` - an informative name of the model used by MedCAT (optional),
- `APP_MODEL_CDB_PATH` - the path to the model's concept database,
- `APP_MODEL_VOCAB_PATH` - the path to the model's vocabulary,
- `APP_MODEL_META_PATH_LIST` - the list of paths to meta-annotation models, each separated by `:` character (optional),
- `APP_BULK_NPROC` - the number of threads used in bulk processing (default: `8`),
- `APP_MEDCAT_MODEL_PACK` -  MedCAT Model Pack path, if this parameter has a value IT WILL BE LOADED FIRST OVER EVERYTHING ELSE (CDB, Vocab, MetaCATs, etc.) declared above.
- `APP_ENABLE_METRICS` - Enable prometheus metrics collection served on the path /metrics
- `APP_ENABLE_DEMO_UI` - Enable the demo user interface to try models. (Default: `False`)
- `APP_DEMO_UI_PATH` - Customise the path of the demo UI. (Default: `/`)

### Shared Memory (`DOCKER_SHM_SIZE`)

The MedCAT service uses PyTorch multiprocessing and memory-mapped models, which rely on Linux shared memory (`/dev/shm`).  
By default, Docker limits this to **64 MB**, which is insufficient for NLP models.

Use the environment variable `DOCKER_SHM_SIZE` to control the size of shared memory inside the container. 
You can set this variable in the `env/general.env` file.

- **Recommended**: `8g` for bulk inference (`APP_BULK_NPROC > 1`)  
- **Minimum**: `1g` for single-process inference (`APP_BULK_NPROC=1`)  

Example:

```env
DOCKER_SHM_SIZE=8g
```

### Telemetry
MedCAT Service supports exporting traces using Opentelemetry
To enable distributed tracing and telemetry in the MedCAT Service, several environment variables must be set. These can be configured in your environment files or exported in your startup scripts (see `start_service_debug.sh` and related files):

| Environment Variable                       | Description                                                                                       | Example Value                         |
|--------------------------------------------|---------------------------------------------------------------------------------------------------|---------------------------------------|
| `APP_ENABLE_TRACING`                       | Enable OpenTelemetry tracing in the application.                                                  | `True`                                |
| `OTEL_TRACES_EXPORTER`                     | Exporter to use for traces (commonly `otlp`).                                                     | `otlp`                                |
| `OTEL_SERVICE_NAME`                        | Logical service name for your traces.                                                             | `medcat-service`                      |
| `OTEL_EXPORTER_OTLP_ENDPOINT`              | URL for your OpenTelemetry collector.                                                             | `http://localhost:4317`               |
| `OTEL_EXPORTER_OTLP_PROTOCOL`              | Protocol to use for OTLP exporter.                                                                | `grpc`                                |
| `OTEL_METRICS_EXPORTER`                    | Set to `none` to disable metrics export, or another value if metrics are enabled.                 | `none`                                |
| `OTEL_PYTHON_FASTAPI_EXCLUDED_URLS`        | Comma-separated list of URLs to exclude from tracing and metrics (e.g., health/metrics endpoints).| `/api/health,/metrics`                |
| `OTEL_EXPERIMENTAL_RESOURCE_DETECTORS`     | Additional resource detectors to use (comma-separated).                                           | `containerid,os`                      |


See https://opentelemetry-python.readthedocs.io/en/latest/sdk/environment_variables.html for the full list of opentelemetry environment variables.

## Performance Tuning

Theres a range of factors that might impact the performance of this service, the most obvious being the size of the processed documents (amount of text per document) as well as the resources of the machine on which the service operates.
The main settings that can be used to improve the performance when querying large amounts of documents are : `SERVER_WORKERS` (number of flask web workers that chan handle parallel requests) and `APP_BULK_NPROC` (threads for annotation processing).

## MedCAT library

MedCAT parameters are defined in selected `envs/medcat*`  file.

For details on available MedCAT parameters please refer to [the official GitHub repository](https://github.com/CogStack/cogstack-nlp/blob/main/medcat-v2/).