from __future__ import annotations

import json
import logging
import re
from typing import Any

from medcat.cdb import CDB
from medcat.components.types import CoreComponentType
from medcat.config.config import ComponentConfig, Linking
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.vocab import Vocab
from openai import APIConnectionError, APIError, APITimeoutError

from .base import (
    AbstractLLMEntityComponent,
    LLMConnectionConfig,
    MisconfiguredComponentException,
    clean_response,
    one_chat,
)

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL)


class NoSuchSpan(ValueError):
    """Raised when a reported span cannot be found in the source text."""


class PureLLMLinkConfig(LLMConnectionConfig):
    """Config for a linker that detects and links in a single LLM call.

    The model sees the whole document plus every concept in the CDB.
    Connection details (``base_url``, ``api_key``, ``model``,
    ``temperature``, ``timeout``, ``retries``) come from
    ``LLMConnectionConfig``. ``timeout`` and ``retries`` default to the
    values the standalone script used.
    """

    comp_name: str = "pure_llm_linker"
    model: str = "qwen3.8:27b"
    timeout: float = 600.0
    retries: int = 5
    # Qwen-style servers otherwise spend the timeout on a hidden
    # reasoning trace. Set ``reasoning_effort`` to None to omit it,
    # and ``enable_thinking`` to True to leave thinking on.
    reasoning_effort: str | None = "none"
    enable_thinking: bool = False

    prompt_opt_list_placeholder: str = "{##OPTIONS##}"
    prompt_doc_placeholder: str = "{##DOC##}"
    prompt: str = f"""
    Identify all medical concepts (i.e the spans) in the text provided
    and map them to the correct Snomed codes. The possible Snomed codes
    are listed here in the format "CUI (name)": {prompt_opt_list_placeholder}.

    Respond in JSON format with the following schema, include no other response:
    {{
        "entities": [
            {{
                "value": "val-str",
                "start_char_index": 0,
                "cui": "91936005"
            }},
            # and so on
        ]
    }}

    In the above:
    value - the exact string in the text that was identified as a medical term
    start_char_index - the character index where the value starts
    cui - the concept ID (from the list above)

    The text to process is as follows:
    {prompt_doc_placeholder}
    """


def _strip_model_wrappers(raw: str) -> str:
    text = _THINK_RE.sub("", raw)
    return clean_response(text)


def find_start(
    orig_doc: str,
    orig_name: str,
    raw_start_char: int,
    in_lower_case: bool = False,
) -> int:
    """Reconcile a model-reported start index with the source text.

    Uses the reported index when the span matches there. Otherwise
    searches for the surface form and, if it occurs more than once,
    picks the occurrence closest to the reported index. Falls back to
    a case-insensitive search once.
    """
    doc = orig_doc.lower() if in_lower_case else orig_doc
    name = orig_name.lower() if in_lower_case else orig_name
    name_len = len(name)
    if (
        name
        and 0 <= raw_start_char <= len(doc) - name_len
        and doc[raw_start_char:raw_start_char + name_len] == name
    ):
        return raw_start_char
    found = list(re.finditer(re.escape(name), doc)) if name else []
    if len(found) == 1:
        # A unique hit can still be the wrong mention, but there is
        # nothing else to disambiguate against.
        return found[0].start()
    if len(found) > 1:
        return min(found, key=lambda m: abs(raw_start_char - m.start())).start()
    if in_lower_case:
        raise NoSuchSpan(f"No span {name!r} found in document")
    return find_start(orig_doc, orig_name, raw_start_char, in_lower_case=True)


def parse_output(
    doc: str,
    raw_response: str,
    valid_cuis: set[str],
) -> list[tuple[int, str, str]]:
    """Turn one model response into ``(start, surface, cui)`` triples."""
    cleaned = _strip_model_wrappers(raw_response)
    try:
        payload = json.loads(cleaned.strip())
        entities = payload["entities"]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        logger.warning(
            "Unparseable LLM response (%s). Raw response starts: %r",
            exc, raw_response[:500])
        return []
    if not isinstance(entities, list):
        logger.warning("LLM response 'entities' is not a list: %r", entities)
        return []

    linked: list[tuple[int, str, str]] = []
    for rn, ent in enumerate(entities):
        try:
            name = ent["value"]
            raw_start_char = ent["start_char_index"]
            cui = str(ent["cui"]).strip()
        except (KeyError, TypeError, AttributeError):
            logger.warning("Malformed entity at row %s: %r", rn, ent)
            continue
        if cui not in valid_cuis:
            logger.warning(
                "Dropping row %s (%r): cui %s is not in the candidate list",
                rn, name, cui)
            continue
        try:
            real_start_char = find_start(doc, name, raw_start_char)
        except (NoSuchSpan, TypeError, ValueError):
            window = 20
            start_at = raw_start_char if isinstance(raw_start_char, int) else 0
            context = doc[max(start_at - window, 0):start_at + len(str(name)) + window]
            logger.warning(
                "Could not place row %s: %r, %s @ %s. Nearby text: %r",
                rn, name, cui, raw_start_char, context)
            continue
        linked.append((real_start_char, name, cui))
    return linked


class PureLLMLinker(AbstractLLMEntityComponent):
    """Detect and link concepts with one prompt per document.

    Upstream NER entities are ignored. Each document is sent to the
    model together with the full candidate list taken from the CDB,
    and the JSON response is reconciled back into MedCAT entities.
    """

    name = "pure_llm_linker"

    def __init__(
        self,
        l_cnf: Linking,
        cnf: PureLLMLinkConfig,
        tokenizer: BaseTokenizer,
        name_separator: str,
        all_candidates: list[tuple[str, str]],
    ) -> None:
        super().__init__(cnf)
        self.l_cnf = l_cnf
        self.cnf: PureLLMLinkConfig = cnf
        self._tokenizer = tokenizer
        self._name_separator = name_separator
        self._all_candidates = dict(all_candidates)
        self._valid_cuis = {cui for cui, _ in all_candidates}
        self._recreate_candidates()

    def _filter_changed(self) -> bool:
        return (
            self.l_cnf.filters.cuis != self._cur_cui_include or
            self.l_cnf.filters.cuis_exclude != self._cur_cui_exclude
        )

    def _recreate_candidates(self) -> None:
        cui_include: set[str] = self.l_cnf.filters.cuis or set(self._valid_cuis)
        cui_exclude: set[str] = self.l_cnf.filters.cuis_exclude
        self._all_candidates_str = ", ".join(
            f"{cui} ({self._all_candidates[cui]})" for cui in cui_include
            if self.l_cnf.filters.check_filters(cui)
        )
        self._cur_cui_include = set(cui_include)
        self._cur_cui_exclude = set(cui_exclude)

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking

    def _response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "entities": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "value": {"type": "string"},
                            "start_char_index": {"type": "integer"},
                            "cui": {"type": "string"},
                        },
                        "required": ["value", "start_char_index", "cui"],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["entities"],
            "additionalProperties": False,
        }

    def _request_kwargs(self) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if self.cnf.reasoning_effort is not None:
            extra["reasoning_effort"] = self.cnf.reasoning_effort
        if not self.cnf.enable_thinking:
            extra["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": False},
            }
        return extra

    def _prep_prompt(self, text: str) -> str:
        prompt = self.cnf.prompt.replace(
            self.cnf.prompt_opt_list_placeholder, self._all_candidates_str)
        return prompt.replace(self.cnf.prompt_doc_placeholder, text)

    def _to_entities(
        self,
        doc: MutableDocument,
        raw_ents: list[tuple[int, str, str]],
    ) -> list[MutableEntity]:
        out_ents: list[MutableEntity] = []
        seen: set[tuple[int, int]] = set()
        for ent_id, (start_char_index, raw_name, cui) in enumerate(raw_ents):
            end_char_index = start_char_index + len(raw_name)
            if (start_char_index, end_char_index) in seen:
                continue
            tkns = [
                tkn for tkn in doc.get_tokens(start_char_index, end_char_index)
                if not tkn.to_skip
            ]
            if not tkns:
                logger.warning(
                    "Unable to tokenize %r (%s) @ [%s:%s] %r",
                    raw_name, cui, start_char_index, end_char_index,
                    doc.base.text[start_char_index:end_char_index])
                continue
            entity = self._tokenizer.entity_from_tokens_in_doc(tkns, doc)
            entity.cui = cui
            entity.detected_name = self._name_separator.join(
                tkn.base.text.lower() for tkn in tkns)
            entity.link_candidates = [cui]
            entity.confidence = entity.context_similarity = 1.0
            entity.id = ent_id
            out_ents.append(entity)
            seen.add((start_char_index, end_char_index))
        return out_ents

    def predict_entities(
        self, doc: MutableDocument, ents: list[MutableEntity] | None = None
    ) -> list[MutableEntity]:
        if self._filter_changed():
            logger.info("Recreating candidates based on new filter")
            self._recreate_candidates()
        text = doc.base.text
        try:
            raw = one_chat(
                self.cnf,
                self._client,
                self._prep_prompt(text),
                schema=self._response_schema(),
                request_kwargs=self._request_kwargs(),
            )
        except (APIConnectionError, APITimeoutError, APIError) as exc:
            logger.warning("%s: giving up on document: %s", self.name, exc)
            return []
        return self._to_entities(doc, parse_output(text, raw, self._valid_cuis))

    @classmethod
    def create_new_component(
        cls,
        cnf: ComponentConfig,
        tokenizer: BaseTokenizer,
        cdb: CDB,
        vocab: Vocab,
        model_load_path: str | None,
    ) -> PureLLMLinker:
        if not isinstance(cnf, Linking):
            raise MisconfiguredComponentException(
                "Wrong type of config on config.linking - "
                f"Expected Linking, got {type(cnf).__name__}"
            )
        llm_cnf = cnf.additional
        if not isinstance(llm_cnf, PureLLMLinkConfig):
            raise MisconfiguredComponentException(
                "Wrong type of config on config.linking.additional - "
                f"Expected PureLLMLinkConfig, got {type(llm_cnf).__name__}"
            )
        all_candidates = [(cui, cdb.get_name(cui)) for cui in cdb.cui2info]
        return cls(
            cnf, llm_cnf, tokenizer, cdb.config.general.separator, all_candidates)
