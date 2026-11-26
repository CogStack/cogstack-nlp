import os
import tempfile
import unittest

from medcat.model_creation.preprocess_snomed import Snomed


REFSET_HEADER = [
    "id", "effectiveTime", "active", "moduleId", "refsetId",
    "referencedComponentId", "mapGroup", "mapPriority", "mapRule",
    "mapAdvice", "mapTarget", "correlationId", "mapCategoryId",
]
# one concept mapped to a target in each of two map groups
REFSET_ROWS = [
    ["a1", "20240101", "1", "449080006", "447562003", "1111", "1", "1",
     "TRUE", "ALWAYS E11.9", "E11.9", "447561005", "447637006"],
    ["a2", "20240101", "1", "449080006", "447562003", "1111", "2", "1",
     "TRUE", "ALWAYS Z79.4", "Z79.4", "447561005", "447637006"],
]


class SnomedRefsetMappingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        data_path = os.path.join(
            cls.temp_dir.name,
            "SnomedCT_InternationalRF2_PRODUCTION_20240101T120000Z")
        map_path = os.path.join(data_path, "Snapshot", "Refset", "Map")
        os.makedirs(map_path)
        refset_file = os.path.join(
            map_path, "der2_iisssccRefset_ExtendedMapSnapshot_INT_20240101.txt")
        with open(refset_file, "w", encoding="utf-8") as f:
            for row in [REFSET_HEADER] + REFSET_ROWS:
                f.write("\t".join(row) + "\n")
        cls.mapping = Snomed(data_path).map_snomed2icd10()

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_maps_concept_to_both_targets(self):
        self.assertEqual(
            [m['code'] for m in self.mapping["1111"]], ["E11.9", "Z79.4"])

    def test_keeps_map_group(self):
        self.assertEqual(
            [m['mapGroup'] for m in self.mapping["1111"]], ["1", "2"])

    def test_keeps_map_priority(self):
        self.assertEqual(
            [m['mapPriority'] for m in self.mapping["1111"]], ["1", "1"])


if __name__ == '__main__':
    unittest.main()
