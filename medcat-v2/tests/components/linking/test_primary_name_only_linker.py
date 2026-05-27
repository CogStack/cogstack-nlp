import os

from medcat.cdb import CDB
from medcat.cat import CAT
from medcat.vocab import Vocab
from medcat.components.linking.only_primary_name_linker import (
    PrimNameLinker)

import unittest

from ... import UNPACKED_EXAMPLE_MODEL_PACK_PATH


EXAMPLE_CDB_PATH = os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, "cdb")
EXAMPLE_VOCAB_PATH = os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, "vocab")


class PrimaryNamesLinkerTests(unittest.TestCase):
    TEXT = (
        "Man was diagnosed with severe kidney failure and acute diabetes "
        "and presented with a light fever")

    @classmethod
    def setUpClass(cls):
        vocab = Vocab.load(EXAMPLE_VOCAB_PATH)
        cdb = CDB.load(EXAMPLE_CDB_PATH)
        cdb.config.components.linking.comp_name = PrimNameLinker.name
        cls.cat = CAT(cdb, vocab)

    def test_gets_entities(self):
        ents = self.cat.get_entities(self.TEXT)
        self.assertTrue(ents)
        self.assertTrue(len(ents["entities"]))
