from typing import Iterable
import os
import subprocess
import sys
import re
from collections import Counter

MISSING_DEP_PATTERN = re.compile(
    r"The optional dependency set '([\w\-_]*)' is missing")


def walk_packages(path: str,
                  base_pkg_name: str,
                  base_path: str = '') -> Iterable[str]:
    if not base_path:
        base_path = path
    pkg_path = path.removeprefix(base_path).replace(
        os.path.sep, '.').strip(".")
    pkg_to_here = f"{base_pkg_name}.{pkg_path}" if pkg_path else base_pkg_name
    for fn in os.listdir(path):
        cur_path = os.path.join(path, fn)
        if os.path.isdir(cur_path) and (
                not fn.startswith("__") and not fn.endswith("__")):
            yield from walk_packages(cur_path, base_pkg_name=base_pkg_name,
                                     base_path=base_path)
            continue
        if not fn.endswith(".py"):
            continue
        if fn == "__init__.py":
            yield pkg_to_here
            continue
        yield f"{pkg_to_here}.{fn.removesuffix('.py')}"


def find_all_modules(package_name, package_path=None):
    """Find all importable modules in a package."""
    if package_path is None:
        # Import the package to get its path
        try:
            pkg = __import__(package_name)
            package_path = pkg.__path__
        except ImportError:
            print(f"Could not import {package_name}")
            return []

    modules = []
    for modname in walk_packages(package_path[0],
                                 base_pkg_name=package_name):
        modules.append(modname)

    return modules


def test_import(module_name):
    """Test if a module can be imported in isolation."""
    code = f"import {module_name}"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0, result.stderr


def get_missing_dep_set(error: str) -> str | None:
    err1 = error.strip().split('\n')[-1]
    if "MissingDependenciesError" not in err1:
        return None
    matches = MISSING_DEP_PATTERN.findall(err1)
    if len(matches) != 1:
        raise ValueError(f"Unknown error:\n'{error}'\nLookin at:\n{err1}"
                         f"\ngot: {matches}")
    return matches[0]


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_imports.py <package_name>")
        sys.exit(1)

    package_name = sys.argv[1]

    print(f"Finding all modules in {package_name}...")
    modules = find_all_modules(package_name)

    if not modules:
        print(f"No modules found in {package_name}")
        sys.exit(1)

    print(f"Found {len(modules)} modules. Testing imports...\n")

    successful = []
    missing_opt_dep_expl = []
    failed = []

    for module in modules:
        success, error = test_import(module)
        if success:
            successful.append(module)
            print(f"✓ {module}")
        elif (missing_dep := get_missing_dep_set(error)):
            missing_opt_dep_expl.append((module, missing_dep))
            print(f"M {module}: missing {missing_dep}")
        else:
            failed.append((module, error))
            print(f"✗ {module}")
            # Print the first line of error for quick diagnosis
            first_error_line = (
                error.strip().split('\n')[-1] if error else "Unknown error")
            print(f"  → {first_error_line}")

    # Summary
    print("\n" + "="*60)
    per_opt_dep_missing = Counter()
    for _, missing_dep in missing_opt_dep_expl:
        per_opt_dep_missing[missing_dep] += 1
    print(f"Results: {len(successful)} successful, "
          f"{len(missing_opt_dep_expl)} missing optional deps "
          f"({per_opt_dep_missing}), {len(failed)} failed")
    print("="*60)

    if failed:
        print("\nFailed imports:")
        for module, error in failed:
            print(f"\n{module}:")
            print(error)
        sys.exit(1)


if __name__ == "__main__":
    main()
