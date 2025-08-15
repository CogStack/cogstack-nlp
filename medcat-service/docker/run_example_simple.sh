#!/usr/bin/env bash

DOCKER_COMPOSE_FILE_V1="docker-compose.example.v1.yml"
DOCKER_COMPOSE_FILE_V2="docker-compose.example.yml"
DOCKER_COMPOSE_FILE_DEID="docker-compose.example.deid.yml"

EXAMPLE_TO_RUN=$1

# choose between file based on CLI argument
if [ "$EXAMPLE_TO_RUN" = "v1" ]; then
  DOCKER_COMPOSE_FILE="$DOCKER_COMPOSE_FILE_V1"
elif [ "$EXAMPLE_TO_RUN" = "DeID" ]; then
  DOCKER_COMPOSE_FILE="$DOCKER_COMPOSE_FILE_DEID"
else
  DOCKER_COMPOSE_FILE="$DOCKER_COMPOSE_FILE_V2"
fi
# To run in a container run "export LOCALHOST_NAME=host.docker.internal"
LOCALHOST_NAME=${LOCALHOST_NAME:-localhost}

echo "Running docker-compose"
docker compose -f ${DOCKER_COMPOSE_FILE} up -d

echo "Running test"
source ../scripts/integration_test_functions.sh
smoketest_medcat_service $LOCALHOST_NAME $DOCKER_COMPOSE_FILE

if [ $? -ne 0 ]; then
    echo "Failed basic smoketest"
    exit 1
fi

# Test the deployment
if [ $EXAMPLE_TO_RUN = "DeID" ]; then
  EXPECTED_ANNOTATION="PATIENT"
else
  EXPECTED_ANNOTATION="Kidney Failure"
fi
integration_test_medcat_service $LOCALHOST_NAME 5555 "$EXPECTED_ANNOTATION"
if [ $? -ne 0 ]; then
    echo "Failed integration test"
    exit 1
fi

cat <<EOF
-----------------------------------------------------------------
MedCATService running on http://${LOCALHOST_NAME}:5555/
-----------------------------------------------------------------
EOF