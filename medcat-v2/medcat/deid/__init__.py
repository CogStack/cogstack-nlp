from medcat.utils.import_utils import (
    ensure_optional_extras_installed as __ensure_deid)

__ensure_deid("medcat", "deid")

from medcat.components.trf.deid import DeIDModel  # noqa

__all__ = ["DeIDModel"]
