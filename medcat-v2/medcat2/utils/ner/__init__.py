from medcat2.utils.import_utils import ensure_optional_extras_installed
import medcat2


_EXTRA_NAME = "deid"


ensure_optional_extras_installed(medcat2.__name__, _EXTRA_NAME)
