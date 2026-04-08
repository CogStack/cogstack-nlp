# .github/scripts/bump_dependants.py
"""
Bumps the core package version in all dependant projects and opens a PR for each.
Handles both direct and optional/extra dependencies in requirements.txt and pyproject.toml.
Only updates entries using == or ~= specifiers (leaves unpinned or ranged deps alone).
"""

import argparse
import re
import os
import subprocess
import sys
from pathlib import Path

SUPPORTED_SPECIFIERS = ("==", "~=")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True, help="New version, e.g. 1.5.0")
    parser.add_argument("--package", required=True, help="Core package name")
    parser.add_argument("--dependants", nargs="+", required=True, help="Project directories to update")
    return parser.parse_args()


def bump_requirements_txt(path: Path, package: str, new_version: str) -> bool:
    """
    Matches lines like:
      package==1.2.3
      package~=1.2
      package[extra1,extra2]==1.2.3
      package[extra1,extra2]~=1.2
    Leaves unpinned or range-pinned (>=, <=, !=) entries untouched.
    """
    pattern = re.compile(
        rf"^({re.escape(package)}(?:\[[^\]]*\])?)({'|'.join(re.escape(s) for s in SUPPORTED_SPECIFIERS)})[^\s#]+",
        re.MULTILINE,
    )
    original = path.read_text()
    updated, count = pattern.subn(rf"\g<1>~={new_version}", original)
    if count:
        path.write_text(updated)
    return bool(count)


def bump_pyproject_toml(path: Path, package: str, new_version: str) -> bool:
    """
    Matches PEP 508 strings in pyproject.toml, covering:
      - [project] dependencies
      - [project.optional-dependencies] groups
      - [tool.poetry.dependencies] and similar
    e.g. 'your-core-library==1.2.3', 'your-core-library[opt]~=1.2'
    Uses regex rather than a TOML parser to preserve file formatting.
    """
    pattern = re.compile(
        rf'({re.escape(package)}(?:\[[^\]]*\])?)({"|".join(re.escape(s) for s in SUPPORTED_SPECIFIERS)})[^\s,"\']+',
    )
    original = path.read_text()
    updated, count = pattern.subn(rf"\g<1>~={new_version}", original)
    if count:
        path.write_text(updated)
    return bool(count)


def bump_project(project_dir: Path, package: str, new_version: str) -> list[Path]:
    """Returns list of files that were modified."""
    modified = []

    candidates = {
        "requirements.txt": bump_requirements_txt,
        "requirements-dev.txt": bump_requirements_txt,
        "pyproject.toml": bump_pyproject_toml,
    }

    for filename, bump_fn in candidates.items():
        fpath = project_dir / filename
        if fpath.exists() and bump_fn(fpath, package, new_version):
            modified.append(fpath)

    return modified


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def open_pr(branch: str, title: str, body: str, base: str = "main"):
    # Guard against a PR already being open for this branch
    result = subprocess.run(
        ["gh", "pr", "list", "--head", branch, "--json", "number"],
        capture_output=True, text=True, check=True,
    )
    if '"number"' in result.stdout:
        print(f"  PR already open for {branch}, skipping")
        return

    run(["gh", "pr", "create",
         "--title", title,
         "--body", body,
         "--base", base,
         "--head", branch,
         "--label", "dependencies"])


def main():
    args = parse_args()
    package = args.package
    new_version = args.version.removeprefix("v")
    repo_root = Path(__file__).resolve().parents[2]

    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])

    start_ref = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
        ).stdout.strip()
    print(f"Starting ref: {start_ref}")


    for dependant in args.dependants:
        dependant = dependant.strip().removesuffix(os.path.sep).strip()
        print(f"\nProcessing: {dependant}")
        project_dir = repo_root / dependant
        if not project_dir.is_dir():
            print(f"  Directory not found, skipping")
            continue

        modified = bump_project(project_dir, package, new_version)
        if not modified:
            print(f"  No pinned {package} dependency found, skipping")
            continue

        branch = f"chore/bump-{package}-{new_version}-in-{dependant}"
        run(["git", "checkout", "-b", branch])

        for fpath in modified:
            run(["git", "add", str(fpath)])

        run(["git", "commit", "-m", f"chore({dependant}): bump {package} to {new_version}"])
        run(["git", "push", "origin", branch])

        open_pr(
            branch=branch,
            title=f"chore({dependant}): bump {package} to ~={new_version}",
            body=(
                f"Automated minor version bump of `{package}` to `~={new_version}` "
                f"following the upstream release.\n\n"
                f"Files updated:\n"
                + "\n".join(f"- `{f.relative_to(repo_root)}`" for f in modified)
            ),
        )

        run(["git", "checkout", start_ref])

    print("\nDone.")


if __name__ == "__main__":
    sys.exit(main())
