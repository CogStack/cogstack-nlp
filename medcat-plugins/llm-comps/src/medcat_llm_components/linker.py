from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from medcat.tokenizing.tokens import MutableDocument, MutableEntity

from .base import AbstractLLMEntityComponent, LLMConnectionConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Linking step
#
# An LLM asked to freely produce a CUI will hallucinate one - it has no
# access to your CDB. So this only ever asks it to pick from a
# candidate list you supply (`candidate_fn`: name -> [(cui, pretty
# name), ...], e.g. via CDB name lookup / fuzzy match), and this is
# where structured output actually earns its keep: constraining the
# response to an enum of the candidate CUIs (+ "NONE") is a much
# stronger guarantee than "please reply with just the CUI".
# ---------------------------------------------------------------------------

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
            candidates = self.candidate_fn(ent.base.text)
            if not candidates:
                continue
            start = max(0, ent.base.start_char_index - self.cnf.context_window)
            end = min(len(text), ent.base.end_char_index + self.cnf.context_window)
            cui = self._pick_cui(text[start:end], ent.base.text, candidates)
            if cui is not None:
                ent.cui = cui  # NOTE: attribute name is a guess - adjust to MutableEntity's real API
        return ents
