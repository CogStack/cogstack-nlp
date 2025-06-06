import pkg_resources
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


def _update_installed_dependencies_recursive(
        gathered: dict[str, str],
        package: pkg_resources.Distribution) -> dict[str, str]:
    if package.project_name.lower() in gathered:
        logger.debug("Trying to update already found transitive dependency "
                     "'%'", package.egg_name)
        return gathered
    for req in package.requires():
        if req.project_name.lower() in gathered:
            logger.debug("Trying to look up already found transitive "
                         "dependency '%'", req.project_name)
            continue  # don't look for it again
        try:
            dep = pkg_resources.get_distribution(req.project_name)
        except pkg_resources.DistributionNotFound as e:
            logger.warning("Unable to locate requirement '%s':",
                           req.project_name, exc_info=e)
            continue
        _update_installed_dependencies_recursive(gathered, dep)
        # do this after so its dependencies get explored
        gathered[dep.project_name.lower()] = dep.version
    return gathered


def get_transitive_deps(direct_deps: list[str]) -> dict[str, str]:
    """Get the transitive dependencies of the direct dependencies.

    Args:
        direct_deps (list[str]): List of direct dependencies.

    Returns:
        dict[str, str]: The dependency names and their corresponding versions.
    """
    # map from name to version so as to avoid multiples of the same package
    all_transitive_deps: dict[str, str] = {}
    for dep in direct_deps:
        package = pkg_resources.get_distribution(dep)
        _update_installed_dependencies_recursive(all_transitive_deps, package)
    return all_transitive_deps


def get_installed_dependencies(include_extras: bool) -> dict[str, str]:
    """Get the installed packages and their versions.

    Args:
        include_extras (bool): Whether to include extras (like spacy).

    Returns:
        dict[str, str]: All installed packages and their versions.
    """
    direct_deps = get_direct_dependencies(include_extras)
    installed_packages: dict[str, str] = {}
    for package in pkg_resources.working_set:
        if package.project_name.lower() not in direct_deps:
            continue
        installed_packages[package.project_name.lower()] = package.version
    return installed_packages


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
