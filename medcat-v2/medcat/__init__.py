from importlib.metadata import version as __version_method
from importlib.metadata import PackageNotFoundError as __PackageNotFoundError

try:
    __version__ = __version_method("medcat")
except __PackageNotFoundError:
    __version__ = "0.0.0-dev"
