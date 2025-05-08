from medcat2.utils.import_utils import ensure_optional_extras_installed
import medcat2


# NOTE: the _ is converted to - automatically
_EXTRA_NAME = "meta-cat"


ensure_optional_extras_installed(medcat2.__name__, _EXTRA_NAME)
