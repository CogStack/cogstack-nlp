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

if [[ ! "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+([ab]|rc)?[0-9]*$ ]]; then
    echo "Error: version '$VERSION' must be in format X.Y.Z or X.Y.Z<pre><n> (e.g 2.0.0b0)"
    exit 1
fi
VERSION_TAG="medcat/v$VERSION"

# Extract version components
VERSION_MAJOR_MINOR="${VERSION%.*}"
# work with alpha/beta/rc
VERSION_PATCH="$(echo "$VERSION" | sed -E 's/^[0-9]+\.[0-9]+\.([0-9]+).*/\1/')"
RELEASE_BRANCH="medcat/v$VERSION_MAJOR_MINOR"

# some prerequisites
[[ "$VERSION_PATCH" == "0" ]] && error_exit "Patch version must not be 0."

run_or_echo git fetch origin

if ! git show-ref --verify --quiet "refs/remotes/origin/$RELEASE_BRANCH"; then
    error_exit "Release branch '$RELEASE_BRANCH' does not exist remotely."
fi

if git rev-parse "$VERSION_TAG" >/dev/null 2>&1 && ! $FORCE; then
    error_exit "Tag '$VERSION_TAG' already exists. Use --force to override."
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
    echo "  git tag -a $VERSION_TAG -m 'Release v$VERSION'"
    echo "  git push origin $RELEASE_BRANCH"
    echo "  git push origin $VERSION_TAG"
    exit 0
fi

if $DRY_RUN; then
    echo "Checking for potential cherry-pick conflicts... this would not run in non-dry-run scenarios"

    ORIGINAL_REF=$(git rev-parse --abbrev-ref HEAD)
    git fetch origin "$RELEASE_BRANCH" >/dev/null 2>&1 || error_exit "Could not fetch release branch"
    git checkout --detach "origin/$RELEASE_BRANCH" >/dev/null 2>&1 || error_exit "Could not check out release branch (detached)"

    for HASH in "${CHERRYPICK_HASHES[@]}"; do
        if git cherry-pick --no-commit --no-gpg-sign "$HASH" >/dev/null 2>&1; then
            echo "✓ Commit $HASH should apply cleanly"
        else
            echo "⚠️ Commit $HASH may cause conflicts"
        fi
        git reset --hard HEAD >/dev/null 2>&1
    done

    git checkout "$ORIGINAL_REF" >/dev/null 2>&1 || error_exit "Could not return to original branch"
fi

# do the cherry-picking
for HASH in "${CHERRYPICK_HASHES[@]}"; do
    if ! run_or_echo git cherry-pick "$HASH"; then
        echo "Conflict detected when cherry-picking $HASH."
        echo
        echo "Options:"
        echo "1. Resolve the conflict manually now:"
        echo "   - Edit the conflicted files"
        echo "   - git add <resolved-files>"
        echo "   - git cherry-pick --continue"
        echo
        echo "2. Abort this process and try a different approach:"
        echo "   - git cherry-pick --abort"
        echo "   - Create a separate branch from $RELEASE_BRANCH"
        echo "   - Apply changes manually and commit"
        echo "   - Use the new commit hash with this script"
        echo
        read -p "Do you want to resolve conflicts now? (y/n): " choice
        if [[ "$choice" =~ ^[Yy]$ ]]; then
            echo "Please resolve conflicts (in an editor) and then press Enter to continue..."
            read -r

            # Check if cherry-pick is still in progress
            if [[ -d "$(git rev-parse --git-dir)/CHERRY_PICK_HEAD" ]]; then
                error_exit "Cherry-pick is still in progress. Please complete it before continuing."
            fi
        else
            run_or_echo git cherry-pick --abort
            echo "Cherry-pick aborted. You may want to:"
            echo "1. Create a new branch: git checkout -b fix-for-$RELEASE_BRANCH"
            echo "2. Merge commit manually and resolve conflicts"
            echo "3. Commit: git commit -m 'Backport $HASH to $VERSION_MAJOR_MINOR'"
            echo "4. Run this script again with the new commit hash"
            exit 1
        fi
    fi
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
run_or_echo git tag -a \"$VERSION_TAG\" -m \"Release v$VERSION\" --force
run_or_echo git push origin \"$RELEASE_BRANCH\"
run_or_echo git push origin \"$VERSION_TAG\" --force

run_or_echo git checkout main

