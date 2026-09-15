import logging

from medcat.components.types import CoreComponentType
from medcat.components.types import lazy_register_core_component


logger = logging.getLogger(__name__)


def do_registration():
    lazy_register_core_component(
        CoreComponentType.ner,
        "transformer_ner",
        "medcat_transformer_ner.transformer_ner",
        "NER.create_new_component",
    )
