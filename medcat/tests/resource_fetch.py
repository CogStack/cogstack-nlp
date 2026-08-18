# NOTE: this file is designed to be copied across the following sub-folders
#         1. medcat-v2/tests/resource_fetch.py
#         2. medcat-den/tests/resource_fetch.py
#       So if you make changes here, copy them over to the others as well.
#
#       NB! This does mean we have duplicate code. But to me the alternatives
#           are note better:
#            a) keep and install a separate local project - not portable
#            b) publish and install from PyPI - extra maintenance burden


import os
import pooch
import importlib
from enum import Enum


_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_CENTRAL_RESOURCES = os.path.join(_REPO_ROOT, 'medcat-test-models')

class DefinedResource(Enum):
    v1_model = "mct_v1_model_pack.zip"
    v2_model = "mct2_model_pack.zip"


def _get_version(project_name: str = 'medcat') -> str:
    # NOTE: plan to use this for medcat-den as well
    try:
        pkg = importlib.import_module(project_name)
        ver = getattr(pkg, '__version__')
        if ver is None:
            raise
        return "%2F".join((project_name, f"v{ver}"))
    except ImportError:
        raise RuntimeError(
            f"Could not determine version for '{project_name}'. "
            f"Is the package installed?"
        )


def _download_resource(version: str, relative_path: str) -> str:
    url = f"https://github.com/CogStack/cogstack-nlp/releases/download/{version}/{relative_path}"
    try:
        return pooch.retrieve(
            url=url,
            known_hash=None,
            path=pooch.os_cache('medcat_tests'),
            fname=relative_path,
        )
    except Exception as e:
        raise FileNotFoundError(
            f"Test resource '{relative_path}' not found locally in '{_CENTRAL_RESOURCES}' "
            f"and could not be fetched from release {version!r}. "
            f"If developing locally, ensure 'medcat-test-models/' exists at the repo root. "
            f"Original error: {e}"
        ) from e


def get_resource(relative_path: str | DefinedResource, project_name: str = 'medcat') -> str:
    """
    Returns a local path to the requested test resource.
    Prefers the central repo location (medcat-test-models/) if available,
    falls back to downloading from the corresponding release via pooch.
    """
    # allow passing string version of defined resoure (e.g v1_model)
    try:
        relative_path = DefinedResource[relative_path]
    except KeyError:
        pass  # treat as a literal path
    if isinstance(relative_path, DefinedResource):
        relative_path = relative_path.value
    central_path = os.path.join(_CENTRAL_RESOURCES, relative_path)

    if os.path.exists(central_path):
        return central_path

    version = _get_version(project_name)
    return _download_resource(version, relative_path)
