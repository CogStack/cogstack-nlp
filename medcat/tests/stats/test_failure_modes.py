"""Tests for false-negative failure mode classification."""
from types import SimpleNamespace

import unittest

# NOTE: adjust this import to wherever the module lives
from medcat.components import base
from medcat.stats.failuremodes import (
    FailureMode as FM, FailureModeFinder,
    _get_failure_mode_for_partial_span, _get_local_span,
)

WINDOW = 5
DOC = "The patient was admitted with a stroke after a long fever last week."

# Concept hierarchy used throughout:
#
#   root
#   ├── A
#   │   ├── B
#   │   │   └── C
#   │   └── D
#   └── E
#
# X is in the CDB but not in the hierarchy at all.
PT2CH = {"root": ["A", "E"], "A": ["B", "D"], "B": ["C"]}
ALL_CUIS = ["root", "A", "B", "C", "D", "E", "X"]
NAMES = {
    "stroke": {"per_cui_status": {"B": "P"}},
    "heart attack": {"per_cui_status": {"B": "P"}},
    "fever": {"per_cui_status": {"X": "P"}},
}
_GOLD_NAME = "stroke"
GOLD_CONTEXT = DOC[
    min(DOC.find(_GOLD_NAME) - WINDOW, 0): (
        DOC.find(_GOLD_NAME) + len(_GOLD_NAME) + WINDOW)
]


# --- fakes / helpers ---------------------------------------------------


class FakeToken:

    def __init__(self, start_char_index: int, text: str) -> None:
        self.char_index = start_char_index
        self.base = self
        self.text = text
        self.to_skip = False
        self.text_versions = [text,]

    @classmethod
    def from_proposal(
        cls,
        proposal: list[tuple[int, int, set[str]]],
    ) -> list['FakeToken']:
        if not proposal:
            return [cls(0, "")]
        prop0 = proposal[0]
        text = next(iter(prop0[-1]))
        # don't need end index for now
        out_l = [*prop0[:-2], text]
        return [cls(*out_l)]


class FakeEntity:

    def __init__(self, start_char_index: int, end_char_index: int, names: set[str], cuis: list[str]) -> None:
        self.start_char_index = start_char_index
        self.end_char_index = end_char_index
        self.names = names
        self.base = self
        self.link_candidates = cuis


class FakeDocument:

    def __init__(self, tokens: list[FakeToken], ner_ents: list[FakeEntity]) -> None:
        self.tokens = tokens
        self.ner_ents = ner_ents
        self.base = self
        self.text = " ".join(tkn.text for tkn in tokens)

    @classmethod
    def from_proposal(
        cls,
        proposal: list[tuple[int, int, set[str]]],
        cui: str,
        full_text: str = GOLD_CONTEXT,
    ) -> 'FakeDocument':
        ner_ents = [FakeEntity(*prop, cuis=[cui]) for prop in proposal]
        words = full_text.split()
        per_word_start_ends = []
        cursor = 0
        for word in words:
            per_word_start_ends.append((cursor, cursor + len(word), {word}))
            cursor += len(word) + 1
        tkns = [
            FakeToken.from_proposal([pwse])[0]
            for pwse in per_word_start_ends
        ]
        return cls(tkns, ner_ents)

    @classmethod
    def from_example(cls, example: dict, full_text: str) -> 'FakeDocument':
        ent_locs = [(example['start'], example['end'], {example['source_value']})]
        return cls.from_proposal(ent_locs, example['cui'], full_text=full_text)

    def __iter__(self):
        yield from self.tokens


def make_example(
    doc: str = DOC, value: str = "stroke", cui: str = "B",
) -> dict:
    """Build an example the way get_stats does: a window either side."""
    start = doc.index(value)
    end = start + len(value)
    return {
        "cui": cui, "start": start, "end": end, "source_value": value,
        "text": doc[max(0, start - WINDOW): end + WINDOW],
    }


GOLD = make_example()
GOLD_START, GOLD_END = GOLD["start"], GOLD["end"]
GOLD_LOCAL = (WINDOW, WINDOW + len("stroke"))


def ner_proposing(*proposals):
    """NER stand-in: always proposes the given (start, end, candidates)."""
    return lambda text: list(proposals)


def make_finder(
    *, cuis=ALL_CUIS, names=NAMES, pt2ch=PT2CH,
    allow=(), disallow=(),
) -> FailureModeFinder:
    return FailureModeFinder(
        cui2info={cui: SimpleNamespace() for cui in cuis},
        name2info=names,
        pt2ch=pt2ch,
        linking_filters=SimpleNamespace(
            cuis=set(allow), cuis_exclude=set(disallow)),
        token_separator=" ",
    )


def pred(cui: str, start: int, end: int) -> dict:
    return {"cui": cui, "start": start, "end": end}


def run(finder: FailureModeFinder, span=(), all_=(), example=GOLD, full_text=DOC) -> FM:
    mut_doc = FakeDocument.from_example(example, full_text)
    return finder.get_failure_mode(
        mut_doc, example, list(span),
        list(all_), window_size=WINDOW)


# --- span relations ----------------------------------------------------

class TestPartialSpan(unittest.TestCase):

    EXAMPLES = [
        ((5, 16), FM.SPAN_PRED_CONTAINS_GOLD),   # starts earlier
        ((10, 20), FM.SPAN_PRED_CONTAINS_GOLD),  # ends later
        ((5, 20), FM.SPAN_PRED_CONTAINS_GOLD),
        ((12, 14), FM.SPAN_GOLD_CONTAINS_PRED),
        ((10, 14), FM.SPAN_GOLD_CONTAINS_PRED),
        ((12, 16), FM.SPAN_GOLD_CONTAINS_PRED),
        ((12, 20), FM.SPAN_PARTIAL_OVERLAP),     # shifted right
        ((5, 12), FM.SPAN_PARTIAL_OVERLAP),      # shifted left
        ((16, 20), None),                        # adjacent: no overlap
        ((4, 10), None),                         # adjacent: no overlap
        ((30, 40), None),
    ]

    def test_span_relation(self):
        for pred_span, expected in self.EXAMPLES:
            with self.subTest(f"{pred_span} Exp: {expected}"):
                self._test_span_relation(pred_span, expected)

    def _test_span_relation(self, pred_span, expected):
        got = _get_failure_mode_for_partial_span("A", 10, 16, "A", *pred_span)
        self.assertIs(got, expected)

    def test_different_cui_is_ignored(self):
        self.assertIsNone(
            _get_failure_mode_for_partial_span(
                "A", 10, 16, "B", 10, 20))


class TestLocalSpan(unittest.TestCase):

    def test_mid_document(self):
        ex = make_example()
        self.assertEqual(_get_local_span(
            ex["text"], ex["start"], ex["end"], ex["source_value"], WINDOW
        ), GOLD_LOCAL)

    def test_at_document_start(self):
        ex = make_example("Stroke noted on arrival, nothing else.", "Stroke")
        self.assertEqual(_get_local_span(
            ex["text"], ex["start"], ex["end"], ex["source_value"], WINDOW
        ), (0, 6))

    def test_at_document_end(self):
        ex = make_example("Admitted with a stroke", "stroke")
        self.assertEqual(_get_local_span(
            ex["text"], ex["start"], ex["end"], ex["source_value"], WINDOW
        ), (5, 11))

    def test_value_missing_from_context_does_not_match(self):
        context = "completely different text"
        start, end = _get_local_span(context, 100, 106, "stroke", WINDOW)
        self.assertNotEqual(context[start:end], "stroke")

    # @pytest.mark.xfail(strict=True, reason=(
    #     "repeated value near a document edge: picks the occurrence closest "
    #     "to the middle of the context, not the real one"))
    def test_repeated_value_near_document_start(self):
        ex = make_example("ab ab cd efgh", "ab")
        self.assertGreater(_get_local_span(
            ex["text"], ex["start"], ex["end"], ex["source_value"], WINDOW
        ), (0, 2))


# --- hierarchy relations -----------------------------------------------

class TestDisambiguationRelation(unittest.TestCase):

    EXAMPLES = [
        ("B", "A", FM.WRONG_CONCEPT_DIRECT_PARENT),
        ("A", "B", FM.WRONG_CONCEPT_DIRECT_CHILD),
        ("B", "D", FM.WRONG_CONCEPT_SIBLING),
        ("C", "A", FM.WRONG_CONCEPT_ANCESTOR),
        ("C", "root", FM.WRONG_CONCEPT_ANCESTOR),
        ("A", "C", FM.WRONG_CONCEPT_DESCENDANT),
        ("root", "C", FM.WRONG_CONCEPT_DESCENDANT),
        # cousins: share an ancestor but not a direct parent
        ("B", "E", FM.WRONG_CONCEPT_UNRELATED),
        # not in the hierarchy at all
        ("B", "X", FM.WRONG_CONCEPT_UNRELATED),
    ]

    def test_relation(self):
        for gold, predicted, expected in self.EXAMPLES:
            with self.subTest(f"G: {gold} -> pred {predicted} = exp {expected}"):
                self._test_relation(gold, predicted, expected)

    def _test_relation(self, gold, predicted, expected):
        finder = make_finder()
        self.assertIs(finder._get_disamb_failure_mode(gold, predicted), expected)

    def test_cyclic_hierarchy_terminates(self):
        # P -> [G, Q], Q -> [P]: walking up from G cycles P -> Q -> P
        finder = make_finder(pt2ch={"P": ["G", "Q"], "Q": ["P"]})
        self.assertIs(
            finder._get_disamb_failure_mode("G", "Z"),
            FM.WRONG_CONCEPT_UNRELATED
        )
        self.assertIs(finder._get_disamb_failure_mode("Z", "G"),
            FM.WRONG_CONCEPT_UNRELATED
        )


# --- individual steps --------------------------------------------------

class TestStep0GoldSanity(unittest.TestCase):

    def test_matching_value_passes(self):
        self.assertIsNone(make_finder()._step_0_gold_sanity(
            GOLD["text"], *GOLD_LOCAL, "stroke"))

    def test_mismatching_value_flagged(self):
        self.assertIs(
            make_finder()._step_0_gold_sanity(
                GOLD["text"], *GOLD_LOCAL, "stoke"
            ),
            FM.SPAN_INCORRECT_FOR_VALUE
        )


class TestStep1NameLookup(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.gold_tkns = FakeToken.from_proposal([[GOLD_START, GOLD_END, {'stroke'}]])
        cls.unknown_name_tkns = FakeToken.from_proposal([[0, 1, {'something'}]])
        fever_start = GOLD_CONTEXT.find("fever")
        cls.fever_tkns = FakeToken.from_proposal(
            [(fever_start, fever_start + len('fever'), {'fever'})])

    def test_cui_not_in_cdb(self):
        finder = make_finder(cuis=[c for c in ALL_CUIS if c != "B"])
        self.assertIs(finder._step_1_concept_and_name_lookup(
            self.gold_tkns, "F"), FM.CUI_NOT_IN_CDB)

    def test_name_unknown(self):
        self.assertIs(make_finder()._step_1_concept_and_name_lookup(
            self.unknown_name_tkns, "B"), FM.NAME_UNKNOWN)

    def test_name_not_linked_to_cui(self):
        self.assertIs(make_finder()._step_1_concept_and_name_lookup(
            self.fever_tkns, "B"), FM.NAME_NOT_LINKED_TO_CUI)

    def test_known_name_linked_to_cui(self):
        self.assertIs(make_finder()._step_1_concept_and_name_lookup(
            self.gold_tkns, "B"), None)

    def test_any_name_variant_linking_to_gold_is_enough(self):
        # "Stroke" has the variants "Stroke" and "stroke"; only one of them
        # links to the gold concept
        names = {
            "Stroke": {"per_cui_status": {"B": "P"}},
            "stroke": {"per_cui_status": {"X": "P"}},
        }
        tkns = FakeToken.from_proposal(
            [(0, 5, {"Stroke"}), ]
        )
        self.assertIs(make_finder(names=names)._step_1_concept_and_name_lookup(
            tkns, "B"), None)


class TestStep2Ner(unittest.TestCase):

    PROPOSALS_A: list[list[tuple[int, int, set[str]]]] = [
        [],                                # nothing proposed
        [(*GOLD_LOCAL, {"X"})],            # gold not among the candidates
        [(0, 3, {"B"})],                   # elsewhere in the context
        [(11, 15, {"B"})],                 # adjacent only
    ]

    def test_ner_miss(self):
        for prop in self.PROPOSALS_A:
            with self.subTest(f"Proposal: {prop}"):
                self._test_ner_miss(prop)

    def _test_ner_miss(self, proposal: list[tuple[int, int, set[str]]]):
        finder = make_finder()
        mut_doc = FakeDocument.from_proposal(proposal, "B")
        tkns = FakeToken.from_proposal([])
        self.assertIs(finder._step_2_ner(
            mut_doc, tkns), FM.NER_NO_SPAN
        )

    PROPOSALS_B = [
        (5, 11, {"B"}),         # exact
        (3, 8, {"B"}),          # shifted: left to the span step
        (0, 20, {"B", "X"}),    # longer
        (6, 8, {"B"}),          # shorter
    ]

    def test_any_overlapping_proposal_with_gold_is_not_a_miss(self):
        for prop in self.PROPOSALS_B:
            with self.subTest(f"Proposal: {prop}"):
                self._test_any_overlapping_proposal_with_gold_is_not_a_miss(
                    prop)

    def _test_any_overlapping_proposal_with_gold_is_not_a_miss(
        self,
        proposal: list[tuple[int, int, set[str]]]
    ):
        finder = make_finder()
        mut_doc = FakeDocument.from_proposal([proposal], 'B')
        tkns = FakeToken.from_proposal([proposal])
        self.assertIsNone(finder._step_2_ner(mut_doc, tkns))


class TestStep3Filters(unittest.TestCase):

    def test_no_filters(self):
        self.assertIsNone(make_finder()._step_3_filters("B"))

    def test_not_in_allow_list(self):
        self.assertIs(
            make_finder(allow=["A"])._step_3_filters("B"),
            FM.FILTERED_NOT_IN_ALLOW_LIST
        )

    def test_in_allow_list(self):
        self.assertIsNone(make_finder(allow=["B"])._step_3_filters("B"))

    def test_in_disallow_list(self):
        self.assertIs(
            make_finder(disallow=["B"])._step_3_filters("B"),
            FM.FILTERED_DISALLOW_LIST
        )

    def test_other_concept_in_disallow_list(self):
        self.assertIsNone(make_finder(disallow=["A"])._step_3_filters("B"))


class TestStep4Disambiguation(unittest.TestCase):

    def test_nothing_predicted(self):
        self.assertIsNone(make_finder()._step_4_disambiguation([], "B", "stroke"))

    def test_relation_of_prediction(self):
        got = make_finder()._step_4_disambiguation(
            [pred("A", GOLD_START, GOLD_END)], "B", "stroke")
        self.assertIs(got, FM.WRONG_CONCEPT_DIRECT_PARENT)

    def test_multiple_predictions_pick_one_of_the_relations(self):
        got = make_finder()._step_4_disambiguation(
            [pred("A", GOLD_START, GOLD_END),
             pred("root", GOLD_START, GOLD_END)], "B", "stroke")
        self.assertIn(got, {
            FM.WRONG_CONCEPT_DIRECT_PARENT,
            FM.WRONG_CONCEPT_ANCESTOR
        })


class TestStep5PartialOverlap(unittest.TestCase):

    def test_no_predictions(self):
        self.assertIsNone(make_finder()._step_5_partial_overlap(GOLD, []))

    def test_other_concepts_are_ignored(self):
        self.assertIsNone(make_finder()._step_5_partial_overlap(
            GOLD, [pred("A", GOLD_START - 2, GOLD_END)]))

    def test_longer_prediction(self):
        got = make_finder()._step_5_partial_overlap(
            GOLD, [pred("B", GOLD_START - 2, GOLD_END)])
        self.assertIs(got, FM.SPAN_PRED_CONTAINS_GOLD)

    def test_most_common_mode_wins(self):
        got = make_finder()._step_5_partial_overlap(GOLD, [
            pred("B", GOLD_START - 2, GOLD_END),
            pred("B", GOLD_START - 3, GOLD_END),
            pred("B", GOLD_START + 2, GOLD_END + 4),
        ])
        self.assertIs(got, FM.SPAN_PRED_CONTAINS_GOLD)


# --- the whole cascade -------------------------------------------------

class TestGetFailureMode(unittest.TestCase):

    def test_falls_through_to_below_threshold(self):
        self.assertIs(run(make_finder()), FM.BELOW_THRESHOLD)

    def test_gold_at_document_start(self):
        doc = "stroke noted on arrival, nothing else."
        ex = make_example(doc, "stroke")
        finder = make_finder()
        self.assertIs(run(finder, example=ex, full_text=doc), FM.BELOW_THRESHOLD)

    def test_gold_at_document_end(self):
        doc = "Admitted with a stroke"
        ex = make_example(doc, "stroke")
        finder = make_finder()
        self.assertIs(run(finder, example=ex, full_text=doc), FM.BELOW_THRESHOLD)

    def test_sanity_beats_lookup(self):
        bad = {**GOLD, "source_value": "stoke"}
        finder = make_finder(cuis=[c for c in ALL_CUIS if c != "B"])
        self.assertIs(run(finder, example=bad), FM.SPAN_INCORRECT_FOR_VALUE)

    def test_lookup_beats_ner(self):
        finder = make_finder(names={})
        self.assertIs(run(finder), FM.NAME_UNKNOWN)

    def test_filters_beat_disambiguation(self):
        finder = make_finder(disallow=["B"])
        span = [pred("A", GOLD_START, GOLD_END)]
        self.assertIs(run(finder, span=span, all_=span), FM.FILTERED_DISALLOW_LIST)

    def test_disambiguation_beats_span(self):
        span = [pred("A", GOLD_START, GOLD_END)]
        overlapping = pred("B", GOLD_START - 2, GOLD_END)
        got = run(make_finder(), span=span, all_=[*span, overlapping])
        self.assertIs(got, FM.WRONG_CONCEPT_DIRECT_PARENT)

    def test_span_beats_threshold(self):
        overlapping = pred("B", GOLD_START - 2, GOLD_END)
        got = run(make_finder(), all_=[overlapping])
        self.assertIs(got, FM.SPAN_PRED_CONTAINS_GOLD)
