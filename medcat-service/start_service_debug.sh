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

fastapi dev medcat_service/main.py 