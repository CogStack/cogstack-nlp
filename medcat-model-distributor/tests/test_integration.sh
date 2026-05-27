#!/usr/bin/env bash
# =============================================================================
# Integration test: build → seed DB → call auth-callback-api → verify
# =============================================================================
# Usage:
#   ./integration_test.sh --model-file /path/to/model.zip [OPTIONS]
#
# Options:
#   --model-file PATH       (required) Path to the MedcatModel file on the HOST
#   --model-name NAME       Model name stored in DB (default: test_model)
#   --model-display NAME    Model display name (default: Test Model)
#   --model-desc TEXT       Model description (default: Integration test model)
#   --api-key-id IDENTIFIER APIKey identifier label (default: integration-test)
#   --compose-file PATH     Path to docker-compose file (default: docker-compose.yml)
#   --service NAME          Django service name in compose file (default: web)
#   --port PORT             Host port the app is mapped to (default: 8000)
#   --base-url URL          Override full base URL (default: http://localhost:PORT)
#   --app-label LABEL       Django app label for model imports (default: yourapp)
#   --keep-up               Don't tear down containers after the test
#   --help                  Show this message
# =============================================================================
set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
MODEL_FILE=""
MODEL_NAME="test_model"
MODEL_DISPLAY_NAME="Test Model"
MODEL_DESCRIPTION="Integration test model"
API_KEY_IDENTIFIER="integration-test"
COMPOSE_FILE="docker-compose-test.yml"
SERVICE="medcatweb"
PORT="8000"
BASE_URL=""
KEEP_UP=false
WORKDIR="/webapp"

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
die()   { error "$*"; exit 1; }
step()  { echo -e "\n${BOLD}=== $* ===${NC}"; }

# ── Argument parsing ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --model-file)    MODEL_FILE="$2";          shift 2 ;;
        --model-name)    MODEL_NAME="$2";          shift 2 ;;
        --model-display) MODEL_DISPLAY_NAME="$2";  shift 2 ;;
        --model-desc)    MODEL_DESCRIPTION="$2";   shift 2 ;;
        --api-key-id)    API_KEY_IDENTIFIER="$2";  shift 2 ;;
        --compose-file)  COMPOSE_FILE="$2";        shift 2 ;;
        --service)       SERVICE="$2";             shift 2 ;;
        --port)          PORT="$2";                shift 2 ;;
        --base-url)      BASE_URL="$2";            shift 2 ;;
        --keep-up)       KEEP_UP=true;             shift   ;;
        --help)
            sed -n '/^# Usage:/,/^# =====/p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) die "Unknown argument: $1" ;;
    esac
done

# ── Validate ───────────────────────────────────────────────────────────────────
[[ -z "$MODEL_FILE" ]]     && die "--model-file is required"
[[ ! -f "$MODEL_FILE" ]]   && die "Model file not found: $MODEL_FILE"
[[ ! -f "$COMPOSE_FILE" ]] && die "Compose file not found: $COMPOSE_FILE"

MODEL_FILE_ABS="$(realpath "$MODEL_FILE")"
MODEL_FILE_DIR="$(dirname "$MODEL_FILE_ABS")"
MODEL_FILE_BASENAME="$(basename "$MODEL_FILE_ABS")"
[[ -z "$BASE_URL" ]] && BASE_URL="http://localhost:${PORT}"

info "Model file  : $MODEL_FILE_ABS"
info "Compose file: $COMPOSE_FILE  (service: $SERVICE)"
info "Base URL    : $BASE_URL"

# ── Cleanup trap ───────────────────────────────────────────────────────────────
cleanup() {
    local exit_code=$?
    if [[ "$KEEP_UP" == false ]]; then
        info "Tearing down containers..."
        docker compose -f "$COMPOSE_FILE" down -v --remove-orphans 2>/dev/null || true
    else
        warn "--keep-up specified; containers left running."
    fi
    if [[ $exit_code -ne 0 ]]; then
        echo -e "\n${RED}${BOLD}Integration test FAILED ✗${NC}"
    fi
    exit $exit_code
}
trap cleanup EXIT

# =============================================================================
# STEP 1 – Build and start the stack
# =============================================================================
step "STEP 1 – Build & start containers"

docker compose -f "$COMPOSE_FILE" up -d --build

# Wait until the health endpoint (or root) responds with any HTTP status.
info "Waiting for app to be reachable at ${BASE_URL}/health (max 90s)..."
MAX_WAIT=90; WAITED=0
until curl -sf --max-time 3 "${BASE_URL}/health" -o /dev/null 2>/dev/null; do
    if [[ $WAITED -ge $MAX_WAIT ]]; then
        error "App did not become ready within ${MAX_WAIT}s. Service logs:"
        docker compose -f "$COMPOSE_FILE" logs --tail 50 "$SERVICE"
        die "Aborting."
    fi
    sleep 3; WAITED=$((WAITED + 3))
done
info "App is ready (${WAITED}s elapsed)"

# =============================================================================
# STEP 2 – Find the model file inside the container
# =============================================================================
step "STEP 2 – Locate model file inside container"

# Attempt auto-detection
DETECTED_PATH="$(docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" find / -name "$MODEL_FILE_BASENAME" -not -path "/proc/*" -not -path "/sys/*" -print -quit 2>/dev/null | tr -d '\r')"

if [[ -n "$DETECTED_PATH" ]]; then
    CONTAINER_MODEL_PATH="$DETECTED_PATH"
else
    # This is the crucial part: Hardcode where your app lives in the Docker image
    # Assuming your Dockerfile puts the code in /webapp
    warn "Auto-detection failed. Using known container path..."
    CONTAINER_MODEL_PATH="/webapp/$MODEL_FILE_BASENAME"
fi

info "Container model path: ${CONTAINER_MODEL_PATH}"

# =============================================================================
# STEP 3 – Seed: MedcatModel + APIKey via manage.py shell
# =============================================================================
step "STEP 3 – Seed database"

# get container ID
CONTAINER=$(docker compose -f "$COMPOSE_FILE" ps -q "$SERVICE")

# copy setup file to container
docker cp tests/setup/setup_in_container.py "$CONTAINER":$WORKDIR/seed_script.py

# We capture stdout only for the API key; all other output goes to stderr.
API_KEY_VALUE="$(
    docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE" \
        python3 $WORKDIR/seed_script.py "$CONTAINER_MODEL_PATH" "$MODEL_NAME" "$MODEL_DISPLAY_NAME" "$MODEL_DESCRIPTION" "$API_KEY_IDENTIFIER"
)"

[[ -z "$API_KEY_VALUE" ]] && die "could not get API key value"
info "APIKey value (first 10 chars): ${API_KEY_VALUE:0:10}..."

# =============================================================================
# STEP 4 – Call the protected endpoint
# =============================================================================
step "STEP 4 – Call manual-api-callback"

AUTH_URL="${BASE_URL}/manual-api-callback/?api_key=${API_KEY_VALUE}"
info "GET ${AUTH_URL}"

# -D - : dump response headers to stdout; we parse status from them
HTTP_RESPONSE_FILE="$(mktemp)"
HTTP_STATUS="$(
    curl -s -o "$HTTP_RESPONSE_FILE" \
         -w "%{http_code}" \
         --max-time 15 \
         "${AUTH_URL}"
)"
HTTP_BODY="$(cat "$HTTP_RESPONSE_FILE")"
rm -f "$HTTP_RESPONSE_FILE"

info "HTTP status: ${HTTP_STATUS}"

# =============================================================================
# STEP 5 – Verify the response
# =============================================================================
step "STEP 5 – Verify response"

python3 tests/verification/verify_response.py "${HTTP_STATUS}" "${MODEL_DISPLAY_NAME}" "${HTTP_BODY}"

echo -e "\n${GREEN}${BOLD}Integration test PASSED ✓${NC}"