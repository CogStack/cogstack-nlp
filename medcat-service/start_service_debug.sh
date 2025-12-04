#!/bin/bash
echo "Starting MedCAT Service"

# Optional - Enable DeID mode with:
#export APP_MEDCAT_MODEL_PACK="models/examples/example-deid-model-pack.zip"
#export DEID_MODE=True
#export DEID_REDACT=True

if [ -z "${APP_MODEL_CDB_PATH}" ] && [ -z "${APP_MODEL_VOCAB_PATH}" ] && [ -z "${APP_MEDCAT_MODEL_PACK}" ]; then
  export APP_MEDCAT_MODEL_PACK="models/examples/example-medcat-v2-model-pack.zip"
  echo "Using default model pack in  $APP_MEDCAT_MODEL_PACK"
fi

export APP_ENABLE_METRICS=${APP_ENABLE_METRICS:-True}

fastapi dev medcat_service/main.py 

export OTEL_TRACES_EXPORTER=otlp
export OTEL_SERVICE_NAME=medcat-service
export OTEL_EXPORTER_OTLP_ENDPOINT="http://host.docker.internal:4318"
export OTEL_EXPORTER_OTLP_PROTOCOL="http/protobuf"
export OTEL_METRICS_EXPORTER=none
export OTEL_PYTHON_DISABLED_INSTRUMENTATIONS="jinja2"
opentelemetry-instrument fastapi dev medcat_service/main.py