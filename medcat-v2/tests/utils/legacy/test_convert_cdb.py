import os

from medcat.utils.legacy import convert_cdb
from medcat.cdb import CDB

import unittest

from .test_convert_config import TESTS_PATH


class CDBConversionTest(unittest.TestCase):
    FILE_PATH = os.path.join(TESTS_PATH, "resources", "mct_v1_cdb.dat")
    EXP_CUIS = 5

    @classmethod
    def setUpClass(cls):
        cls.cdb = convert_cdb.get_cdb_from_old(cls.FILE_PATH)

    def test_conversion_works(self):
        self.assertIsInstance(self.cdb, CDB)

    def test_has_concepts(self):
        self.assertTrue(self.cdb.cui2info)
        self.assertEqual(len(self.cdb.cui2info), self.EXP_CUIS)

    def test_has_names(self):
        self.assertTrue(self.cdb.name2info)

    def test_all_cui_names_in_names(self):
        for cui, cui_info in self.cdb.cui2info.items():
            for name in cui_info['names']:
                with self.subTest(f"{cui}: {name}"):
                    self.assertIn(name, self.cdb.name2info)

    def test_all_cuis_have_original_names(self):
        for cui, ci in self.cdb.cui2info.items():
            with self.subTest(cui):
                print(cui, ":", ci["original_names"])
                self.assertTrue(ci["original_names"])

    def test_all_name_cuis_in_per_cui_status(self):
        for name, nameinfo in self.cdb.name2info.items():
            for cui in nameinfo['per_cui_status']:
                with self.subTest(f"{name}: {cui}"):
                    self.assertIn(cui, self.cdb.cui2info)
