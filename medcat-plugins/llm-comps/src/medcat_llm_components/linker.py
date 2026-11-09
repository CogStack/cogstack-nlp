from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterable
from typing import Any

from openai import OpenAI

from medcat.cdb import CDB
from medcat.components.types import CoreComponentType
from medcat.config.config import ComponentConfig, Linking
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.vocab import Vocab
from medcat.utils.defaults import StatusTypes

from .base import (
    AbstractLLMEntityComponent,
    LLMConnectionConfig,
    MisconfiguredComponentException,
    clean_response,
    one_chat,
)

logger = logging.getLogger(__name__)


CandidateFn = Callable[[str], list[tuple[str, str, str]]]


class LLMLinkConfig(LLMConnectionConfig):
    comp_name: str = "llm_linker"
    context_window: int = 200
    prompt: str = (
        "Given the surrounding text and a medical term found in it, pick "
        "the single best matching concept from the candidates below, or "
        "'NONE' if none fit.\n\nCONTEXT:\n%s\n\nTERM: %s\n\nCANDIDATES "
        "(cui: name):\n%s"
    )
    prompt_multiprocess_threads: int = 4

def _extract_cui(raw: str) -> str:
    text = clean_response(raw)
    try:
        return json.loads(text)["cui"].strip()
    except (json.JSONDecodeError, KeyError, TypeError):
        return text  # freeform fallback: model just replied with the CUI/NONE


def _pick_cui(raw: str, candidates: list[tuple[str, str, str]]):
        answer = _extract_cui(raw)
        valid = {cui for cui, _, _ in candidates}
        return answer if answer in valid else None


def _one_chat(
    cnf: LLMLinkConfig,
    client: OpenAI,
    prompt: str,
    schema: dict[str, Any] | None,
    candidates: list[tuple[str, str, str]],
) -> str:
    if len(candidates) == 1 and candidates[0][2] not in StatusTypes.DO_DISAMBUGATION:
        return candidates[0][0]
    return one_chat(
        cnf, client, prompt, schema
    )


class LLMLinker(AbstractLLMEntityComponent):
    name = "llm_linker"

    def __init__(self, cnf: LLMLinkConfig, candidate_fn: CandidateFn) -> None:
        super().__init__(cnf)
        self.cnf: LLMLinkConfig = cnf
        self.candidate_fn = candidate_fn

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.linking

    def _candidate_schema(self, candidates: list[tuple[str, str, str]]) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cui": {"type": "string", "enum": [c for c, _, _ in candidates] + ["NONE"]},
            },
            "required": ["cui"],
        }

    def _prep_prompt(
        self,
        text: str,
        ent: MutableEntity,
        candidates: list[tuple[str, str, str]],
    ) -> str:
        start = max(0, ent.base.start_char_index - self.cnf.context_window)
        end = min(len(text), ent.base.end_char_index + self.cnf.context_window)
        cand_str = "\n".join(f"{cui}: {pretty}" for cui, pretty, status in candidates)
        context = text[start:end]
        prompt = self.cnf.prompt % (context, ent.base.text, cand_str)
        return prompt

    def _prepare_contexts(
        self,
        doc: MutableDocument,
        ents: list[MutableEntity],
    ) -> Iterable[tuple[int, str, list[tuple[str, str, str]]]]:
        text = doc.base.text
        for idx, ent in enumerate(ents):
            candidates = self.candidate_fn(ent.detected_name)
            if not candidates:
                continue
            prompt = self._prep_prompt(text, ent, candidates)
            yield idx, prompt, candidates

    def _predict_entities_with_context_sequential(
        self,
        ents: list[MutableEntity],
        all_contexts: Iterable[tuple[int, str, list[tuple[str, str ,str]]]],
    ) -> list[MutableEntity]:
        linked_ents: list[MutableEntity] = []
        for ent_idx, prompt, candidates in all_contexts:
            raw = _one_chat(
                self.cnf, self._client,
                prompt, schema=self._candidate_schema(candidates),
                candidates=candidates,
            )
            cui = _pick_cui(raw, candidates)
            ent = ents[ent_idx]
            if cui is not None:
                self._update_entity(ent, cui)
                linked_ents.append(ent)
        return linked_ents

    def _update_entity(self, ent: MutableEntity, cui: str) -> None:
        ent.cui = cui
        # we did not do that, really - but for downstream filtering
        ent.context_similarity = ent.confidence = 1.0

    def _predict_entities_with_context_mp(
        self,
        ents: list[MutableEntity],
        all_contexts: Iterable[tuple[int, str, list[tuple[str, str ,str]]]],
    ) -> list[MutableEntity]:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        max_workers = self.cnf.prompt_multiprocess_threads
        linked_ents: list[MutableEntity] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_id_cands = {
                executor.submit(
                    _one_chat,
                    self.cnf,
                    self._client,
                    prompt,
                    self._candidate_schema(cands),
                    cands,
                ): (idx, cands)
                for idx, prompt, cands in all_contexts}

            # Collect results as they complete
            for future in as_completed(future_to_id_cands):
                raw_result = future.result()
                ent_idx, cands = future_to_id_cands[future]
                cui = _pick_cui(raw_result, cands)
                ent = ents[ent_idx]
                if cui is not None:
                    self._update_entity(ent, cui)
                    linked_ents.append(ent)
        return linked_ents

    def predict_entities(
        self, doc: MutableDocument, ents: list[MutableEntity] | None = None
    ) -> list[MutableEntity]:
        if ents is None:
            raise NotImplementedError(
                "MyLLMLinker only implements the linking step (ents "
                "required); use MyLLMNER for the NER step.")
        all_contexts = self._prepare_contexts(doc, ents)
        if self.cnf.prompt_multiprocess_threads <= 1:
            return self._predict_entities_with_context_sequential(
                ents, all_contexts
            )
        return self._predict_entities_with_context_mp(
            ents, all_contexts
        )

    @classmethod
    def create_new_component(
        cls,
        cnf: ComponentConfig,
        tokenizer: BaseTokenizer,
        cdb: CDB,
        vocab: Vocab,
        model_load_path: str | None,
    ) -> LLMLinker:

        def get_candidates(name: str) -> list[tuple[str, str, str]]:
            if name not in cdb.name2info:
                return []
            return [(cui, cdb.get_name(cui), status) for
                    cui, status in cdb.name2info[name]['per_cui_status'].items()]
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
