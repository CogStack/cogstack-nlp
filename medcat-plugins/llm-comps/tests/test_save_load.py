import os

from medcat.components.types import CoreComponentType
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config import Config

from medcat_llm_components.ner import LLMNERConfig
from medcat_llm_components.linker import LLMLinkConfig

import pytest


def create_new_llm_model():

    # the URL to the (e.g) ollama instance
    base_url = "my_ollama_ip:port/whatever"
    # the model to use
    llm_model = "gemma:2b"

    # create configs
    # ner
    ner_cnf = LLMNERConfig(
        base_url=base_url,
        model=llm_model,
        # for other optional arguments such as prompt
        # refer to code or IDE inspection
    )
    # linker
    linking_cnf = LLMLinkConfig(
        base_url=base_url,
        model=llm_model,
        # for other optional arguments such as prompt
        # refer to code or IDE inspection
    )

    config = Config()
    config.components.ner.comp_name = "llm_ner"
    config.components.ner.custom_cnf = ner_cnf
    config.components.linking.comp_name = "llm_linker"
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


def assert_has_correct_components(cat: CAT):
    # just names
    assert cat.config.components.ner.comp_name == 'llm_ner'
    assert cat.config.components.linking.comp_name == "llm_linker"
    # actual types
    ner = cat.pipe.get_component(CoreComponentType.ner)
    linker = cat.pipe.get_component(CoreComponentType.linking)
    assert "LLM" in str(type(ner))
    assert "LLM" in str(type(linker))
