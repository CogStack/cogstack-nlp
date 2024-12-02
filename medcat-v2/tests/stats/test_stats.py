from typing import Union
import os
import json

from medcat2.stats import stats
from medcat2.data.mctexport import MedCATTrainerExport

from ..test_cat import TrainedModelTests


RESOURCES_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "resources"))


class PerfectStatsTests(TrainedModelTests):
    PERFECT_STATS_PATH = os.path.join(RESOURCES_PATH,
                                      "mct_export_for_test_exp_perfect.json")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(cls.PERFECT_STATS_PATH) as f:
            cls.data: MedCATTrainerExport = json.load(f)
        (cls.fps, cls.fns, cls.tps, cls.prec, cls.rec, cls.f1,
         cls.counts, cls.examples) = stats.get_stats(cls.model, cls.data)

    def _iter_anns(self):
        for proj in self.data["projects"]:
            for doc in proj["documents"]:
                text = doc["text"]
                for ann in doc["annotations"]:
                    yield proj, doc, text, ann

    # just a sanity check
    def test_check_export_is_valid(self):
        for proj, doc, text, ann in self._iter_anns():
            start, end, value = ann["start"], ann['end'], ann['value']
            with self.subTest(f"{proj['name']} ({proj['id']}): "
                              f"{doc['name']} ({doc['id']}) -> "
                              f"{ann['cui']} ({value}) @ "
                              f"{start}...{end}"):
                detexted_value = text[start:end]
                self.assertEqual(detexted_value, value)

    def assert_perfect_dict(self, d: dict[str, Union[float, int]]) -> None:
        for cui, f1 in d.items():
            with self.subTest(cui):
                self.assertEqual(f1, 1)

    def test_gets_perfect_f1(self):
        self.assert_perfect_dict(self.f1)

    def test_gets_perfect_prec(self):
        self.assert_perfect_dict(self.prec)

    def test_gets_perfect_rec(self):
        self.assert_perfect_dict(self.rec)

    def test_no_fps(self):
        self.assertFalse(self.fps)

    def test_no_fns(self):
        self.assertFalse(self.fns)

    def test_has_counts_for_concepts(self):
        for cui in self.model.cdb.cui2info:
            with self.subTest(cui):
                cnts = self.counts.get(cui, 0)
                self.assertGreater(cnts, 0)
