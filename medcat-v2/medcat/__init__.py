from importlib.metadata import version as __version_method
from importlib.metadata import PackageNotFoundError as __PackageNotFoundError

from medcat.utils.check_for_updates import (
    check_for_updates as __check_for_updates)

from medcat.plugins import load_plugins as __load_plugins

try:
    __version__ = __version_method("medcat")
except __PackageNotFoundError:
    __version__ = "0.0.0-dev"


# NOTE: this will not always actually do the check
#       it will only (by default) check once a week
__check_for_updates("medcat", __version__)

# load / init addons
__load_plugins()
