
import logging

from medcat.components.types import CoreComponentType
from medcat.components.types import lazy_register_core_component


logger = logging.getLogger(__name__)


def do_registration():
    lazy_register_core_component(
        CoreComponentType.ner, "gliner_ner",
        "medcat_gliner.gliner_ner", "GlinerNER.create_new_component")
