#!/usr/bin/env bash
set -e

export MODEL_NAME=medmen
export MODEL_VOCAB_URL=https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/vocab.dat 
export MODEL_CDB_URL=https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/cdb-medmen-v1.dat 
export MODEL_META_URL=https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/medcat-example-models/mc_status.zip 

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/../.venv/bin/python"

if [[ -x "${VENV_PYTHON}" ]]; then
  PYTHON_EXECUTABLE="${VENV_PYTHON}"
else
  PYTHON_EXECUTABLE=""

  for PYTHON_CANDIDATE in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "${PYTHON_CANDIDATE}" >/dev/null 2>&1; then
      PYTHON_EXECUTABLE="$(command -v "${PYTHON_CANDIDATE}")"
      break
    fi
  done

  if [[ -z "${PYTHON_EXECUTABLE}" ]]; then
    echo "Python 3 is required. Create .venv or install Python 3.11 through 3.14." >&2
    exit 1
  fi
fi

echo "Using $("${PYTHON_EXECUTABLE}" --version 2>&1) (${PYTHON_EXECUTABLE})"
"${PYTHON_EXECUTABLE}" "${SCRIPT_DIR}/download_model.py"
