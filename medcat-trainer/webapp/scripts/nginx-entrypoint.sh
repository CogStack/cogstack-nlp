#!/bin/sh
set -e

echo "Generating runtime config.json from template..."

# Set VITE_USE_OIDC to 0 if not provided (traditional auth mode)
export VITE_USE_OIDC="${VITE_USE_OIDC:-0}"

# If OIDC is enabled, require all OIDC-related variables
if [ "$VITE_USE_OIDC" = "1" ]; then
  echo "OIDC mode enabled - validating OIDC environment variables..."

  if [ -z "$VITE_KEYCLOAK_URL" ]; then
    echo "ERROR: VITE_KEYCLOAK_URL environment variable is required when VITE_USE_OIDC=1"
    exit 1
  fi

  if [ -z "$VITE_KEYCLOAK_REALM" ]; then
    echo "ERROR: VITE_KEYCLOAK_REALM environment variable is required when VITE_USE_OIDC=1"
    exit 1
  fi

  if [ -z "$VITE_KEYCLOAK_CLIENT_ID" ]; then
    echo "ERROR: VITE_KEYCLOAK_CLIENT_ID environment variable is required when VITE_USE_OIDC=1"
    exit 1
  fi

  if [ -z "$VITE_LOGOUT_REDIRECT_URI" ]; then
    echo "ERROR: VITE_LOGOUT_REDIRECT_URI environment variable is required when VITE_USE_OIDC=1"
    exit 1
  fi

else
  echo "Traditional auth mode enabled (VITE_USE_OIDC=0)"
  # Traditional auth mode - set defaults for unused variables
  export VITE_KEYCLOAK_URL="${VITE_KEYCLOAK_URL:-http://localhost}"
  export VITE_KEYCLOAK_REALM="${VITE_KEYCLOAK_REALM:-default}"
  export VITE_KEYCLOAK_CLIENT_ID="${VITE_KEYCLOAK_CLIENT_ID:-medcattrainer}"
  export VITE_LOGOUT_REDIRECT_URI="${VITE_LOGOUT_REDIRECT_URI:-/}"
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
