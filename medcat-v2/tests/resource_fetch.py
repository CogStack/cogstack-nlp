import os
import pooch
import importlib

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_CENTRAL_RESOURCES = os.path.join(_REPO_ROOT, 'medcat-test-models')


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


def get_resource(relative_path: str) -> str:
    """
    Returns a local path to the requested test resource.
    Prefers the central repo location (medcat-test-models/) if available,
    falls back to downloading from the corresponding release via pooch.
    """
    central_path = os.path.join(_CENTRAL_RESOURCES, relative_path)

    if os.path.exists(central_path):
        return central_path

    version = _get_version()
    return _download_resource(version, relative_path)
