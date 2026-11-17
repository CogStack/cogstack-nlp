import os

from medcat.components.types import CoreComponentType
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config import Config

from medcat_llm_components.ner import LLMNERConfig
from medcat_llm_components.linker import LLMLinkConfig

from medcat_llm_components.pure_llm_linker import PureLLMLinkConfig
import pytest


DEFAULT_BASE_URL = "my_ollama_ip:port/whatever"
DEFAULT_MODEL = "gemma:2b"
DEFAULT_PROMPT_NER = "Never gonna give you up: %s"
DEFAULT_PROMPT_LINKER = "Never gonna let you go"


def create_new_llm_model(
    default_ner: bool = False,
    use_pure_llm_linker: bool = False,
):

    # the URL to the (e.g) ollama instance
    base_url = DEFAULT_BASE_URL
    # the model to use
    llm_model = DEFAULT_MODEL

    # create configs
    # ner
    ner_cnf = LLMNERConfig(
        base_url=base_url,
        model=llm_model,
        prompt=DEFAULT_PROMPT_NER,
    )
    # linker
    l_cnf_cls = PureLLMLinkConfig if use_pure_llm_linker else LLMLinkConfig
    linking_cnf = l_cnf_cls(
        base_url=base_url,
        model=llm_model,
        prompt=DEFAULT_PROMPT_LINKER,
    )

    config = Config()
    if not default_ner:
        config.components.ner.comp_name = "llm_ner"
        config.components.ner.custom_cnf = ner_cnf
    config.components.linking.comp_name = (
        "pure_llm_linker" if use_pure_llm_linker else "llm_linker")
    config.components.linking.additional = linking_cnf

    vocab = Vocab()
    # or load a CDB on its own with CDB.load("my_cdb.zip")
    cdb = CDB(config)

    cat = CAT(cdb, vocab)
    print(cat.describe_pipeline())
    return cat


@pytest.fixture
def llm_cat():
    return create_new_llm_model()


def test_can_save(llm_cat, tmpdir):
    mpp = llm_cat.save_model_pack(str(tmpdir))
    assert tmpdir.listdir()
    assert os.path.exists(mpp)


def test_can_save_and_load(llm_cat, tmpdir):
    mpp = llm_cat.save_model_pack(str(tmpdir))
    cat = CAT.load_model_pack(mpp)
    assert cat
    assert isinstance(cat, CAT)
    assert_has_correct_components(cat)
    assert_has_correct_config_opts(cat)


def assert_has_correct_components(cat: CAT):
    # just names
    assert cat.config.components.ner.comp_name == 'llm_ner'
    assert cat.config.components.linking.comp_name == "llm_linker"
    # actual types
    ner = cat.pipe.get_component(CoreComponentType.ner)
    linker = cat.pipe.get_component(CoreComponentType.linking)
    assert "LLM" in str(type(ner))
    assert "LLM" in str(type(linker))


def assert_has_correct_config_opts(cat: CAT):
    ner_cnf = cat.config.components.ner.custom_cnf
    linking_cnf = cat.config.components.linking.additional
    assert isinstance(ner_cnf, LLMNERConfig)
    assert isinstance(linking_cnf, LLMLinkConfig)
    assert ner_cnf.base_url == DEFAULT_BASE_URL
    assert linking_cnf.base_url == DEFAULT_BASE_URL
    assert ner_cnf.model == DEFAULT_MODEL
    assert linking_cnf.model == DEFAULT_MODEL
    assert ner_cnf.prompt == DEFAULT_PROMPT_NER
    assert linking_cnf.prompt == DEFAULT_PROMPT_LINKER
