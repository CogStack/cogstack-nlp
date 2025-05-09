#!/usr/bin/env bash
set -euo pipefail

trap 'echo "Error on line $LINENO"' ERR

VERSION="$1"
shift

# Collect optional flags
DRY_RUN=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true ;;
        --force) FORCE=true ;;
        *) echo "Unknown argument: '$1'" >&2; exit 1 ;;
    esac
    shift
done

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: version '$VERSION' must be in format X.Y.Z"
    exit 1
fi

# Extract version components
VERSION_MAJOR_MINOR="${VERSION%.*}"
VERSION_PATCH="${VERSION##*.}"
RELEASE_BRANCH="release/$VERSION_MAJOR_MINOR"

# Helpers
run_or_echo() {
    if $DRY_RUN; then echo "+ $*"; else eval "$*"; fi
}

error_exit() {
    echo "Error: $1" >&2
    exit 1
}

# Preconditions
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [[ "$current_branch" != "main" && $FORCE == false ]]; then
    error_exit "Must be on 'main' branch to create a minor release. Use --force to override."
fi

if [[ "$VERSION_PATCH" != "0" ]]; then
    error_exit "Patch version must be 0 for a minor release. Got: $VERSION_PATCH"
fi

if git show-ref --quiet "refs/heads/$RELEASE_BRANCH" && [[ $FORCE == false ]]; then
    error_exit "Branch '$RELEASE_BRANCH' already exists. Use --force to override."
fi

if git show-ref --quiet "refs/tags/v$VERSION" && [[ $FORCE == false ]]; then
    error_exit "Tag 'v$VERSION' already exists. Use --force to override."
fi

if [[ -n "$(git status --porcelain)" ]]; then
    error_exit "Working directory not clean. Commit or stash changes first."
fi

# Create release branch
# NOTE: will overwrite release branch if --force is specified
run_or_echo git checkout -B "$RELEASE_BRANCH"

# Update version in pyproject.toml
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS (BSD sed)
    run_or_echo sed -i \'\' \'s/^version = \".*\"/version = \"\'$VERSION\'\"/\' pyproject.toml
else
    # Linux (GNU sed)
    run_or_echo sed -i \'s/^version = \".*\"/version = \"\'$VERSION\'\"/\' pyproject.toml
fi

run_or_echo git add pyproject.toml
run_or_echo git commit -m \"Bump version to $VERSION for release\"

# Create and push tag
run_or_echo git tag -a \"v$VERSION\" -m \"Release v$VERSION\"
run_or_echo git push origin \"$RELEASE_BRANCH\"
run_or_echo git push origin \"v$VERSION\"

run_or_echo git checkout main
