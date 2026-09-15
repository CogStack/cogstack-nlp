from mock_llm_server import mock_llm_server, VOCAB

from medcat_llm_components.ner import LLMNER, LLMNERConfig
from medcat_llm_components.linker import LLMLinker, LLMLinkConfig

from medcat.components.types import CoreComponentType
from medcat.config.config import Linking, Ner, Config
from medcat.tokenizing.tokenizers import create_tokenizer
from medcat.cdb import CDB
from medcat.preprocessors.cleaners import prepare_name

import pytest
import re


BASE_URL = "http://localhost:8009"


@pytest.fixture
def has_ner_server():
    with mock_llm_server(CoreComponentType.ner):
        yield

@pytest.fixture
def has_linking_server():
    with mock_llm_server(CoreComponentType.linking):
        yield


@pytest.fixture
def ner_cnf():
    return LLMNERConfig(
        base_url=BASE_URL,
        model="non-existant-model",
    )


@pytest.fixture
def linking_cnf():
    return LLMLinkConfig(
        base_url=BASE_URL,
        model="non-existant-model",
    )


@pytest.fixture
def base_cnf():
    cnf = Config()
    cnf.general.nlp.provider = "regex"
    return cnf


@pytest.fixture
def tokenizer(base_cnf):
    return create_tokenizer(base_cnf.general.nlp.provider, base_cnf)


@pytest.fixture
def cdb(base_cnf, tokenizer):
    cdb = CDB(base_cnf)
    for num, name in enumerate(VOCAB):
        prepped = prepare_name(name, tokenizer, {}, [
            base_cnf.general, base_cnf.preprocessing, base_cnf.cdb_maker])
        cui = f"C{num + 1:02d}"
        cdb.add_names(cui, prepped)
    return cdb


@pytest.fixture
def ner(ner_cnf, tokenizer, cdb):
    ner_cnf = Ner(
        custom_cnf=ner_cnf,
    )
    return LLMNER.create_new_component(ner_cnf, tokenizer, cdb, None, None)


@pytest.fixture
def linker(linking_cnf, cdb):
    linking_cnf = Linking(
        additional=linking_cnf,
    )
    return LLMLinker.create_new_component(linking_cnf, None, cdb, None, None)


@pytest.fixture
def example_text():
    return "Patient had diabetes and kidney failure"


@pytest.fixture
def example_doc(tokenizer, example_text):
    return tokenizer(example_text)


def test_ner_can_predict(has_ner_server, ner, example_doc):
    ents = ner.predict_entities(example_doc, None)
    assert ents
    assert all(
        ent.detected_name for ent in ents
    )


def _generate_ents(doc) -> list:
    out_ents = []
    raw_text = doc.text
    for name in VOCAB:
        if name not in raw_text:
            continue
        occurrences = [m.start() for m in re.finditer(re.escape(name), raw_text)]
        for start in occurrences:
            tkns = doc.get_tokens(start, start + len(name))
            if not tkns:
                continue
            tkn_start, tkn_end = tkns[0].index, tkns[-1].index
            ent = doc[tkn_start: tkn_end + 1]
            ent.detected_name = name
            out_ents.append(ent)
    return out_ents


def test_linker_can_predict(
    has_linking_server, linker, example_doc
):
    ner_ents = _generate_ents(example_doc)
    assert ner_ents
    linked_ents = linker.predict_entities(example_doc, ner_ents)
    assert linked_ents
    assert all(
        ent.cui for ent in linked_ents
    )
