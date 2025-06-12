from medcat.utils.import_utils import ensure_optional_extras_installed
import medcat

from .meta_cat import MetaCAT, MetaCATAddon


__all__ = ["MetaCAT", "MetaCATAddon"]

# NOTE: the _ is converted to - automatically
_EXTRA_NAME = "meta-cat"


ensure_optional_extras_installed(medcat.__name__, _EXTRA_NAME)
