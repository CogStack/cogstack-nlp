#!/bin/bash
# Integration test of medcat service docker image
echo "Running integration test of medcat service"

if [ -n "$IMAGE_TAG" ]; then
  echo "Testing image tag $IMAGE_TAG"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"


cd ${SCRIPT_DIR}/../docker
bash run_example_simple.sh $1

# Check if health check was successful
if [ $? -eq 0 ]; then
    echo "✅ Success! Medcat service passed integration tests"
    docker compose -f docker-compose.example.yml down
    exit 0
else
    echo "❌ Failure. Medcat service failed tests"
    exit 1
fi

