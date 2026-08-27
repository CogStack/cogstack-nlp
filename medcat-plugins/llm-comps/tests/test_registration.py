import pytest

from medcat.components.types import CoreComponentType, create_core_component, CoreComponent
from medcat.config.config import Linking, Ner
from medcat_llm_components.ner import LLMNERConfig
from medcat_llm_components.linker import LLMLinkConfig


BASE_CNF_OPTS = {
    "base_url": "https://www.example.com",
    "model": "this-model-does-not-exist",
}


COMP_CREATORS = [
    # NOTE: for now, the args are just None all around
    (CoreComponentType.ner, 'llm_ner', (Ner(
        custom_cnf=LLMNERConfig(**BASE_CNF_OPTS),
    ), None, None, None, None)),
    (CoreComponentType.linking, 'llm_linker', (Linking(
        additional=LLMLinkConfig(**BASE_CNF_OPTS),
    ), None, None, None, None)),
]


@pytest.mark.parametrize("comp_type,comp_name,args", COMP_CREATORS)
def test_has_registered_components(
    comp_type: CoreComponentType, comp_name: str, args: list
):
    comp = create_core_component(comp_type, comp_name, *args)
    assert comp


@pytest.mark.parametrize("comp_type,comp_name,args", COMP_CREATORS)
def test_components_are_core_components(
    comp_type: CoreComponentType, comp_name: str, args: list
):
    comp = create_core_component(comp_type, comp_name, *args)
    assert isinstance(comp, CoreComponent)


@pytest.mark.parametrize("comp_type,comp_name,args", COMP_CREATORS)
def test_components_are_correct_type(
    comp_type: CoreComponentType, comp_name: str, args: list
):
    comp = create_core_component(comp_type, comp_name, *args)
    assert comp.get_type() is comp_type
