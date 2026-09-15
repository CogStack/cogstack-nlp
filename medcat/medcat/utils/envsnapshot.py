import platform
import logging
import importlib.metadata
import re

from pydantic import BaseModel

from medcat.storage.serialisables import AbstractSerialisable


logger = logging.getLogger(__name__)


DEP_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\-_]+')


def get_direct_dependencies(include_extras: bool) -> list[str]:
    """Gets the direct dependencies of the current package and their versions.

    Args:
        include_extras (bool): Whether to include extras (like spacy).
    """
    # NOTE: __package__ would be medcat.utils in this case
    package = __package__.split('.', 1)[0]
    reqs = importlib.metadata.requires(package)
    if reqs is None:
        raise ValueError("Unable to find package direct dependencies")
    # filter out extras
    if not include_extras:
        reqs = [req for req in reqs
                if "; extra ==" not in req]
    # only keep name, not version
    # NOTE: all correct dependency names will match this regex
    reqs = [DEP_NAME_PATTERN.match(req).group(0).lower()  # type: ignore
            for req in reqs]
    return reqs


def get_transitive_deps(direct_deps: list[str]) -> dict[str, str]:
    """Get the transitive dependencies of the direct dependencies.

    Args:
        direct_deps (list[str]): List of direct dependencies.

    Returns:
        dict[str, str]: The dependency names and their corresponding versions.
    """
    all_deps: dict[str, str] = {}
    to_process = set(direct_deps)
    processed = set()
    # list installed packages for ease of use
    installed_packages = {
        dist.metadata['name'].lower()
        for dist in importlib.metadata.distributions()}

    while to_process:
        package = to_process.pop()
        if package in processed:
            continue

        processed.add(package)

        try:
            dist = importlib.metadata.distribution(package)
        except importlib.metadata.PackageNotFoundError:
            # NOTE: if not installed, we won't bother
            #       after all, if we can save the model, clearly
            #       everything is working
            continue
        requires = dist.requires or []

        for req in requires:
            match = DEP_NAME_PATTERN.match(req)
            if match is None:
                raise ValueError(f"Malformed dependency: {req}")
            dep_name = match.group(0).lower()
            if (dep_name and dep_name not in processed and
                    dep_name in installed_packages):
                all_deps[dep_name] = importlib.metadata.distribution(
                    dep_name).version
                to_process.add(dep_name)

    for direct in direct_deps:
        # remove direct dependencies if they were added
        all_deps.pop(direct, None)
    return all_deps


def get_installed_dependencies(include_extras: bool) -> dict[str, str]:
    """Get the installed packages and their versions.

    Args:
        include_extras (bool): Whether to include extras (like spacy).

    Returns:
        dict[str, str]: All installed packages and their versions.
    """
    direct_deps = get_direct_dependencies(include_extras)
    installed_packages: dict[str, str] = {}
    for package in importlib.metadata.distributions():
        req_name = package.metadata["name"].lower()
        # NOTE: we're checking against the '-' typed package name not
        #       the import name (which will have _ instead)
        req_name_dashes = req_name.replace("_", "-")
        if all(cn not in direct_deps for cn in
               [req_name, req_name_dashes]):
            continue
        installed_packages[req_name] = package.version
    return installed_packages


def is_dependency_installed(dependency: str) -> bool:
    """Checks whether a dependency is installed.

    This takes into account changes such as '-' vs '_'.
    For example, `typing-extensions` is a direct dependency,
    but its module path will be `typing_extension` and that's
    how we can find it as an installed dependency.

    Args:
        dependency (str): The dependency in question.

    Returns:
        bool: Whether the depedency has been installed.
    """
    installed_deps = get_installed_dependencies(True)
    dep_name = dependency.lower()
    dep_name_underscores = dependency.replace("-", "_")
    options = [dep_name, dep_name_underscores]
    return any(option in installed_deps for option in options)


class Environment(BaseModel, AbstractSerialisable):
    dependencies: dict[str, str]
    transitive_deps: dict[str, str]
    os: str
    cpu_arcitecture: str
    python_version: str

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        return list(cls.model_fields)


def get_environment_info(include_transitive_deps: bool = True,
                         include_extras: bool = True) -> Environment:
    """Get the current environment information.

    This includes dependency versions, the OS, the CPU architecture and the
        python version.

    Args:
        include_transitive_deps (bool): Whether to include transitive
            dependencies. Defaults to True.
        include_extras (bool): Whether to include extras (like spacy).
            Defaults to True.

    Returns:
        Environment: The environment.
    """
    deps = get_installed_dependencies(include_extras)
    os = platform.platform()
    cpu_arc = platform.machine()
    py_ver = platform.python_version()
    if include_transitive_deps:
        direct_deps = list(deps.keys())
        trans_deps = get_transitive_deps(direct_deps)
    else:
        trans_deps = {}
    return Environment(dependencies=deps, transitive_deps=trans_deps, os=os,
                       cpu_arcitecture=cpu_arc, python_version=py_ver)
