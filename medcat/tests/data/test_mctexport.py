import os
import json

from medcat.data import mctexport
import pydantic

import unittest


MCTExportPydanticModel = pydantic.TypeAdapter(mctexport.MedCATTrainerExport)


class MCTExportIterationTests(unittest.TestCase):
    EXPORT_PATH = os.path.join(os.path.dirname(__file__), "..",
                               "resources", "medcat_trainer_export.json")
    EXPECTED_DOCS = 27
    EXPECTED_ANNS = 435

    @classmethod
    def setUpClass(cls) -> None:
        with open(cls.EXPORT_PATH) as f:
            cls.mct_export: mctexport.MedCATTrainerExport = json.load(f)

    def assert_is_mct_export(self, mct_export: dict):
        model_instance = MCTExportPydanticModel.validate_python(mct_export)
        self.assertIsInstance(model_instance, dict)
        # NOTE: otherwise would have raised an exception

    def test_conforms_to_template(self):
        self.assert_is_mct_export(self.mct_export)

    def test_iterates_over_all_docs(self):
        self.assertEqual(mctexport.count_all_docs(self.mct_export),
                         self.EXPECTED_DOCS)

    def test_iterates_over_all_anns(self):
        self.assertEqual(mctexport.count_all_annotations(self.mct_export),
                         self.EXPECTED_ANNS)

    def test_gets_correct_nr_of_annotations_per_doc(self):
        for project in self.mct_export['projects']:
            for doc in project["documents"]:
                with self.subTest(
                    f"Proj-{project['name']} "
                        f"({project['id']})-{doc['name']} ({doc['id']})"):
                    self.assertEqual(mctexport.get_nr_of_annotations(doc),
                                     len(doc["annotations"]))
