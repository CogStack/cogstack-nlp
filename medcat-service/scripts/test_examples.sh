#!/bin/bash
# Integration test of medcat service docker image
echo "Running integration test of medcat service"

if [ -n "$IMAGE_TAG" ]; then
  echo "Testing image tag $IMAGE_TAG"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VARIANT=$1

if [ "$VARIANT" = "v1" ]; then
  COMPOSE_FILE="docker-compose.example.v1.yml"
elif [ "$VARIANT" = "DeID" ]; then
  COMPOSE_FILE="docker-compose.example.deid.yml"
else
  COMPOSE_FILE="docker-compose.example.yml"
fi

cd "${SCRIPT_DIR}/../docker"
bash run_example_simple.sh "${VARIANT}"

if [ $? -eq 0 ]; then
    echo "✅ Success! Medcat service passed integration tests"
    docker compose -f "${COMPOSE_FILE}" down
    exit 0
else
    echo "❌ Failure. Medcat service failed tests"
    docker compose -f "${COMPOSE_FILE}" down
    exit 1
fi

