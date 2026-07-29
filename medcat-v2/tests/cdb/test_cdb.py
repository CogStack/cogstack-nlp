from typing import cast
import os

from medcat.storage.serialisers import deserialise
from medcat.config import Config
from medcat.cdb import cdb
from medcat.utils.cdb_state import captured_state_cdb
from medcat.preprocessors.cleaners import NameDescriptor

import pandas as pd
from unittest import TestCase
import tempfile

from .. import UNPACKED_EXAMPLE_MODEL_PACK_PATH, RESOURCES_PATH
from .. import UNPACKED_V1_MODEL_PACK_PATH


ZIPPED_CDB_PATH = os.path.join(RESOURCES_PATH, "mct2_cdb.zip")


class CDBTests(TestCase):
    CDB_PATH = os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, "cdb")
    LEGACY_CDB_PATH = os.path.join(UNPACKED_V1_MODEL_PACK_PATH, "cdb.dat")
    CUI_TO_REMOVE = "C03"
    NAMES_TO_REMOVE = ['high~temperature']
    TO_FILTER = ['C01', 'C02']

    @classmethod
    def setUpClass(cls):
        cls.cdb = cast(cdb.CDB, deserialise(cls.CDB_PATH))

    def test_convenience_method_save(self):
        with tempfile.TemporaryDirectory() as dir:
            self.cdb.save(dir)
            self.assertTrue(os.path.exists(dir))
            # should have a non-empty directory
            self.assertTrue(os.listdir(dir))
            obj = deserialise(dir)
            self.assertIsInstance(obj, cdb.CDB)

    def test_can_load_from_zip(self):
        loaded = cdb.CDB.load(ZIPPED_CDB_PATH)
        self.assertIsInstance(loaded, cdb.CDB)
        # make sure it's actually a file not a folder
        self.assertTrue(os.path.isfile(ZIPPED_CDB_PATH))

    def test_can_convert_legacy_upon_load(self):
        loaded = cdb.CDB.load(self.LEGACY_CDB_PATH)
        self.assertIsInstance(loaded, cdb.CDB)

    def test_can_save_to_zip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_name = os.path.join(temp_dir, "cdb.zip")
            # NOTE: auto detection should write as zip
            self.cdb.save(file_name)
            self.assertTrue(os.path.exists(file_name))
            self.assertTrue(os.path.isfile(file_name))
            # and can load from saved zip
            loaded = cdb.CDB.load(file_name)
            self.assertIsInstance(loaded, cdb.CDB)

    def test_convenience_method_load(self):
        ccdb = cdb.CDB.load(self.CDB_PATH)
        self.assertIsInstance(ccdb, cdb.CDB)

    def test_cdb_has_concepts(self):
        self.assertTrue(self.cdb.cui2info)

    def test_cdb_has_names(self):
        self.assertTrue(self.cdb.name2info)

    def test_can_add_cui(self):
        cui = "C-NEW"
        names = {"new~cui": NameDescriptor(tokens=['new', 'cui'],
                                           snames={'new', 'new~cdb'},
                                           raw_name='new cdb',
                                           is_upper=False)}
        with captured_state_cdb(self.cdb):
            self.cdb.add_names(cui, names)
            self.assertIn(cui, self.cdb.cui2info)
            self.assertIn(list(names.keys())[0], self.cdb.name2info)
            for sname in names['new~cui'].snames:
                with self.subTest(f"Subname: {sname} of {cui} | "
                                  f"({list(names.keys())[0]})"):
                    self.assertIn(sname, self.cdb._subnames)

    def test_can_remove_name(self):
        cui = self.CUI_TO_REMOVE
        to_remove = self.NAMES_TO_REMOVE
        with captured_state_cdb(self.cdb):
            self.cdb._remove_names(cui, to_remove)
            for name_to_remove in to_remove:
                if name_to_remove in self.cdb.name2info:
                    ni = self.cdb.name2info[name_to_remove]
                    self.assertNotIn(cui, ni['per_cui_status'])
                else:
                    self.assertNotIn(name_to_remove, self.cdb.name2info)

    # filtering
    def test_can_filter_cdb(self):
        to_filter = self.TO_FILTER
        # NOTE: this does not always guarantee other CUIs are removed
        #       if there's a lot of overlap between concept names.
        #       see docstring of CDB.filter_by_cui
        removed_cui = set(self.cdb.cui2info) - set(to_filter)
        with captured_state_cdb(self.cdb):
            self.cdb.filter_by_cui(self.TO_FILTER)
            self.assertEqual(len(self.cdb.cui2info), len(self.TO_FILTER))
            self.assertEqual(set(self.TO_FILTER), set(self.cdb.cui2info))
            for removed in removed_cui:
                self.assertNotIn(removed, self.cdb.cui2info)

    CUI_TO_REMOVE_UNIQUE_NAMES = 'C03'

    def assert_removed_names(self, cui_to_remove: str, had_names: list[str],
                             should_remove_name_info: bool):
        if should_remove_name_info:
            for removed_name in had_names:
                with self.subTest(f"Removed name[KNI]: {removed_name}"):
                    self.assertNotIn(removed_name, self.cdb.name2info)
        else:
            # may keep SOME names' name info but not ALL
            self.assertTrue(any(name not in self.cdb.name2info
                                for name in had_names))
            for removed_name in had_names:
                if removed_name not in self.cdb.name2info:
                    continue  # removed as expexted
                with self.subTest(f"Removed name[RNI]: {removed_name}"):
                    ni = self.cdb.name2info[removed_name]
                    self.assertNotIn(cui_to_remove, ni['per_cui_status'])

    def assert_can_remove_cui(self, cui_to_remove: str,
                              should_remove_name_info: bool):
        had_names = self.cdb.cui2info[cui_to_remove]['names']
        with captured_state_cdb(self.cdb):
            self.cdb.remove_cui(cui_to_remove)
            self.assert_removed_names(
                cui_to_remove, had_names, should_remove_name_info)
            self.assertNotIn(cui_to_remove, self.cdb.cui2info)

    def test_can_remove_cui_unique_names(self):
        self.assert_can_remove_cui(self.CUI_TO_REMOVE_UNIQUE_NAMES, True)

    CUI_TO_REMOVE_NON_UNIQUE_NAMES = 'C04'

    def test_can_remove_cui_non_unique_names(self):
        self.assert_can_remove_cui(self.CUI_TO_REMOVE_NON_UNIQUE_NAMES, False)


class CDBWithBrokenState(TestCase):
    CUIS_NAMES = {
        "C001": ["kidney failure", "renal disease"],
        "C002": ["diabetes", "diabetes mellitus"],
        "C003": ["diabetes", "type 2 diabetes"],
        "C004": ["fever", "high temperature"],
    }
    TO_UNMAP = {
        # we unmap this CUI from diabetes
        "C003": ["diabetes", "diabete"]
    }

    def setUp(self) -> None:
        self.cnf = Config()
        self.cnf.general.nlp.provider = 'spacy'
        self.cdb = cdb.CDB(self.cnf)
        self._create_cdb()
        self._break_cdb()
        self.safe_to_remove = {
            cui for cui in self.CUIS_NAMES
            if cui not in self.TO_UNMAP
        }
        self.unsafe_to_remove = set(self.TO_UNMAP)

    def _break_cdb(self):
        for cui, names in self.TO_UNMAP.items():
            for name in names:
                ni = self.cdb.name2info.get(name)
                if ni is None:
                    continue
                if cui in ni["per_cui_status"]:
                    del ni["per_cui_status"][cui]

    def _create_cdb(self):
        from medcat.model_creation.cdb_maker import CDBMaker
        maker = CDBMaker(self.cnf, self.cdb)
        data = {
            "cui": [cui for cui, names in self.CUIS_NAMES.items() for _ in names],
            "name": [name for _, names in self.CUIS_NAMES.items() for name in names],
        }
        df = pd.DataFrame(data)
        maker.prepare_csvs([df])

    def test_has_all_cuis(self):
        self.assertEqual(len(self.cdb.cui2info), len(self.CUIS_NAMES))

    def test_has_all_names(self):
        # NOTE: all names are kept, but not all mappings
        expected = set(
            name for names in self.CUIS_NAMES.values()
            for name in names)
        found = set(self.cdb.name2info)
        # NOTE: the preprocessing may create a singular form
        self.assertGreaterEqual(
            len(found), len(expected),
            f"Exepcted:\n{expected}\nFound:\n{found}"
        )

    def test_can_remove_one_regular(self):
        for cui in self.safe_to_remove:
            with self.subTest(f"Removing: {cui}"):
                self.cdb.remove_cui(cui)
                self.assertNotIn(cui, self.cdb.cui2info)

    def test_can_remove_unsafe_one(self):
        for cui in self.unsafe_to_remove:
            with self.subTest(f"Removing {cui}"):
                self.cdb.remove_cui(cui)
                self.assertNotIn(cui, self.cdb.cui2info)

    def test_can_filter_down_to_unsafe_cuis(self):
        safe_but_no_same_names = {
            cui for cui in self.safe_to_remove
            if not any(
                any(
                    uscui in self.cdb.name2info[name]["per_cui_status"]
                    for uscui in self.unsafe_to_remove
                ) or any(
                    name in self.cdb.cui2info[uscui]["names"]
                    for uscui in self.unsafe_to_remove
                )
                for name in self.cdb.cui2info[cui]["names"]
            )
        }
        self.cdb.filter_by_cui(self.unsafe_to_remove)
        for other in safe_but_no_same_names:
            with self.subTest(f"Checking {other}"):
                self.assertNotIn(other, self.cdb.cui2info)

    def test_can_filter_down_to_safe_cuis(self):
        self.cdb.filter_by_cui(self.safe_to_remove)
        for other in self.unsafe_to_remove:
            with self.subTest(f"Checking {other}"):
                self.assertNotIn(other, self.cdb.cui2info)
