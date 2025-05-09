#!/usr/bin/env bash
set -euo pipefail
# the path to folder of this script
# so we can run the others through this one
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    echo "Usage: $0 <version> [--manual] [--dry-run] [--force] [<cherry-pick-hash> ...]"
    echo
    echo "Examples:"
    echo "  $0 0.4.0"
    echo "  $0 0.4.2 abc123 def456"
    echo "  $0 0.4.2 --manual"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi


VERSION=""
EXTRA_FLAGS=()
CHERRY_PICK_HASHES=()

# --- Parse args ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run|--force|--manual)
            EXTRA_FLAGS+=("$1")
            shift
            ;;
        -*)
            echo "Unknown flag: '$1'" >&2
            usage
            ;;
        *)
            if [[ -z "$VERSION" ]]; then
                VERSION="$1"
            else
                CHERRY_PICK_HASHES+=("$1")
            fi
            shift
            ;;
    esac
done


if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: version '$VERSION' must be in format X.Y.Z"
    exit 1
fi

IFS='.' read -r MAJOR MINOR PATCH <<< "$VERSION"

if [[ "$PATCH" == "0" ]]; then
    cmd=("$SCRIPT_DIR/prepare_minor_release.sh" "$VERSION")
    if [[ ${#EXTRA_FLAGS[@]} -gt 0 ]]; then
        cmd+=("${EXTRA_FLAGS[@]}")
    fi
    echo "Preparing minor release $VERSION"
else
    cmd=("$SCRIPT_DIR/prepare_patch_release.sh" "$VERSION")
    # Add extra flags only if they exist
    if [[ ${#EXTRA_FLAGS[@]} -gt 0 ]]; then
        cmd+=("${EXTRA_FLAGS[@]}")
    fi
    # Add cherry pick hashes only if they exist
    if [[ ${#CHERRY_PICK_HASHES[@]} -gt 0 ]]; then
        cmd+=("${CHERRY_PICK_HASHES[@]}")
    fi
    echo "Preparing patch release $VERSION"
fi
bash "${cmd[@]}"
