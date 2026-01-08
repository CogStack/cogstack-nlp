#!/bin/bash
echo "Starting MedCAT Service"

# Optional - Enable DeID mode with:
# export APP_MEDCAT_MODEL_PACK="models/examples/example-deid-model-pack.zip"
# export DEID_MODE=True
# export DEID_REDACT=True

if [ -z "${APP_MODEL_CDB_PATH}" ] && [ -z "${APP_MODEL_VOCAB_PATH}" ] && [ -z "${APP_MEDCAT_MODEL_PACK}" ]; then
  export APP_MEDCAT_MODEL_PACK="models/examples/example-medcat-v2-model-pack.zip"
  echo "Using default model pack in  $APP_MEDCAT_MODEL_PACK"
fi

export APP_ENABLE_METRICS=${APP_ENABLE_METRICS:-True}

if [ "${HOT_MODULE_RELOADING}" = "True" ]; then
  # Experimental: Hot module reloading. Need to `pip install -r requirements-dev.txt`
  echo "Running medcat-service with hot module reloading"
  uvicorn-hmr medcat_service/main:app --refresh --reload-include 'medcat_service'
else
  fastapi dev medcat_service/main.py 
fi

