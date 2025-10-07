#!/bin/bash
set -e

# download the sci-scpacy language model
# NOTE: requirements are installed separately in the workflow
# python3 -m pip install -r ./requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu/;
python3 -m spacy download en_core_web_sm
python3 -m spacy download en_core_web_md
python3 -m spacy download en_core_web_lg

# download the test MedCAT model
bash ./scripts/download_medmen.sh
export APP_MODEL_CDB_PATH="$PWD/models/medmen/cdb.dat"
export APP_MODEL_VOCAB_PATH="$PWD/models/medmen/vocab.dat"

# proceed with the tests
#
echo "Starting the tests ..."

# run the python tests
python3 -m unittest discover -s medcat_service/test
if [ "$?" -ne "0" ]; then
    echo "Error: one or more tests failed"
    exit 1
fi
