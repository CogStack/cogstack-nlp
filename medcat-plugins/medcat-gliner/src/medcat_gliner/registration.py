
import logging

from medcat.components.types import CoreComponentType
try:
    from medcat.components.types import lazy_register_core_componet  # type: ignore
    HAS_LAZY = True
except ImportError:
    from medcat.components.types import register_core_component
    HAS_LAZY = False


logger = logging.getLogger(__name__)


def do_registration():
    if HAS_LAZY:
        lazy_register_core_componet(
            CoreComponentType.ner, "gliner_ner",
            "medcat_gliner.gliner_ner", "GlinerNER.create_new_component")
    else:
        logger.warning("Found medcat<2.5 - can't do lazy registration")
        from .gliner_ner import GlinerNER
        register_core_component(
            CoreComponentType.ner, "gliner_ner",
            GlinerNER.create_new_component)
