from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Union
from medcat.stats.stats import MetricMode
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
                             ("aspirin", "387458008"),
                            #  patient is incorrect linkage
                             ("patient", "25609006")]:
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
        return doc
    
class DummyCATLinker:
    """Small fake CAT object that supports the stats API. Useful for testing the linker."""

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
                "116154003": {"preferred_name": "Patient", "names": {"patient", "Patient"}},
                "387517004": {"preferred_name": "Paracetamol", "names": {"paracetamol", "Paracetamol"}}
            }
        )
        self.pipe = DummyPipe()

    def __call__(self, text: str):
        doc = DummyDocument(text)
        for mention, cui in [("asthma", "195967001"), 
                             ("aspirin", "387458008"),
                             ("patient", "25609006"),
                             ("paracetamol", "387517004")]:
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
        doc.linked_ents.append(ent)
        return doc

def make_fake_test_project() -> dict:
    text = "The patient has asthma and takes aspirin, and paracetamol."
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
        { # Incorrect CUI linked
            "start": text.index("patient"),
            "end": text.index("patient") + len("patient"),
            "cui": "116154003",
            "value": "patient",
        },
        { # Didn't get NER'd
            "start": text.index("paracetamol"),
            "end": text.index("paracetamol") + len("paracetamol"),
            "cui": "387517004",
            "value": "paracetamol"
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
        cls.cat_linker = DummyCATLinker()
        cls.data = {"projects": [make_fake_test_project()]}
        cls.result = stats.get_stats_calculator(
            cat=cls.cat,
            data=cls.data,
            use_project_filters=False,
            ner_performance=True,
            linking_performance=False,
            do_print=False,
        )
        cls.linker_result = stats.get_stats_calculator(
            cat=cls.cat_linker,
            data=cls.data,
            use_project_filters=False,
            ner_performance=False,
            linking_performance=True,
            do_print=False,
        )
      
    def test_basic_counts(self) -> None:
        stats = self.result.stats.all_projects.get_mode(MetricMode.FULL).stats
        # Raw counts of the full pipeline
        self.assertEqual(stats.cui_gold_counts["195967001"], 1)
        self.assertEqual(stats.cui_gold_counts["387458008"], 1)
        self.assertEqual(stats.no_tokens, 0)
        self.assertDictEqual(stats.cui_no_tokens, {})

        ner_stats = self.result.stats.all_projects.get_mode(MetricMode.NER).stats
        # Raw counts of the NER only mode
        self.assertEqual(ner_stats.cui_gold_counts["__NER__"], 4)
        
    def test_raw_counts_full_pipe(self) -> None:
        stats = self.result.stats.all_projects.get_mode(MetricMode.FULL).stats
        # What we got correct
        self.assertEqual(stats.tp, 2)
        self.assertEqual(stats.cui_tp["195967001"], 1)
        self.assertEqual(stats.cui_tp["387458008"], 1)
        # The patient error, wrong linked CUI
        self.assertEqual(stats.fp, 1)
        self.assertEqual(stats.fn, 2)
        self.assertEqual(stats.cui_fp["25609006"], 1)
        self.assertEqual(stats.cui_fn["116154003"], 1)

    def test_raw_counts_ner_only(self) -> None:
        stats = self.result.stats.all_projects.get_mode(MetricMode.NER).stats
        # NER only will correctly fix the patient error, as it doesn't care about the CUI, just the span
        self.assertEqual(stats.tp, 3)
        self.assertEqual(stats.fp, 0)
        self.assertEqual(stats.fn, 1)

    def test_raw_counts_linking_only(self) -> None:
        stats = self.linker_result.stats.all_projects.get_mode(MetricMode.LINKING).stats
        # it's not easily possible to test the linker 
        # as predictions in the dummy set are hard coded
        self.assertEqual(stats.tp, 3)
        self.assertEqual(stats.fp, 2)
        self.assertEqual(stats.fn, 1)

    def test_precision_recall_f1(self) -> None:
        # Full pipeline
        metrics = self.result.stats.all_projects.get_mode(MetricMode.FULL).metrics.overall
        self.assertAlmostEqual(metrics.precision, 2/3)
        self.assertAlmostEqual(metrics.recall, 2/4)
        self.assertAlmostEqual(metrics.f1, 0.57, places=2)

        # NER only
        ner_pipe = self.result.stats.all_projects.get_mode(MetricMode.NER).metrics.overall
        self.assertAlmostEqual(ner_pipe.precision, 3/3)
        self.assertAlmostEqual(ner_pipe.recall, 3/4)
        self.assertAlmostEqual(ner_pipe.f1, 0.85, places=1)

        # Linking only
        linking_pipe = self.linker_result.stats.all_projects.get_mode(MetricMode.LINKING).metrics.overall
        self.assertAlmostEqual(linking_pipe.precision, 0.6)
        self.assertAlmostEqual(linking_pipe.recall, 3/4)
        self.assertAlmostEqual(linking_pipe.f1, 0.666, places=2)

    def test_per_cui_precision_recall_f1(self) -> None:
        full_pipe = self.result.stats.all_projects.get_mode(MetricMode.FULL).metrics.per_cui
        for cui in ["195967001", "387458008"]:
            self.assertAlmostEqual(full_pipe[cui].precision, 1.0)
            self.assertAlmostEqual(full_pipe[cui].recall, 1.0)
            self.assertAlmostEqual(full_pipe[cui].f1, 1.0)

        for cui in ["25609006", "116154003"]:
            self.assertAlmostEqual(full_pipe[cui].precision, 0.0)
            self.assertAlmostEqual(full_pipe[cui].recall, 0.0)
            self.assertAlmostEqual(full_pipe[cui].f1, 0.0)

        ner_pipe = self.result.stats.all_projects.get_mode(MetricMode.NER).metrics.per_cui
        self.assertAlmostEqual(ner_pipe["__NER__"].precision, 1.0)
        self.assertAlmostEqual(ner_pipe["__NER__"].recall, 0.75)
        self.assertAlmostEqual(ner_pipe["__NER__"].f1, 0.85, places=1)

    def test_cuis_exist(self) -> None:
        cui_metrics = self.result.stats.all_projects.get_mode(MetricMode.FULL).metrics.per_cui
        ner_cui_metrics = self.result.stats.all_projects.get_mode(MetricMode.NER).metrics.per_cui
        linker_cui_metrics = self.linker_result.stats.all_projects.get_mode(MetricMode.LINKING).metrics.per_cui
        self.assertIn("__NER__", ner_cui_metrics)
        self.assertNotIn("__NER__", cui_metrics)
        for cui in ["195967001", "387458008", "25609006", "116154003", "387517004"]:
            self.assertNotIn(cui, ner_cui_metrics)
            self.assertIn(cui, cui_metrics)
            self.assertIn(cui, linker_cui_metrics)

    def test_character_statistics(self) -> None:
        full_metrics = self.result.stats.all_projects.get_mode(MetricMode.FULL).metrics.overall
        # two cuis are perfect 1 + 1 = 2
        # two are incorrect 2 intersection, 5 union = 0.4
        self.assertAlmostEqual(full_metrics.char_iou, 0.4)
        # two are incorrect 2 intersection, 4 union = 0.5
        self.assertAlmostEqual(full_metrics.char_giou, 0.5)
        self.assertAlmostEqual(full_metrics.char_cohen_k, 0.45, places=1)

        ner_metrics = self.result.stats.all_projects.get_mode(MetricMode.NER).metrics.overall
        # there's only one CUI, so it's the length calculations as below
        intersection = len("asthma") + len("aspirin") + len("patient")
        union = len("asthma") + len("aspirin") + len("patient") + len("paracetamol")
        self.assertAlmostEqual(ner_metrics.char_iou, intersection/union)
        self.assertAlmostEqual(ner_metrics.char_giou, intersection/union)
        self.assertAlmostEqual(ner_metrics.char_cohen_k, 0.63, places=2)
        
        linking_metrics = self.linker_result.stats.all_projects.get_mode(MetricMode.LINKING).metrics.overall
        self.assertAlmostEqual(linking_metrics.char_iou, 0.6)
        # one is incorrect 2 intersection, 4 union = 0.5
        self.assertAlmostEqual(linking_metrics.char_giou, 0.75)
        self.assertAlmostEqual(linking_metrics.char_cohen_k, 0.6, places=1)

    def test_per_cui_character_statistics(self) -> None:
        full_metrics = self.result.stats.all_projects.get_mode(MetricMode.FULL).metrics.per_cui
        # 195967001 and 387458008 are perfect, so IoU = 1
        self.assertAlmostEqual(full_metrics["195967001"].char_iou, 1.0)
        self.assertAlmostEqual(full_metrics["387458008"].char_iou, 1.0)
        # 25609006 and 116154003 are incorrect, so IoU = 0
        self.assertAlmostEqual(full_metrics["25609006"].char_iou, 0.0)
        self.assertAlmostEqual(full_metrics["116154003"].char_iou, 0.0)

        ner_metrics = self.result.stats.all_projects.get_mode(MetricMode.NER).metrics.per_cui
        # there's only one CUI, so it's the length calculations as below
        # same as previous!
        intersection = len("asthma") + len("aspirin") + len("patient")
        union = len("asthma") + len("aspirin") + len("patient") + len("paracetamol")
        self.assertAlmostEqual(ner_metrics["__NER__"].char_iou, intersection/union)
        self.assertAlmostEqual(ner_metrics["__NER__"].char_giou, intersection/union)
        self.assertAlmostEqual(ner_metrics["__NER__"].char_cohen_k, 0.63, places=2)
        
        linker_metrics = self.linker_result.stats.all_projects.get_mode(MetricMode.LINKING).metrics.per_cui
        self.assertAlmostEqual(linker_metrics["195967001"].char_iou, 1.0)
        self.assertAlmostEqual(linker_metrics["387458008"].char_iou, 1.0)
        self.assertAlmostEqual(linker_metrics["25609006"].char_iou, 0.0)
        self.assertAlmostEqual(linker_metrics["116154003"].char_iou, 0.0)
        self.assertAlmostEqual(linker_metrics["387517004"].char_iou, 1.0)
        