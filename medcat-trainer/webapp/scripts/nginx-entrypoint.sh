#!/bin/sh
set -e

echo "[medcattrainer] Generating runtime config.json from template..."

# Verify required environment variables are set
if [ -z "$VITE_USE_OIDC" ]; then
  echo "[medcattrainer] ERROR: VITE_USE_OIDC environment variable is required"
  exit 1
fi

if [ -z "$VITE_KEYCLOAK_URL" ]; then
  echo "[medcattrainer] ERROR: VITE_KEYCLOAK_URL environment variable is required"
  exit 1
fi

if [ -z "$VITE_KEYCLOAK_REALM" ]; then
  echo "[medcattrainer] ERROR: VITE_KEYCLOAK_REALM environment variable is required"
  exit 1
fi

if [ -z "$VITE_KEYCLOAK_CLIENT_ID" ]; then
  echo "[medcattrainer] ERROR: VITE_KEYCLOAK_CLIENT_ID environment variable is required"
  exit 1
fi

if [ -z "$VITE_LOGOUT_REDIRECT_URI" ]; then
  echo "[medcattrainer] ERROR: VITE_LOGOUT_REDIRECT_URI environment variable is required"
  exit 1
fi

# Check if template exists
TEMPLATE_FILE="/home/frontend/dist/config.template.json"
if [ ! -f "$TEMPLATE_FILE" ]; then
  echo "[medcattrainer] ERROR: Template not found at $TEMPLATE_FILE"
  exit 1
fi

# Generate config.json from template
envsubst < "$TEMPLATE_FILE" > /home/frontend/dist/config.json

# Copy to static directory for web access (must be done after collectstatic)
if [ -d "/home/api/static" ]; then
  cp /home/frontend/dist/config.json /home/api/static/config.json
  echo "[medcattrainer] Generated /home/api/static/config.json with:"
  echo "  USE_OIDC=$VITE_USE_OIDC"
  echo "  KEYCLOAK_URL=$VITE_KEYCLOAK_URL"
  echo "  KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM"
  echo "  KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID"
else
  echo "[medcattrainer] WARNING: /home/api/static directory does not exist yet"
  echo "[medcattrainer] Config will be copied when collectstatic runs"
fi

echo "[medcattrainer] Runtime config generation complete"
