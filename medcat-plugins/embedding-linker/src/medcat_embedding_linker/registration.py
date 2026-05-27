import logging

from medcat.components.types import CoreComponentType
from medcat.components.types import lazy_register_core_component


logger = logging.getLogger(__name__)


def do_registration():
    lazy_register_core_component(
        CoreComponentType.linking,
        "embedding_linker",
        "medcat_embedding_linker.embedding_linker",
        "Linker.create_new_component",
    )
    lazy_register_core_component(
        CoreComponentType.linking,
        "trainable_embedding_linker",
        "medcat_embedding_linker.trainable_embedding_linker",
        "Linker.create_new_component",
    )
