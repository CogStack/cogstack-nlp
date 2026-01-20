#!/bin/sh
set -e

echo "Generating runtime config.json from template..."

# Verify required environment variables are set
if [ -z "$VITE_USE_OIDC" ]; then
  echo "ERROR: VITE_USE_OIDC environment variable is required"
  exit 1
fi

if [ -z "$VITE_KEYCLOAK_URL" ]; then
  echo "ERROR: VITE_KEYCLOAK_URL environment variable is required"
  exit 1
fi

if [ -z "$VITE_KEYCLOAK_REALM" ]; then
  echo "ERROR: VITE_KEYCLOAK_REALM environment variable is required"
  exit 1
fi

if [ -z "$VITE_KEYCLOAK_CLIENT_ID" ]; then
  echo "ERROR: VITE_KEYCLOAK_CLIENT_ID environment variable is required"
  exit 1
fi

if [ -z "$VITE_LOGOUT_REDIRECT_URI" ]; then
  echo "ERROR: VITE_LOGOUT_REDIRECT_URI environment variable is required"
  exit 1
fi

# Check if template exists
TEMPLATE_FILE="/home/frontend/dist/config.template.json"
if [ ! -f "$TEMPLATE_FILE" ]; then
  echo "ERROR: Template not found at $TEMPLATE_FILE"
  exit 1
fi

# Generate config.json from template
envsubst < "$TEMPLATE_FILE" > /home/frontend/dist/config.json

# Copy to static directory for web access
if [ ! -d "/home/api/static" ]; then
  mkdir -p -v /home/api/static
fi

cp /home/frontend/dist/config.json /home/api/static/config.json
echo "Generated /home/api/static/config.json: "
cat /home/api/static/config.json

echo "Runtime config generation complete"
