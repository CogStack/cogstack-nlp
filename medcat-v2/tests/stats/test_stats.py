from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Union

from medcat.components.types import CoreComponentType
from medcat.stats import stats
from medcat.data.mctexport import MedCATTrainerExport

from ..test_cat import TrainedModelTests


RESOURCES_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources"))


class DummyLinkingFilters:
    def __init__(self):
        self.cuis = set()
        self.cuis_exclude = set()

    def check_filters(self, cui: str) -> bool:
        return True

@dataclass
class DummyToken:
    text: str
    index: int
    start_char_index: int
    end_char_index: int

    @property
    def base(self):
        return SimpleNamespace(
            text=self.text,
            index=self.index,
            start_char_index=self.start_char_index,
            end_char_index=self.end_char_index,
        )


@dataclass
class DummyEntity:
    text: str
    start_char_index: int
    end_char_index: int
    cui: str
    context_similarity: float = 1.0
    id: int = 0
    base: SimpleNamespace = field(init=False)

    def __post_init__(self):
        self.base = SimpleNamespace(
            text=self.text,
            start_char_index=self.start_char_index,
            end_char_index=self.end_char_index,
            index=0,
        )


class DummyDocument:
    """Minimal object that behaves like a MedCAT document."""

    def __init__(self, text: str):
        self.base = SimpleNamespace(text=text)
        self.linked_ents: list[DummyEntity] = []

    def get_tokens(self, start: int, end: int):
        tokens = []
        for idx, match in enumerate(re.finditer(r"\S+", self.base.text)):
            s, e = match.span()
            if s < end and e > start:
                tokens.append(
                    DummyToken(
                        text=match.group(),
                        index=idx,
                        start_char_index=s,
                        end_char_index=e,
                    )
                )
        return tokens


class DummyTokenizer:
    def entity_from_tokens_in_doc(self, tokens, doc):
        if not tokens:
            raise ValueError("No tokens to build entity from")
        start = tokens[0].base.start_char_index
        end = tokens[-1].base.end_char_index
        text = doc.base.text[start:end]
        return DummyEntity(
            text=text,
            start_char_index=start,
            end_char_index=end,
            cui="C0004093",
            context_similarity=1.0,
        )


# these two are needed for the ner aware performance metrics
class DummyComponent:
    def get_type(self):
        return CoreComponentType.ner


class DummyPipe:
    def __init__(self):
        self.tokenizer = DummyTokenizer()
        self._components = [DummyComponent()]

    def get_component(self, comp_type):
        return self._components[0]


class DummyCAT:
    """Small fake CAT object that supports the stats API."""

    def __init__(self):
        self.config = SimpleNamespace(
            components=SimpleNamespace(
                linking=SimpleNamespace(filters=DummyLinkingFilters())
            )
        )
        self.cdb = SimpleNamespace(
            cui2info={
                "195967001": {"preferred_name": "Asthma", "names": {"asthma", "Asthma"}},
                "387458008": {"preferred_name": "Aspirin", "names": {"aspirin", "Aspirin"}},
            }
        )
        self.pipe = DummyPipe()

    def __call__(self, text: str):
        doc = DummyDocument(text)
        for mention, cui in [("asthma", "195967001"), 
                             ("aspirin", "387458008")]:
            idx = text.index(mention)
            end = idx + len(mention)
            ent = DummyEntity(
                text=mention,
                start_char_index=idx,
                end_char_index=end,
                cui=cui,
                context_similarity=1.0,
            )
            doc.linked_ents.append(ent)
        # now an incorrect prediction for testing false positives
        ent = DummyEntity(
            text="patient",
            start_char_index=text.index("patient"),
            end_char_index=text.index("patient") + len("patient"),
            cui="25609006",  # has patient
            context_similarity=1.0,
        )
        doc.linked_ents.append(ent)
        return doc


def make_fake_test_project() -> dict:
    text = "The patient has asthma and takes aspirin."
    annotations = [
        {
            "start": text.index("asthma"),
            "end": text.index("asthma") + len("asthma"),
            "cui": "195967001",
            "value": "asthma",
        },
        {
            "start": text.index("aspirin"),
            "end": text.index("aspirin") + len("aspirin"),
            "cui": "387458008",
            "value": "aspirin",
        },
        {
            "start": text.index("patient"),
            "end": text.index("patient") + len("patient"),
            "cui": "116154003",
            "value": "patient",
        }
    ]
    return {
        "name": "dummy_project",
        "id": "0",
        "cuis": "",
        "tuis": None,
        "documents": [{
            "name": "dummy_doc",
            "id": "0",
            "text": text,
            "annotations": annotations,
        }],
    }


fake_cat = DummyCAT()
test_projects = {"projects": [make_fake_test_project()]}


class StatsTests(TrainedModelTests):
    @classmethod
    def setUpClass(cls):
        cls.cat = DummyCAT()
        cls.data = {"projects": [make_fake_test_project()]}
        cls.result = stats.get_stats(
            cat=cls.cat,
            data=cls.data,
            use_project_filters=False,
            ner_performance=True,
            linking_performance=True,
            do_print=False,
        )
        
    def test_returns_StatsCollection(self) -> None:
        self.assertIsInstance(self.result, stats.StatsCollection)
        
    def test_basic_counts(self) -> None:
        # Raw counts
        self.assertEqual(self.result.all_projects.get_mode("full").stats.cui_gold_counts["195967001"], 1)
        self.assertEqual(self.result.all_projects.get_mode("full").stats.cui_gold_counts["387458008"], 1)
        self.assertEqual(self.result.all_projects.get_mode("full").stats.no_tokens, 0)
        self.assertDictEqual(self.result.all_projects.get_mode("full").stats.cui_no_tokens, {})
        
    def test_binary_statistics_full_pipe(self) -> None:
        # What we got correct
        self.assertEqual(self.result.all_projects.get_mode("full").stats.tp, 2)
        self.assertEqual(self.result.all_projects.get_mode("full").stats.cui_tp["195967001"], 1)
        self.assertEqual(self.result.all_projects.get_mode("full").stats.cui_tp["387458008"], 1)
        # The patient error, wrong linked CUI
        self.assertEqual(self.result.all_projects.get_mode("full").stats.fp, 1)
        self.assertEqual(self.result.all_projects.get_mode("full").stats.fn, 1)
        self.assertEqual(self.result.all_projects.get_mode("full").stats.cui_fp["25609006"], 1)
        self.assertEqual(self.result.all_projects.get_mode("full").stats.cui_fn["116154003"], 1)
        
    # def test_character_statistics_