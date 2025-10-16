import os

from medcat.cdb import CDB
from medcat.utils.legacy import fixes
from medcat.utils.cdb_state import captured_state_cdb

import unittest

from ... import UNPACKED_EXAMPLE_MODEL_PACK_PATH


class TestCUI2OriginalNamesFix(unittest.TestCase):
    CONVERTED_CDB_PATH = os.path.join(
        UNPACKED_EXAMPLE_MODEL_PACK_PATH, "cdb")

    @classmethod
    def setUpClass(cls):
        cls.converted_cdb = CDB.load(cls.CONVERTED_CDB_PATH)

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
            for ci in self.converted_cdb.cui2info.values():
                with self.subTest(ci["cui"]):
                    self.assertTrue(ci["original_names"])
