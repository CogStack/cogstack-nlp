from medcat.version import __version__
from medcat.utils.check_for_updates import (
    check_for_updates as __check_for_updates)

from medcat.plugins import load_plugins as __load_plugins

# NOTE: this will not always actually do the check
#       it will only (by default) check once a week
__check_for_updates("medcat", __version__)

# load / init addons
__load_plugins()
