#!/bin/bash
set -euo pipefail

echo "Waiting for service to start..."

# Wait until curl doesn't fail
for i in {1..60}; do
  if curl -s --fail http://localhost:8000 > /dev/null; then
    echo "Service is up"
    break
  else
    echo "Waiting ($i)..."
    sleep 2
  fi
done

# Submit test input and assert that it was processed
RESPONSE=$(curl -s -X POST -d "text=aspirin is good for headache" http://localhost:8000)

# Optionally print for debugging
echo "$RESPONSE"

# Check output contains a known string (your app returns doc_html/json in the template)
echo "$RESPONSE" | grep -q 'No documents yet' && echo "Form not processed" && exit 1
echo "$RESPONSE" | grep -q 'aspirin' || (echo "Expected annotation not found" && exit 1)

echo "Test passed ✅"
