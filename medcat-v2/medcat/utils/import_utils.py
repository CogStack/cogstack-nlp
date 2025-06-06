import importlib.util
import importlib.metadata

import re

_DEP_PATTERN = re.compile(r"^([\w-]+)[<>=~;!].*")


class KeyDefaultDict(dict):
    def __missing__(self, key):
        return key


# Map the project name to the package needed to be imported where appropraite.
# Default to the package name itself.
_DEP_NAME_MAPPER = KeyDefaultDict({
    "pyahocorasick": "ahocorasick"
})


def get_all_extra_deps_raw(package_name: str) -> list[str]:
    """Get all the dependencies for a pcakge that are for an extra component.

    The output will include extra information such as the extra it's tied to.

    Args:
        package_name (str): The package name.

    Raises:
        ValueError: If the package isn't installed.

    Returns:
        list[str]: The list of extra dependencies, including extra information.
    """
    try:
        dependencies = importlib.metadata.requires(package_name)
        if dependencies is None:
            return []
    except importlib.metadata.PackageNotFoundError:
        raise ValueError(f"Package '{package_name}' is not installed")
    return [dep for dep in dependencies
            if "extra == " in dep]


def get_required_extra_deps(package_name: str, extra_name: str) -> list[str]:
    """Get the extra dependencies required for this extra part.

    Args:
        package_name (str): The package name.
        extra_name (str): The extra name.

    Returns:
        list[str]: All the required extra dependencies for this part.
    """
    dependencies = get_all_extra_deps_raw(package_name)
    return [
        # just package name
        _DEP_PATTERN.match(dep).group(1)  # type: ignore
        for dep in dependencies
        # check that this is an extra related to this name
        if (f"extra == '{extra_name}'" in dep
            or f'extra == "{extra_name}"' in dep)
    ]


def get_installed_extra_dependencies(package_name: str, extra_name: str
                                     ) -> list[str]:
    """Get installed dependencies for a given package's extra parts.

    Args:
        package_name (str): The package name.

    Returns:
        list[str]: The list of extra packages installed.
    """
    extra_deps = get_required_extra_deps(package_name, extra_name)
    return [dep for dep in extra_deps
            if importlib.util.find_spec(_DEP_NAME_MAPPER[dep]) is not None]


def ensure_optional_extras_installed(package_name: str, extra_name: str):
    """Ensure that an optional dependency set is installed.

    Args:
        package_name (str): The base package name.
        extra_name (str): The name of the extra dependency.

    Raises:
        MissingDependenciesError: If the extra dependency isn't provided.
    """
    installed = get_installed_extra_dependencies(package_name, extra_name)
    if not installed:
        req = get_required_extra_deps(package_name, extra_name)
        if not req:
            raise IncorrectExtraComponent(package_name, extra_name)
        missing = [requirement for requirement in req
                   if requirement not in installed]
        raise MissingDependenciesError(package_name, extra_name, missing)


class IncorrectExtraComponent(Exception):

    def __init__(self, package_name: str, extra_name: str):
        super().__init__(f"The '{extra_name}' part does not exist in as"
                         f"an optional part in {package_name} "
                         "(or does not define dependencies)")
        self.package_name = package_name
        self.extra_name = extra_name


class MissingDependenciesError(Exception):
    """Custom exception for missing optional dependencies."""

    def __init__(self, package_name: str, extra_name: str,
                 missing: list[str]):
        super().__init__(f"The optional dependency set '{extra_name}' "
                         f"is missing for {package_name}. The list of "
                         f"missing dependencies: {missing}. "
                         "If this came up when using the package, you need "
                         "to install the optional dependency alongside the "
                         "package. For instance, you can use "
                         f"`pip install {package_name}[{extra_name}]`. "
                         "PS: If you require multiple extras, you need to "
                         "specify them all ans separate by comma, e.g "
                         "`pkg[add1,add2]`")
        self.package_name = package_name
        self.extra_name = extra_name
        self.missing = missing
