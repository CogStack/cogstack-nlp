#!/bin/bash
set -euo pipefail

echo "Waiting for service to start..."

# install bs4 for tests
python -m pip install beautifulsoup4

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

python tests/test_integration.py
