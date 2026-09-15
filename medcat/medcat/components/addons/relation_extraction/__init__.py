from medcat.utils.import_utils import ensure_optional_extras_installed
import medcat


# NOTE: the _ is converted to - automatically
_EXTRA_NAME = "rel-cat"


ensure_optional_extras_installed(medcat.__name__, _EXTRA_NAME)
