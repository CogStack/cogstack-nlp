from medcat.config import Ner
from medcat.storage.serialisers import serialise, deserialise
from medcat.storage.serialisers import AvailableSerialisers

import os
import tempfile

import unittest


class SaveWithExtraTests(unittest.TestCase):
    EXTRA_KEY = "some_extra_key"
    EXTRA_VAL = {"val": 1, "f": ''}

    def setUp(self):
        self.base = Ner()
        self.base.some_extra_key = self.EXTRA_VAL
        self.temp_dir = tempfile.TemporaryDirectory()

    def do_save(self) -> tuple[str, str]:
        """Do the save and return folder path and raw dict path.

        Returns:
            tuple[str, str]: The folder and the path to raw dict.
        """
        serialise(AvailableSerialisers.dill, self.base, self.temp_dir.name)
        return self.temp_dir.name, os.path.join(self.temp_dir.name,
                                                "raw_dict.dat")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_value_is_set(self):
        self.assertTrue(hasattr(self.base, self.EXTRA_KEY))
        self.assertIs(getattr(self.base, self.EXTRA_KEY), self.EXTRA_VAL)

    def test_can_save_and_load_obj(self):
        folder, _ = self.do_save()
        other = deserialise(folder)
        self.assertIsInstance(other, type(self.base))
        self.assertEqual(other, self.base)

    def test_loaded_has_extra_key(self):
        folder, _ = self.do_save()
        other = deserialise(folder)
        self.assertTrue(hasattr(other, self.EXTRA_KEY))
        self.assertEqual(getattr(other, self.EXTRA_KEY), self.EXTRA_VAL)
