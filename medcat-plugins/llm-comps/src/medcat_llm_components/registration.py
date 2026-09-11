import logging

from medcat.components.types import CoreComponentType, lazy_register_core_component

logger = logging.getLogger(__name__)


def do_registration():
    lazy_register_core_component(
        CoreComponentType.ner, "llm_ner",
        "medcat_llm_components.ner", "LLMNER.create_new_component")
    lazy_register_core_component(
        CoreComponentType.linking, "llm_linker",
        "medcat_llm_components.linker", "LLMLinker.create_new_component")
