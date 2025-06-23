import platform
import logging
import importlib.metadata
import re
from sys import version_info as cur_ver_info

from pydantic import BaseModel

from medcat.storage.serialisables import AbstractSerialisable


logger = logging.getLogger(__name__)


DEP_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\-_]+')
PY_VER_PATTERN = re.compile(
    r""".*?python_version\s*(==|!=|<=|>=|<|>)\s*(['"])([^'"]+)\2""")


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


def _is_relevant(req_name_and_ver: str) -> bool:
    if 'extra' in req_name_and_ver:
        return False
    ver_match = PY_VER_PATTERN.match(req_name_and_ver)
    if ver_match:
        comp = ver_match.group(1)
        ver_nums = ver_match.group(3).split(".")
        exp_ver = (int(ver_nums[0]), int(ver_nums[1]))
        cur_ver = cur_ver_info.major, cur_ver_info.minor
        # eg. 3.10 < 3.11
        to_eval = f"{cur_ver} {comp} {exp_ver}"
        return bool(eval(to_eval))
    return True


def _update_installed_dependencies_recursive(
        gathered: dict[str, str],
        package: importlib.metadata.Distribution) -> dict[str, str]:
    pkg_name = package.metadata["Name"].lower()
    # print("Looking at", repr(pkg_name))
    if pkg_name in gathered:
        logger.debug("Trying to update already found transitive dependency "
                     "'%'", pkg_name)
        return gathered
    requirements = package.requires
    if not requirements:
        return gathered
    for req_name_and_ver in requirements:
        req_name_cs = DEP_NAME_PATTERN.match(req_name_and_ver).group(0)  # type: ignore
        req_name = req_name_cs.lower()
        # to avoid recursion issues
        gathered[req_name] = None  # type: ignore
        try:
            dep = importlib.metadata.distribution(req_name)
        except importlib.metadata.PackageNotFoundError as e1:
            # try case sensitive as well
            try:
                dep = importlib.metadata.distribution(req_name_cs)
            except importlib.metadata.PackageNotFoundError:
                if _is_relevant(req_name_and_ver):
                    logger.warning(
                        "Unable to locate requirement '%s' ('%s'):",
                        req_name, req_name_and_ver, exc_info=e1)
                gathered.pop(req_name)
                continue
        _update_installed_dependencies_recursive(gathered, dep)
        gathered[req_name] = dep.version
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
        package = importlib.metadata.distribution(dep)
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
    for package in importlib.metadata.distributions():
        req_name = package.metadata["Name"].lower()
        if req_name not in direct_deps:
            continue
        installed_packages[req_name] = package.version
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
