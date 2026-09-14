import os

from medcat.cdb import CDB
from medcat.utils.legacy import fixes
from medcat.utils.cdb_state import captured_state_cdb

import unittest

from ... import UNPACKED_EXAMPLE_MODEL_PACK_PATH


CONVERTED_CDB_PATH = os.path.join(
    UNPACKED_EXAMPLE_MODEL_PACK_PATH, "cdb")


class TestCUI2OriginalNamesFix(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.converted_cdb = CDB.load(CONVERTED_CDB_PATH,
                                     perform_fixes=False)

    def test_converted_model_does_not_have_orig_names(self):
        for ci in self.converted_cdb.cui2info.values():
            with self.subTest(ci["cui"]):
                self.assertFalse(ci["original_names"])

    def test_model_has_orig_names_after_fix(self):
        # to make sure this is agnostic to the order
        with captured_state_cdb(self.converted_cdb):
            changed = fixes.fix_cui2original_names_if_needed(
                self.converted_cdb)
            self.assertTrue(changed)
            # has not cui2original_names
            self.assertNotIn("cui2original_names",
                             self.converted_cdb.addl_info)
            for ci in self.converted_cdb.cui2info.values():
                with self.subTest(ci["cui"]):
                    self.assertTrue(ci["original_names"])

    def test_will_not_fix_twice(self):
        with captured_state_cdb(self.converted_cdb):
            fixes.fix_cui2original_names_if_needed(
                self.converted_cdb)
            changed_twice = fixes.fix_cui2original_names_if_needed(
                self.converted_cdb)
            self.assertFalse(changed_twice)


class TestCUI2OriginalNamesFixAuto(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.converted_cdb = CDB.load(CONVERTED_CDB_PATH,
                                     perform_fixes=True)

    def test_cui2orig_names_fixed_automatically(self):
        for ci in self.converted_cdb.cui2info.values():
            with self.subTest(ci["cui"]):
                self.assertTrue(ci["original_names"])

    def test_addl_info_has_no_cui2original_names(self):
        self.assertNotIn("cui2original_names", self.converted_cdb.addl_info)
