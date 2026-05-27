#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEBAPP_DIR="$(cd "$ROOT_DIR/.." && pwd)"
API_DIR="$WEBAPP_DIR/api"
ENV_FILE="${MCT_ENV_FILE:-$ROOT_DIR/../../envs/env}"

MODE="${1:-server}"

usage() {
  cat <<'EOF'
Usage:
  ./run_local_debug.sh [server|worker|shell|bootstrap]

Modes:
  server     Bootstrap local DB, then run Django on 0.0.0.0:8001.
  worker     Bootstrap local DB, then run background-task worker.
  shell      Bootstrap local DB, then open Django shell.
  bootstrap  Run local bootstrap only, then exit.

App settings are sourced from:
  envs/env

Script-only overrides:
  MCT_DEBUG_HOST=127.0.0.1
  MCT_DEBUG_PORT=8001
  MCT_ENV_FILE=/path/to/env
  MCT_ADMIN_USERNAME=admin
  MCT_ADMIN_PASSWORD=admin
  MCT_BOOTSTRAP_ADMIN=0
  MCT_RESET_ADMIN_PASSWORD=0
  MCT_RUN_MIGRATIONS=0
  MCT_START_SOLR=1
  MCT_GATEWAY_NETWORK_NAME=gateway-auth_gateway-net
  MCT_SYNC_DEPS=1
EOF
}

if [[ "$MODE" == "-h" || "$MODE" == "--help" ]]; then
  usage
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but was not found on PATH." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

export UV_PROJECT="$WEBAPP_DIR"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

HOST="${MCT_DEBUG_HOST:-0.0.0.0}"
PORT="${MCT_DEBUG_PORT:-8001}"

ADMIN_USERNAME="${MCT_ADMIN_USERNAME:-admin}"
ADMIN_EMAIL="${MCT_ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${MCT_ADMIN_PASSWORD:-admin}"
BOOTSTRAP_ADMIN="${MCT_BOOTSTRAP_ADMIN:-1}"
RESET_ADMIN_PASSWORD="${MCT_RESET_ADMIN_PASSWORD:-1}"
RUN_MIGRATIONS="${MCT_RUN_MIGRATIONS:-1}"
BOOTSTRAP_GROUP="${MCT_BOOTSTRAP_GROUP:-1}"
SYNC_DEPS="${MCT_SYNC_DEPS:-auto}"
START_SOLR="${MCT_START_SOLR:-1}"
GATEWAY_NETWORK_NAME="${MCT_GATEWAY_NETWORK_NAME:-gateway-auth_gateway-net}"
export MCT_GATEWAY_NETWORK_NAME="$GATEWAY_NETWORK_NAME"

run_manage() {
  (cd "$API_DIR" && uv run python manage.py "$@")
}

ensure_docker_network() {
  local network_name="$1"

  if docker network inspect "$network_name" >/dev/null 2>&1; then
    return
  fi

  echo "Creating Docker network: $network_name"
  docker network create "$network_name" >/dev/null || docker network inspect "$network_name" >/dev/null
}

if [[ "$SYNC_DEPS" == "1" || ( "$SYNC_DEPS" == "auto" && ! -d "$WEBAPP_DIR/.venv" ) ]]; then
  echo "Syncing Python dependencies with uv..."
  (cd "$WEBAPP_DIR" && uv sync --frozen)
fi

if [[ "$START_SOLR" == "1" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "MCT_START_SOLR=1 requires docker, but docker was not found on PATH." >&2
    exit 1
  fi
  ensure_docker_network "$GATEWAY_NETWORK_NAME"
  echo "Starting Solr with docker compose..."
  (cd "$ROOT_DIR/../../" && docker compose -f docker-compose-dev.yml up -d solr)
fi

if command -v curl >/dev/null 2>&1; then
  if ! curl -fsS "http://${CONCEPT_SEARCH_SERVICE_HOST}:${CONCEPT_SEARCH_SERVICE_PORT}/solr/admin/info/system?wt=json" >/dev/null 2>&1; then
    echo "Warning: Solr did not respond at http://${CONCEPT_SEARCH_SERVICE_HOST}:${CONCEPT_SEARCH_SERVICE_PORT}/solr" >&2
    echo "         Concept search/model setup may fail until Solr is running." >&2
  fi
fi

mkdir -p "$API_DIR/static"
cat > "$API_DIR/static/config.json" <<EOF
{
  "USE_OIDC": "${USE_OIDC:-0}"
}
EOF

if [[ "$RUN_MIGRATIONS" == "1" ]]; then
  echo "Applying migrations to local DB..."
  run_manage migrate --noinput
fi

if [[ "$BOOTSTRAP_ADMIN" == "1" ]]; then
  echo "Ensuring local debug admin user exists..."
  MCT_ADMIN_USERNAME="$ADMIN_USERNAME" \
  MCT_ADMIN_EMAIL="$ADMIN_EMAIL" \
  MCT_ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  MCT_RESET_ADMIN_PASSWORD="$RESET_ADMIN_PASSWORD" \
    run_manage shell -c "
import os
from django.contrib.auth import get_user_model

User = get_user_model()
username = os.environ['MCT_ADMIN_USERNAME']
email = os.environ['MCT_ADMIN_EMAIL']
password = os.environ['MCT_ADMIN_PASSWORD']
reset_password = os.environ.get('MCT_RESET_ADMIN_PASSWORD', '1') == '1'

user, created = User.objects.get_or_create(username=username, defaults={'email': email})
user.email = user.email or email
user.is_active = True
user.is_staff = True
user.is_superuser = True
if created or reset_password:
    user.set_password(password)
user.save()
print(f'Local debug admin ready: {username} / {password if reset_password else \"<existing password>\"}')
"
fi

if [[ "$BOOTSTRAP_GROUP" == "1" ]]; then
  echo "Ensuring default user_group exists..."
  (cd "$API_DIR" && uv run python manage.py shell < "$WEBAPP_DIR/scripts/create_group.py")
fi

case "$MODE" in
  bootstrap)
    echo "Local bootstrap complete."
    ;;
  shell)
    run_manage shell
    ;;
  worker)
    echo "Starting local background-task worker..."
    run_manage process_tasks --log-std
    ;;
  server)
    echo "Starting local Django debug server at http://127.0.0.1:${PORT}/"
    echo "Login: ${ADMIN_USERNAME} / ${ADMIN_PASSWORD}"
    run_manage runserver "${HOST}:${PORT}"
    ;;
esac
