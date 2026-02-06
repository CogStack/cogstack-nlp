#!/bin/sh
set -e

echo "Generating runtime config.json from template..."

# Set USE_OIDC to 0 if not provided (traditional auth mode)
export USE_OIDC="${USE_OIDC:-0}"

# If OIDC is enabled, validate required variables
if [ "$USE_OIDC" = "1" ]; then
  echo "OIDC mode enabled - validating OIDC environment variables..."

  if [ -z "$KEYCLOAK_URL" ]; then
    echo "ERROR: KEYCLOAK_URL is required when USE_OIDC=1"
    exit 1
  fi

  if [ -z "$KEYCLOAK_REALM" ]; then
    echo "ERROR: KEYCLOAK_REALM is required when USE_OIDC=1"
    exit 1
  fi

  if [ -z "$KEYCLOAK_FRONTEND_CLIENT_ID" ]; then
    echo "ERROR: KEYCLOAK_FRONTEND_CLIENT_ID is required when USE_OIDC=1"
    exit 1
  fi

  if [ -z "$KEYCLOAK_LOGOUT_REDIRECT_URI" ]; then
    echo "ERROR: KEYCLOAK_LOGOUT_REDIRECT_URI is required when USE_OIDC=1"
    exit 1
  fi

else
  echo "Traditional auth mode enabled (USE_OIDC=0)"
  # Set Defaults
  export KEYCLOAK_URL="${KEYCLOAK_URL:-}"
  export KEYCLOAK_REALM="${KEYCLOAK_REALM:-}"
  export KEYCLOAK_LOGOUT_REDIRECT_URI="${KEYCLOAK_LOGOUT_REDIRECT_URI:-}"
  export KEYCLOAK_FRONTEND_CLIENT_ID="${KEYCLOAK_FRONTEND_CLIENT_ID:-}"
fi

# Check if template exists
TEMPLATE_FILE="/home/frontend/dist/config.template.json"
if [ ! -f "$TEMPLATE_FILE" ]; then
  echo "ERROR: Template not found at $TEMPLATE_FILE"
  exit 1
fi

# Set token refresh settings with sensible defaults
# KEYCLOAK_TOKEN_MIN_VALIDITY: Refresh token if it expires in less than this many seconds (default: 30s)
# KEYCLOAK_TOKEN_REFRESH_INTERVAL: Check token validity every N seconds (default: 20s)
export KEYCLOAK_TOKEN_MIN_VALIDITY="${KEYCLOAK_TOKEN_MIN_VALIDITY:-30}"
export KEYCLOAK_TOKEN_REFRESH_INTERVAL="${KEYCLOAK_TOKEN_REFRESH_INTERVAL:-20}"

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
