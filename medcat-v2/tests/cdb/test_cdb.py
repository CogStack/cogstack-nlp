from typing import cast
import os

from medcat.storage.serialisers import deserialise
from medcat.cdb import cdb
from medcat.utils.cdb_state import captured_state_cdb
from medcat.preprocessors.cleaners import NameDescriptor

from unittest import TestCase

from .. import UNPACKED_EXAMPLE_MODEL_PACK_PATH


class CDBTests(TestCase):
    CDB_PATH = os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, "cdb")
    CUI_TO_REMOVE = "C03"
    NAMES_TO_REMOVE = ['high~temperature']
    TO_FILTER = ['C01', 'C02']

    @classmethod
    def setUpClass(cls):
        cls.cdb = cast(cdb.CDB, deserialise(cls.CDB_PATH))

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
