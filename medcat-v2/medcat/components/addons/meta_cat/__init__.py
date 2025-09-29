from medcat.utils.import_utils import ensure_optional_extras_installed
import medcat

_EXTRA_NAME = "meta-cat"
ensure_optional_extras_installed(medcat.__name__, _EXTRA_NAME)

# NOTE: need to check above before local imports, otherwise there's no
#       point since the imports below will have already failed

from .meta_cat import (MetaCAT, MetaCATAddon,  # noqa
                       get_meta_annotations, MetaAnnotationValue)


__all__ = ["MetaCAT", "MetaCATAddon",
           "get_meta_annotations", "MetaAnnotationValue"]

# NOTE: the _ is converted to - automatically
