from typing import cast
import os

from medcat2.storage.serialisers import deserialise
from medcat2.cdb import cdb
from medcat2.utils.cdb_state import captured_state_cdb

from unittest import TestCase

from .. import UNPACKED_EXAMPLE_MODEL_PACK_PATH


class CDBTests(TestCase):
    CDB_PATH = os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, "cdb")
    CUI_TO_REMOVE = "C03"
    NAMES_TO_REMOVE = ['high~temperature']

    @classmethod
    def setUpClass(cls):
        cls.cdb = cast(cdb.CDB, deserialise(cls.CDB_PATH))

    def test_cdb_has_concepts(self):
        self.assertTrue(self.cdb.cui2info)

    def test_cdb_has_names(self):
        self.assertTrue(self.cdb.name2info)

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
