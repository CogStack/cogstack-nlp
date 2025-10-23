
import os
import sys

import pandas as pd

import unittest

from medcat_den.injection import injected_den


_FILE_DIR = os.path.dirname(__file__)

# because this project isn't (at least of of writing this)
# set up as a python project, there are no __init__.py
# files in each folder
# as such, in order to gain access to the relevant module,
# I'll need to add the path manually
_ROOT_FOLDER = os.path.join(_FILE_DIR, "..", "..")
MEDCAT_EVAL_MCT_EXPORT_FOLDER = os.path.abspath(
    os.path.join(_ROOT_FOLDER, "evaluate_mct_export"))
sys.path.append(MEDCAT_EVAL_MCT_EXPORT_FOLDER)
# and now we can import from mct_analysis
from mct_analysis import MedcatTrainer_export


# add path to MCT export
RESOURCE_DIR = os.path.abspath(os.path.join(_FILE_DIR, "..", "resources"))
MCT_EXPORT_JSON_PATH = os.path.join(RESOURCE_DIR, "MCT_export_example.json")


EXAMPLE_MODEL_HASH = "a645742030cae7be"


class MCTExportInitTests(unittest.TestCase):

    def test_can_init(self):
        inst = MedcatTrainer_export([MCT_EXPORT_JSON_PATH, ], None)
        self.assertIsInstance(inst, MedcatTrainer_export)


class BaseMCTExportTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.export = MedcatTrainer_export([MCT_EXPORT_JSON_PATH, ], None)

    def assertNonEmptyDataframe(self, df):
        self.assertIsInstance(df, pd.DataFrame)
        self.assertFalse(df.empty)


class MCTExportBasicTests(BaseMCTExportTests):

    def test_can_get_annotations(self):
        annotation_df = self.export.annotation_df()
        self.assertNonEmptyDataframe(annotation_df)

    def test_can_get_summary(self):
        summary_df = self.export.concept_summary()
        self.assertNonEmptyDataframe(summary_df)

    def test_can_get_user_stats(self):
        users_stats = self.export.user_stats()
        self.assertNonEmptyDataframe(users_stats)

    def test_can_rename_meta_anns_empty_no_change(self):
        ann_df1 = self.export.annotation_df()
        self.export.rename_meta_anns()
        ann_df2 = self.export.annotation_df()
        self.assertTrue(all(ann_df1 == ann_df2))


class MCTExportUsageTests(BaseMCTExportTests):

    def assertDataFrameHasRowsColumns(self, df,
                                      exp_rows: int,
                                      exp_columns: int):
        self.assertEqual(len(df.index), exp_rows)
        self.assertEqual(len(df.columns), exp_columns)

    def test_has_correct_projects(self, exp_proj=['MartTestAnnotation']):
        got = self.export.project_names
        self.assertEqual(len(got), len(exp_proj))
        self.assertEqual(got, exp_proj)

    def test_has_correct_documents(self, exp_docs=[
            'Doc 1', 'Doc 2', 'Doc 3', 'Doc 4', 'Doc 5']):
        got = self.export.document_names
        self.assertEqual(len(got), len(exp_docs))
        self.assertEqual(got, exp_docs)

    def test_rename_meta_anns_empty_does_not_add_project_and_doc_names(self):
        self.export.rename_meta_anns()
        self.test_has_correct_projects()
        self.test_has_correct_documents()

    def test_annotations_has_correct_rows_columns(self,
                                                  exp_rows=362,
                                                  exp_columns=19):
        ann_df = self.export.annotation_df()
        self.assertDataFrameHasRowsColumns(ann_df, exp_rows, exp_columns)

    def test_summary_has_correct_rows_columns(self,
                                              exp_rows=197,
                                              exp_columns=5):
        summary_df = self.export.concept_summary()
        self.assertDataFrameHasRowsColumns(summary_df, exp_rows, exp_columns)

    def test_cuser_stats_has_correct_rows_columns(self,
                                                  exp_rows=1,
                                                  exp_columns=2):
        users_stats = self.export.user_stats()
        self.assertDataFrameHasRowsColumns(users_stats, exp_rows, exp_columns)

    def test_cuser_stats_has_correct_user(self, expected="mart"):
        unique_users = self.export.user_stats()["user"].unique().tolist()
        self.assertEqual(len(unique_users), 1)
        self.assertEqual(unique_users[0], expected)


class MCTExportMetaAnnRenameTests(unittest.TestCase):
    NAMES2RENAME = {"Status": "VERSION"}
    VALUES2RENAME = {"Status": {"Affirmed": "Got it!"}}
    # can only rename values if renaming names
    # so need a mapping from the same name to the same name
    # for each name used in values
    VALUES_RENAME_HELPER = dict((n, n) for n in VALUES2RENAME)

    def setUp(self) -> None:
        self.export = MedcatTrainer_export([MCT_EXPORT_JSON_PATH, ], None)

    def _get_all_meta_anns(self):
        for proj in self.export.mct_export['projects']:
            for doc in proj['documents']:
                for ann in doc['annotations']:
                    for meta_ann in ann["meta_anns"].items():
                        yield meta_ann

    def _check_names(self, prev_anns: list):
        for (meta_ann_name, _), (prev_name, _) in zip(
                self._get_all_meta_anns(), prev_anns):
            for name, replacement_name in self.NAMES2RENAME.items():
                with self.subTest(
                        f"{name} -> {replacement_name} ({meta_ann_name})"):
                    self.assertNotEqual(meta_ann_name, name)
                    if prev_name == name:
                        self.assertEqual(meta_ann_name, replacement_name)

    def test_meta_annotations_renamed_names(self):
        prev_anns = list(self._get_all_meta_anns())
        self.export.rename_meta_anns(meta_anns2rename=self.NAMES2RENAME)
        self._check_names(prev_anns)

    def _check_values(self, prev_anns: list, only_values: bool = True):
        for (name, ann), (prev_name, prev_ann) in zip(
                self._get_all_meta_anns(), prev_anns):
            with self.subTest(f"{prev_ann} -> {ann}"):
                if only_values:
                    # if only changing values, not names themselves
                    self.assertEqual(name, prev_name, "Names should not change")
                for target_name, value_map in self.VALUES2RENAME.items():
                    # if correct target and has a value that can be remapped
                    if name == target_name and prev_ann["value"] in value_map:
                        with self.subTest(f"{target_name} with {value_map}"):
                            start_value = prev_ann["value"]
                            new_value = ann["value"]
                            exp_value = value_map[start_value]
                            self.assertEqual(new_value, exp_value)

    def test_meta_annotations_renamed_values(self):
        prev_anns = list(self._get_all_meta_anns())
        self.export.rename_meta_anns(
            meta_anns2rename=self.VALUES_RENAME_HELPER,
            meta_ann_values2rename=self.VALUES2RENAME)
        self._check_values(prev_anns)

    def test_meta_annotations_renamed_names_and_values(self):
        prev_anns = list(self._get_all_meta_anns())
        self.export.rename_meta_anns(
            meta_anns2rename=self.NAMES2RENAME,
            meta_ann_values2rename=self.VALUES2RENAME)
        self._check_names(prev_anns)
        self._check_values(prev_anns, only_values=False)

    def test_meta_annotations_renamed_values_only(self):
        prev_anns = list(self._get_all_meta_anns())
        self.export.rename_meta_anns(meta_ann_values2rename=self.VALUES2RENAME)
        self._check_values(prev_anns, only_values=True)


class MCTExportWithModelTests(BaseMCTExportTests):

    @classmethod
    def setUpClass(cls):
        with injected_den():
            cls.export = MedcatTrainer_export(
                [MCT_EXPORT_JSON_PATH, ], EXAMPLE_MODEL_HASH)

    def test_can_get_full_df(self):
        full_df = self.export.full_annotation_df()
        self.assertNonEmptyDataframe(full_df)
