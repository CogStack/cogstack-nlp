#!/bin/bash

set -euo pipefail

usage() {
    echo "Usage: $0 <version> [--manual] [--dry-run] [--force] [<cherry-pick-hash> ...]"
    exit 1
}

error_exit() {
    echo "Error: $1" >&2
    exit 1
}

run_or_echo() {
    if $DRY_RUN; then
        echo "+ $*"
    else
        eval "$*"
    fi
}

# Argument parsing
if [[ $# -lt 1 ]]; then
    usage
fi

VERSION="$1"
shift

MANUAL=false
DRY_RUN=false
FORCE=false
CHERRYPICK_HASHES=()

while (( "$#" )); do
    case "$1" in
        --manual) MANUAL=true; shift ;;
        --dry-run) DRY_RUN=true; shift ;;
        --force) FORCE=true; shift ;;
        *) CHERRYPICK_HASHES+=("$1"); shift ;;
    esac
done

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: version '$VERSION' must be in format X.Y.Z"
    exit 1
fi

# Extract version components
VERSION_MAJOR_MINOR="${VERSION%.*}"
VERSION_PATCH="${VERSION##*.}"
RELEASE_BRANCH="release/$VERSION_MAJOR_MINOR"

# some prerequisites
[[ "$VERSION_PATCH" == "0" ]] && error_exit "Patch version must not be 0."

run_or_echo git fetch origin

if ! git show-ref --verify --quiet "refs/remotes/origin/$RELEASE_BRANCH"; then
    error_exit "Release branch '$RELEASE_BRANCH' does not exist remotely."
fi

if git rev-parse "v$VERSION" >/dev/null 2>&1 && ! $FORCE; then
    error_exit "Tag 'v$VERSION' already exists. Use --force to override."
fi

if [[ -n "$(git status --porcelain)" && ! $FORCE ]]; then
    error_exit "Working directory is not clean. Please commit or stash your changes."
fi

# move to release branch
run_or_echo git checkout "$RELEASE_BRANCH"
run_or_echo git pull origin "$RELEASE_BRANCH"

# if `--manual` allow user to make their changes
if $MANUAL; then
    echo "Manual mode: Please cherry-pick your commits and bump the version manually."
    echo
    echo "Suggested commands:"
    echo "  git cherry-pick <hash>"
    echo "  sed -i 's/version = \".*\"/version = \"$VERSION\"/' pyproject.toml"
    echo "  git add pyproject.toml"
    echo "  git commit -m 'Bump version to $VERSION'"
    echo "  git tag -a v$VERSION -m 'Release v$VERSION'"
    echo "  git push origin $RELEASE_BRANCH"
    echo "  git push origin v$VERSION"
    exit 0
fi

# do the cherry-picking
for HASH in "${CHERRYPICK_HASHES[@]}"; do
    run_or_echo git cherry-pick "$HASH" || error_exit "Failed to cherry-pick $HASH."
done

# Update version in pyproject.toml
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS (BSD sed)
    run_or_echo sed -i \'\' \'s/^version = \".*\"/version = \"\'$VERSION\'\"/\' pyproject.toml
else
    # Linux (GNU sed)
    run_or_echo sed -i \'s/^version = \".*\"/version = \"\'$VERSION\'\"/\' pyproject.toml
fi

# add and commit changes
run_or_echo git add pyproject.toml
run_or_echo git commit -m \"Bump version to $VERSION\" --allow-empty

# now do the tagging
# NOTE: can force since without the `--force` flag we would have checked
#       for existing tag
run_or_echo git tag -a \"v$VERSION\" -m \"Release v$VERSION\" --force
run_or_echo git push origin \"$RELEASE_BRANCH\"
run_or_echo git push origin \"v$VERSION\" --force

run_or_echo git checkout main

