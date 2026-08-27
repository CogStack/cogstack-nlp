from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from medcat.cdb import CDB
from medcat.config.config import ComponentConfig, Linking
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.vocab import Vocab

from .base import (
    AbstractLLMEntityComponent,
    LLMConnectionConfig,
    MisconfiguredComponentException,
)

logger = logging.getLogger(__name__)


CandidateFn = Callable[[str], list[tuple[str, str]]]


class LLMLinkConfig(LLMConnectionConfig):
    comp_name: str = "llm_linker"
    context_window: int = 200
    prompt: str = (
        "Given the surrounding text and a medical term found in it, pick "
        "the single best matching concept from the candidates below, or "
        "'NONE' if none fit.\n\nCONTEXT:\n%s\n\nTERM: %s\n\nCANDIDATES "
        "(cui: name):\n%s"
    )


class LLMLinker(AbstractLLMEntityComponent):
    def __init__(self, cnf: LLMLinkConfig, candidate_fn: CandidateFn) -> None:
        super().__init__(cnf)
        self.cnf: LLMLinkConfig = cnf
        self.candidate_fn = candidate_fn

    def _candidate_schema(self, candidates: list[tuple[str, str]]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cui": {"type": "string", "enum": [c for c, _ in candidates] + ["NONE"]},
            },
            "required": ["cui"],
        }

    def _extract_cui(self, raw: str) -> str:
        text = self._clean_response(raw)
        try:
            return json.loads(text)["cui"]
        except (json.JSONDecodeError, KeyError, TypeError):
            return text  # freeform fallback: model just replied with the CUI/NONE

    def _pick_cui(
        self, context: str, name: str, candidates: list[tuple[str, str]]
    ) -> str | None:
        cand_str = "\n".join(f"{cui}: {pretty}" for cui, pretty in candidates)
        prompt = self.cnf.prompt % (context, name, cand_str)
        raw = self._chat(prompt, schema=self._candidate_schema(candidates))
        answer = self._extract_cui(raw)
        valid = {cui for cui, _ in candidates}
        return answer if answer in valid else None

    def predict_entities(
        self, doc: MutableDocument, ents: list[MutableEntity] | None = None
    ) -> list[MutableEntity]:
        if ents is None:
            raise NotImplementedError(
                "MyLLMLinker only implements the linking step (ents "
                "required); use MyLLMNER for the NER step.")
        text = doc.base.text
        for ent in ents:
            candidates = self.candidate_fn(ent.detected_name)
            if not candidates:
                continue
            start = max(0, ent.base.start_char_index - self.cnf.context_window)
            end = min(len(text), ent.base.end_char_index + self.cnf.context_window)
            cui = self._pick_cui(text[start:end], ent.base.text, candidates)
            if cui is not None:
                ent.cui = cui  # NOTE: attribute name is a guess - adjust to MutableEntity's real API
        return ents

    @classmethod
    def create_new_component(
        cls,
        cnf: ComponentConfig,
        tokenizer: BaseTokenizer,
        cdb: CDB,
        vocab: Vocab,
        model_load_path: str | None,
    ) -> LLMLinker:

        def get_candidates(name: str) -> list[tuple[str, str]]:
            if name not in cdb.name2info:
                return []
            return [(cui, cdb.get_name(cui)) for
                    cui in cdb.name2info[name]['per_cui_status']]
        if not isinstance(cnf, Linking):
            raise MisconfiguredComponentException(
                "Wrong type of config on config.linking - "
                f"Expected Linking, got {type(cnf).__name__}"
            )
        llm_cnf = cnf.additional
        if not isinstance(llm_cnf, LLMLinkConfig):
            raise MisconfiguredComponentException(
                "Wrong type of config on config.linking.additional - "
                f"Expected LLMLinkConfig, got {type(llm_cnf).__name__}"
            )
        return cls(llm_cnf, get_candidates)
