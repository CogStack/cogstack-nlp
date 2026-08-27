from __future__ import annotations

import csv
import io
import logging
import re

from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableDocument, MutableEntity

from .base import AbstractLLMEntityComponent, LLMConnectionConfig, UnknownSpanException

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NER step
# ---------------------------------------------------------------------------

class LLMNERConfig(LLMConnectionConfig):
    comp_name: str = "llm_ner"
    prompt: str = (
        "Given the following clinical text, list every medical term "
        "(finding, symptom, disease, procedure, drug, etc). "
        "Respond with ONLY a CSV with header 'entity,start,end' - no "
        "prose, no markdown fences, no other commentary. 'start' and "
        "'end' are the character offsets of the term in the text "
        "below, copied exactly as they appear (same case, same "
        "spelling).\n\nTEXT:\n%s"
    )
    trust_llm_span: bool = False
    span_tolerance_total: int = 10


class LLMNER(AbstractLLMEntityComponent):
    def __init__(self, tokenizer: BaseTokenizer, cnf: LLMNERConfig) -> None:
        super().__init__(cnf)
        self.tokenizer = tokenizer
        self.cnf: LLMNERConfig = cnf  # narrow the type for the rest of this class

    def _parse_csv(self, raw: str) -> list[tuple[str, int, int]]:
        text = self._clean_response(raw)
        if not text:
            return []
        reader = csv.DictReader(io.StringIO(text))
        out: list[tuple[str, int, int]] = []
        for row in reader:
            try:
                name = row["entity"].strip()
                start = int(row["start"])
                end = int(row["end"])
            except (KeyError, ValueError, AttributeError) as exc:
                logger.warning("Skipping malformed LLM row %r: %s", row, exc)
                continue
            out.append((name, start, end))
        return out

    def _call_api_raw(self, text: str) -> list[tuple[str, int, int]]:
        raw = self._chat(self.cnf.prompt % text)
        return self._parse_csv(raw)

    def _get_real_start_end(
        self, text: str, name: str, start: int, end: int
    ) -> tuple[int, int]:
        in_text = text[start:end]
        if in_text == name:
            return start, end
        occurrences = [m.start() for m in re.finditer(re.escape(name), text)]
        if not occurrences:
            raise UnknownSpanException(
                f"'{name}' does not appear verbatim in the document text "
                f"(reported span [{start}:{end}] contained {in_text!r}).")
        best_start = min(occurrences, key=lambda s: abs(s - start))
        best_end = best_start + len(name)
        dist = abs(start - best_start) + abs(end - best_end)
        if dist > self.cnf.span_tolerance_total:
            raise UnknownSpanException(
                f"Unable to find {name!r} near [{start}:{end}]. Nearest "
                f"match at [{best_start}:{best_end}] is {dist} chars away "
                "(over span_tolerance_total). If this is still correct, "
                "raise the tolerance in the config.")
        return best_start, best_end

    def _process_spans_into_ents(
        self, doc: MutableDocument, raw_spans: list[tuple[str, int, int]]
    ) -> list[MutableEntity]:
        all_ents: list[MutableEntity] = []
        raw_text = doc.base.text
        seen: set[tuple[int, int]] = set()
        for name, start, end in raw_spans:
            if not self.cnf.trust_llm_span:
                try:
                    start, end = self._get_real_start_end(raw_text, name, start, end)
                except UnknownSpanException as exc:
                    logger.warning("%s", exc)
                    continue
            if (start, end) in seen:
                continue  # LLM sometimes repeats a term
            tkns = doc.get_tokens(start, end)
            if not tkns:
                logger.warning(
                    "Unable to tokenize span [%d:%d] (%r)", start, end, name)
                continue
            entity = self.tokenizer.entity_from_tokens_in_doc(tkns, doc)
            all_ents.append(entity)
            seen.add((start, end))
        return all_ents

    def predict_entities(
        self, doc: MutableDocument, ents: list[MutableEntity] | None = None
    ) -> list[MutableEntity]:
        if ents is not None:
            raise NotImplementedError(
                "MyLLMNER only implements the NER step; use MyLLMLinker "
                "for the ents-provided (linking) step.")
        raw_spans = self._call_api_raw(doc.base.text)
        return self._process_spans_into_ents(doc, raw_spans)
