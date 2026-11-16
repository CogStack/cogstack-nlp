import pytest

from medcat.config.config import Linking, Ner
from medcat.cdb import CDB
from medcat.config import Config

from medcat_llm_components.base import MisconfiguredComponentException
from medcat_llm_components.pure_llm_linker import (
    NoSuchSpan,
    PureLLMLinkConfig,
    PureLLMLinker,
    find_start,
    parse_output,
)


BASE = {"base_url": "http://localhost:9/v1", "model": "test-model"}


def test_find_start_uses_reported_index_when_it_matches():
    assert find_start("pain in the chest", "pain", 0) == 0


def test_find_start_picks_the_closest_occurrence():
    text = "pain and then more pain later"
    # "pain" starts at 0 and at 19. The closest index is not the
    # position of that match in the match list.
    assert find_start(text, "pain", 20) == 19


def test_find_start_falls_back_to_case_insensitive_match():
    assert find_start("Has Diabetes mellitus", "diabetes mellitus", 4) == 4


def test_find_start_raises_when_the_span_is_absent():
    with pytest.raises(NoSuchSpan):
        find_start("no medical terms here", "diabetes", 0)


def test_parse_output_keeps_only_placeable_known_cuis():
    raw = """
    <think>looking</think>
```json
    {"entities": [
        {"value": "pain", "start_char_index": 99, "cui": "111"},
        {"value": "nope", "start_char_index": 0, "cui": "111"},
        {"value": "pain", "start_char_index": 0, "cui": "999"},
        {"value": "missing-field", "cui": "111"}
    ]}
```
    """
    assert parse_output("pain here", raw, {"111"}) == [(0, "pain", "111")]


def test_parse_output_returns_empty_on_garbage():
    assert parse_output("pain", "not json", {"111"}) == []


def test_prompt_is_filled_from_config_and_candidates():
    cnf = PureLLMLinkConfig(**BASE)
    linker = PureLLMLinker(cnf, tokenizer=None, name_separator="~",
                           all_candidates=[("111", "Pain")])
    prompt = linker._prep_prompt("patient has pain")
    assert "111 (Pain)" in prompt
    assert "patient has pain" in prompt
    assert cnf.prompt_opt_list_placeholder not in prompt
    assert cnf.prompt_doc_placeholder not in prompt
    assert linker._request_kwargs()["reasoning_effort"] == "none"
    assert linker._request_kwargs()["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False},
    }


def test_create_new_component_reads_candidates_from_the_cdb():
    config = Config()
    cdb = CDB(config)
    cdb.cui2info["111"] = {
        "preferred_name": "Pain",
        "names": {"Pain"},
    }
    linking = Linking(additional=PureLLMLinkConfig(**BASE))
    linker = PureLLMLinker.create_new_component(
        linking, tokenizer=None, cdb=cdb, vocab=None, model_load_path=None)
    assert linker._all_candidates == [("111", "Pain")]
    assert linker._name_separator == "~"


def test_create_new_component_rejects_the_wrong_config():
    with pytest.raises(MisconfiguredComponentException):
        PureLLMLinker.create_new_component(
            Ner(), tokenizer=None, cdb=CDB(Config()), vocab=None,
            model_load_path=None)
    with pytest.raises(MisconfiguredComponentException):
        PureLLMLinker.create_new_component(
            Linking(), tokenizer=None, cdb=CDB(Config()), vocab=None,
            model_load_path=None)
