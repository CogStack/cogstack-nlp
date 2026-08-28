from medcat.utils.import_utils import ensure_optional_extras_installed
import medcat


_EXTRA_NAME = "spacy"


ensure_optional_extras_installed(medcat.__name__, _EXTRA_NAME)
