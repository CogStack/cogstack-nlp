from enum import Enum
from typing import Callable, Iterable, Collection
from itertools import product
import logging
from collections import Counter

from medcat.cat import CAT
from medcat.cdb.concepts import CUIInfo, NameInfo
from medcat.components.base import CoreComponentType
from medcat.config import LinkingFilters
from medcat.pipeline import Pipeline
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.tokens import MutableToken
from medcat.stats.common import PredictedAnnotation
from medcat.utils.cdb_utils import reverse_pt2ch


logger = logging.getLogger(__name__)


class FailureMode(str, Enum):
    """Why a gold-standard annotation was not predicted (false negative).

    Each FN is assigned exactly ONE mode. Evaluated in this order; the first
    matching mode wins:

        0. gold sanity             (SPAN_INCORRECT_FOR_VALUE)
        1. concept / name lookup   (CUI_NOT_IN_CDB .. NAME_NOT_LINKED_TO_CUI)
        2. NER                     (NER_NO_SPAN)
        3. filters                 (FILTERED_*)
        4. disambiguation          (WRONG_CONCEPT_*)
        5. span                    (SPAN_*)
        6. thresholding            (BELOW_THRESHOLD)
        7. fallback                (UNKNOWN)

    Filters are checked before disambiguation because a filtered-out gold
    concept is removed from the candidates, which would otherwise show up as
    a (misleading) disambiguation failure.

    Hierarchy-based modes need a concept hierarchy (e.g. SNOMED is-a). With
    no hierarchy (custom ontology) use WRONG_CONCEPT_UNRELATED.
    """

    # --- 0. Gold sanity -----------------------------------------------
    SPAN_INCORRECT_FOR_VALUE = "span_incorrect_for_value"
    """The span start/end index did not match the value specified by the
    annotation. This is normally due to some preprocessing somewhere. Not a
    model failure, and nothing else can be said about such an annotation."""

    # --- 1. Concept / name lookup -------------------------------------
    CUI_NOT_IN_CDB = "cui_not_in_cdb"
    """The gold concept does not exist in the CDB at all, so no name can
    reach it (e.g. CDB built from a subset of the ontology)."""

    NAME_UNKNOWN = "name_unknown"
    """The surface text (after normalisation) is not a known name in the CDB
    for any concept."""

    NAME_NOT_LINKED_TO_CUI = "name_not_linked_to_cui"
    """The name is in the CDB, but only maps to other concepts. The gold
    concept was never a candidate, so disambiguation could not select it."""

    # --- 2. NER ---------------------------------------------------------
    NER_NO_SPAN = "ner_no_span"
    """The name is in the CDB and maps to the gold concept, but the NER step
    never proposed a span. Typical causes: tokenisation boundary mismatch,
    normalisation, case sensitivity (e.g. abbreviations), min name length,
    or too many skipped tokens in a multi-word name."""

    # --- 3. Filters -----------------------------------------------------
    FILTERED_DISALLOW_LIST = "filtered_disallow_list"
    """The gold concept is explicitly excluded by a disallow list / exclude
    filter."""

    FILTERED_NOT_IN_ALLOW_LIST = "filtered_not_in_allow_list"
    """An allow list / include filter is active and the gold concept is not
    in it."""

    # --- 4. Disambiguation (gold concept was a candidate, other chosen) --
    WRONG_CONCEPT_DIRECT_PARENT = "wrong_concept_direct_parent"
    """The direct parent of the concept was predicted instead of the expected
    (more specific) gold concept."""
    WRONG_CONCEPT_ANCESTOR = "wrong_concept_ancestor"
    """A more general concept (ancestor of the gold concept) was predicted
    instead. Record the hierarchy distance as metadata."""

    WRONG_CONCEPT_DIRECT_CHILD = "wrong_concept_direct_child"
    """The direct child of the concept was predicted instead of the expected
    (more general) gold concept."""

    WRONG_CONCEPT_DESCENDANT = "wrong_concept_descendant"
    """A more specific concept (descendant of the gold concept) was predicted
    instead. Record the hierarchy distance as metadata."""

    WRONG_CONCEPT_SIBLING = "wrong_concept_sibling"
    """A concept sharing a direct parent with the gold concept was predicted
    instead."""

    WRONG_CONCEPT_UNRELATED = "wrong_concept_unrelated"
    """A concept with no known hierarchical relation to the gold concept was
    predicted instead (or no hierarchy is available)."""

    # --- 5. Span --------------------------------------------------------
    SPAN_PRED_CONTAINS_GOLD = "span_pred_contains_gold"
    """Right concept, but the predicted span is longer: it fully contains the
    gold span."""

    SPAN_GOLD_CONTAINS_PRED = "span_gold_contains_pred"
    """Right concept, but the predicted span is shorter: it lies fully inside
    the gold span."""

    SPAN_PARTIAL_OVERLAP = "span_partial_overlap"
    """Right concept, but the predicted span is shifted: it overlaps the gold
    span without either containing the other."""

    # --- 6. Thresholding -----------------------------------------------
    BELOW_THRESHOLD = "below_threshold"
    """The gold concept was not chosen due to its linking score being below
    the acceptance threshold. We cannot tell for certain if there were other
    concepts that were higher in linking score at this stage. Store the score
    margin and the concept's training count as metadata to tell 'needs more
    training data' apart from 'close to the threshold'."""

    # --- 7. Fallback ----------------------------------------------------
    UNKNOWN = "unknown"
    """No mode above explains the miss (includes possible gold-annotation
    errors such as bad offsets or labels)."""


# Given some text, return (start, end, link_candidates) for every entity the
# NER step proposed, with char indices relative to that text. See
# `make_ner_candidates` for how to build one.
NERCandidates = Callable[[str], Iterable[tuple[int, int, Collection[str]]]]

# When the predictions for a span map to several different relations to the
# gold concept, pick the closest relation first.
_DISAMB_PRIORITY = [
    FailureMode.WRONG_CONCEPT_DIRECT_PARENT,
    FailureMode.WRONG_CONCEPT_DIRECT_CHILD,
    FailureMode.WRONG_CONCEPT_SIBLING,
    FailureMode.WRONG_CONCEPT_ANCESTOR,
    FailureMode.WRONG_CONCEPT_DESCENDANT,
    FailureMode.WRONG_CONCEPT_UNRELATED,
]


def make_ner_candidates(
    pipe: Pipeline,
) -> NERCandidates:
    """Build the NER-only callable.

    UNTESTED SKETCH: check the entity attribute names against your version.
    The point is to run ONLY tokenizer + NER. Do not use full pipeline
    output: the linker replaces `doc.ner_ents` with the linked entities.
    """
    def run(text: str) -> list[tuple[int, int, Collection[str]]]:
        doc = pipe.pipe_until(text, CoreComponentType.ner)
        return [
            (ent.base.start_char_index, ent.base.end_char_index,
             ent.link_candidates)
            for ent in doc.ner_ents
        ]
    return run


def _get_local_span(
    context: str,
    start: int, end: int,
    source_value: str,
    window_size: int,
) -> tuple[int, int]:
    span_len = end - start
    # if in the middle of some text
    if len(context) == window_size + span_len + window_size:
        return window_size, window_size + span_len
    # harder case where we're not in the middle of text so the span
    # we're looking for could be at the start or end of the context
    l_context = context.lower()
    l_source = source_value.lower()
    occurances = l_context.count(l_source)
    if occurances == 1:
        cstart = l_context.find(l_source)
        return cstart, cstart + span_len
    elif occurances == 0:
        # does not exist in here
        # NOTE: this can detract from SPAN_INCORRECT_FOR_VALUE
        #       but only in cases where the span is at the start
        #       or end of the text, otherwise the length based
        #       check should have caught it anyway
        return -2, -1
    # even harder since there are multiple places in there
    # I will just get the one that's closest to the middle of
    # the context...
    logger.info(
        "Having trouble getting local span detials for %s due to the text "
        "having %d instances of the string within it. We will try to pick "
        "the one that's closest to the centre of the context, but that is "
        "not guaranteed to be correct either."
    )
    cur_start = 0
    spans: list[tuple[int, int]] = []
    while (new_start := l_context.find(l_source, cur_start)) != -1:
        cur_end = new_start + len(l_source)
        spans.append((new_start, cur_end))
        cur_start = cur_end
    midpoint = len(l_context)
    return min(spans, key=lambda item: abs(sum(item) - midpoint))


# TODO: if/when #622 is merged, use method from there
def _build_opts(tkns: list[MutableToken], separator: str) -> set[str]:
    per_tkn_opts: list[list[str]] = []
    for tkn in tkns:
        name_versions = tkn.base.text_versions
        # NOTE: I want to preserve order since the text versions returns in
        #       the correct / expected order in which to check
        unique_versions = []
        # NOTE: we want to avoid duplicate names so we only keep uinque ones
        #       otherwise the option set can become massive
        for version in name_versions:
            # NOTE: we're checking contents of a list, not ideal
            #       but we should only ever have 0 or 1 items in the list
            #       at time of check so shouldn't be too bad
            if version not in unique_versions:
                unique_versions.append(version)
        per_tkn_opts.append(unique_versions)
    opt_set = set(product(*per_tkn_opts))
    return set(map(separator.join, opt_set))


def _ancestors(cui: str, ch2pt: dict[str, list[str]]) -> set[str]:
    """All ancestors of a concept. Safe against cycles."""
    seen: set[str] = set()
    stack = list(ch2pt.get(cui, []))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(ch2pt.get(cur, []))
    return seen


def get_disamb_failure_mode(
    gold_cui: str,
    pred_cui: str,
    ch2pt: dict[str, list[str]],
) -> FailureMode:
    """Relation of the predicted concept to the gold one.

    Only needs the child -> parents map. Walks UPWARDS from both concepts
    (parents are few; descendants of a general concept can be huge).
    """
    gold_parents = set(ch2pt.get(gold_cui, []))
    pred_parents = set(ch2pt.get(pred_cui, []))
    if pred_cui in gold_parents:
        return FailureMode.WRONG_CONCEPT_DIRECT_PARENT
    if gold_cui in pred_parents:
        return FailureMode.WRONG_CONCEPT_DIRECT_CHILD
    if gold_parents & pred_parents:
        return FailureMode.WRONG_CONCEPT_SIBLING
    if pred_cui in _ancestors(gold_cui, ch2pt):
        return FailureMode.WRONG_CONCEPT_ANCESTOR
    if gold_cui in _ancestors(pred_cui, ch2pt):
        return FailureMode.WRONG_CONCEPT_DESCENDANT
    return FailureMode.WRONG_CONCEPT_UNRELATED


def _get_failure_mode_for_partial_span(
    gold_cui: str, gold_start: int, gold_end: int,
    pred_cui: str, pred_start: int, pred_end: int,
) -> FailureMode | None:
    if gold_cui != pred_cui:
        return None
    if pred_end <= gold_start or gold_end <= pred_start:
        return None
    if pred_start <= gold_start and gold_end <= pred_end:
        # NOTE: identical spans would be a TP, so never reach here as FN
        return FailureMode.SPAN_PRED_CONTAINS_GOLD
    if gold_start <= pred_start and pred_end <= gold_end:
        return FailureMode.SPAN_GOLD_CONTAINS_PRED
    return FailureMode.SPAN_PARTIAL_OVERLAP


def _get_partially_overlapping_spans(
    example: dict,
    predictions: list[PredictedAnnotation],
) -> list[tuple[PredictedAnnotation, FailureMode]]:
    gold_cui = example['cui']
    gold_start, gold_end = example['start'], example['end']
    return [
        (pred, fm) for pred in predictions
        if (fm := _get_failure_mode_for_partial_span(
            gold_cui, gold_start, gold_end,
            pred['cui'], pred['start'], pred['end']))
    ]


def _ner_proposed_span(
    ner_candidates: NERCandidates,
    context: str,
    local_start: int, local_end: int,
    gold_cui: str,
) -> bool:
    """Did NER propose anything overlapping the gold span that had the gold
    concept among its link candidates?

    Overlap rather than same-start, so a shifted/longer/shorter proposal is
    not an NER miss: it falls through to the span modes.
    """
    return any(
        start < local_end and local_start < end and gold_cui in cands
        for start, end, cands in ner_candidates(context)
    )


class FailureModeFinder:

    def __init__(
        self,
        tokenizer: BaseTokenizer,
        cui2info: dict[str, CUIInfo],
        name2info: dict[str, NameInfo],
        pt2ch: dict[str, list[str]],
        linking_filters: LinkingFilters,
        token_separator: str,
        ner_candidates: NERCandidates,
    ) -> None:
        self.tokenizer = tokenizer
        self.cui2info = cui2info
        self.name2info = name2info
        self.pt2ch = pt2ch
        self._ch2pt: dict[str, list[str]] | None = None
        self.linking_filters = linking_filters
        self.token_separator = token_separator
        self.ner_candidates = ner_candidates

    @property
    def ch2pt(self) -> dict[str, list[str]]:
        if self._ch2pt is None:
            self._ch2pt = reverse_pt2ch(self.pt2ch)
        return self._ch2pt

    @classmethod
    def from_cat(cls, cat: CAT) -> 'FailureModeFinder':
        return cls(
            cat.pipe.tokenizer_with_tag, cat.cdb.cui2info, cat.cdb.name2info,
            cat.cdb.addl_info['pt2ch'], cat.config.components.linking.filters,
            cat.config.general.separator, make_ner_candidates(cat.pipe)
        )

    def step_0_gold_sanity(
        self, context: str, start: int, end: int,
        source_val: str,
    ) -> FailureMode | None:
        if context[start: end] != source_val:
            return FailureMode.SPAN_INCORRECT_FOR_VALUE
        return None

    def step_1_concept_and_name_lookup(
        self,
        gold_cui: str,
        source_val: str,
    ) -> FailureMode | None:
        tkns = [
            tkn for tkn in self.tokenizer(source_val)
            if not tkn.to_skip
        ]
        name_versions = _build_opts(tkns, self.token_separator)
        suitable_names = [
            name for name in name_versions if name in self.name2info]
        # any name variant linking to the gold concept is enough
        candidates: set[str] = set()
        for name in suitable_names:
            candidates.update(self.name2info[name]['per_cui_status'])
        if gold_cui not in self.cui2info:
            return FailureMode.CUI_NOT_IN_CDB
        if not suitable_names:
            return FailureMode.NAME_UNKNOWN
        if gold_cui not in candidates:
            return FailureMode.NAME_NOT_LINKED_TO_CUI
        return None

    def step_2_ner(
        self, context: str, start: int, end: int, gold_cui: str
    ) -> FailureMode | None:
        if self.ner_candidates is not None and not _ner_proposed_span(
                self.ner_candidates, context, start, end, gold_cui):
            return FailureMode.NER_NO_SPAN
        return None

    def step_3_filters(
        self, gold_cui: str,
    ) -> FailureMode | None:
        allow_filter = self.linking_filters.cuis
        disallow_filter = self.linking_filters.cuis_exclude
        if allow_filter and gold_cui not in allow_filter:
            return FailureMode.FILTERED_NOT_IN_ALLOW_LIST
        if gold_cui in disallow_filter:
            return FailureMode.FILTERED_DISALLOW_LIST
        return None

    def step_4_disambiguation(
        self, span_predictions: list[PredictedAnnotation],
        gold_cui: str, source_val: str,
    ) -> FailureMode | None:
        if span_predictions:
            modes = {
                get_disamb_failure_mode(gold_cui, pred["cui"], self.ch2pt)
                for pred in span_predictions
            }
            picked = min(modes, key=lambda m: m.name)
            if len(modes) > 1:
                logger.warning(
                    "Unable to determine a single point of failure for %s "
                    "(%s). Available: %s. Picking the first alphabetically "
                    "(%s)",
                    gold_cui, source_val, [fm.name for fm in modes],
                    picked.name,
                )
            return picked
        return None

    def step_5_partial_overlap(
        self, example: dict, all_predictions: list[PredictedAnnotation],
    ) -> FailureMode | None:
        partially_matching_spans = _get_partially_overlapping_spans(
            example, all_predictions)
        if partially_matching_spans:
            cntr: Counter[FailureMode] = Counter(
                fm for _, fm in partially_matching_spans)
            if len(cntr) > 1:
                most_common = cntr.most_common(1)[0][0]
                logger.warning(
                    "Got multiple types of partial failure modes. "
                    "Using most common (%s), available: %s",
                    most_common, cntr
                )
                return most_common
            return next(iter(cntr.keys()))
        return None

    def get_failure_mode(
        self,
        example: dict,
        span_predictions: list[PredictedAnnotation],
        all_predictions: list[PredictedAnnotation],
        window_size: int = 60,
    ) -> FailureMode:
        gold_cui = example['cui']
        context = example['text']
        source_val = example['source_value']

        # prep for step 0
        start, end = _get_local_span(
            context, example['start'], example['end'],
            source_val, window_size
        )

        # 0. gold sanity
        step0 = self.step_0_gold_sanity(context, start, end, source_val)
        if step0:
            return step0

        # 1. concept / name lookup
        step1 = self.step_1_concept_and_name_lookup(
            gold_cui, source_val)
        if step1:
            return step1

        # 2. NER
        step2 = self.step_2_ner(context, start, end, gold_cui)
        if step2:
            return step2

        # 3. filters
        step3 = self.step_3_filters(gold_cui)
        if step3:
            return step3

        # 4. disambiguation: something else WAS annotated at this span
        step4 = self.step_4_disambiguation(
            span_predictions, gold_cui, source_val)
        if step4:
            return step4

        # 5. span: nearby / overlapping prediction of the right concept
        step5 = self.step_5_partial_overlap(example, all_predictions)
        if step5:
            return step5

        # 6. thresholding
        # Everything that reached here had a valid name->cui mapping and was
        # not annotated as anything else. If NER was checked it did propose
        # the span, so the linker must have rejected it. If NER was not
        # checked we cannot tell that apart from an NER miss.
        # NOTE: no way to verify the score itself, since non-predicted concepts
        #       are not returned.
        return FailureMode.BELOW_THRESHOLD
