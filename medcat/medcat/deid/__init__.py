from medcat.utils.import_utils import (
    ensure_optional_extras_installed as __ensure_deid)

__ensure_deid("medcat", "deid")

from medcat.components.ner.trf.deid import DeIdModel  # noqa

__all__ = ["DeIdModel"]
