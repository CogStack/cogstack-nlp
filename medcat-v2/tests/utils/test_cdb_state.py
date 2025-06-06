import unittest
import os
from unittest import mock
from typing import Callable, Any, Dict
import tempfile
import json

import numpy as np

from medcat.config.config import ModelMeta
from medcat.utils.cdb_state import (
    captured_state_cdb, CDBState, copy_cdb_state, _get_attr)
from medcat.storage.serialisers import deserialise
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.cat import CAT

from .. import UNPACKED_EXAMPLE_MODEL_PACK_PATH


def load_cdb(path: str) -> CDB:
    return deserialise(path)


def load_vocab(path: str) -> Vocab:
    return deserialise(path)


class StateTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.cdb = load_cdb(
            os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, "cdb"))
        cls.vocab = load_vocab(
            os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, "vocab"))
        cls.vocab.init_cumsums()
        cls.cdb.config.general.nlp.modelname = "en_core_web_md"
        cls.meta_cat_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "tmp")
        cls.undertest = CAT(cdb=cls.cdb, config=cls.cdb.config,
                            vocab=cls.vocab)
        cls.initial_state = copy_cdb_state(cls.cdb)

    @classmethod
    def _set_info(cls, k: str, v: Any, info_dict: Dict):
        info_dict[k] = (len(v), len(str(v)))

    @classmethod
    def do_smth_for_each_state_var(cls, cdb: CDB,
                                   callback: Callable[[str, Any], None]
                                   ) -> None:
        for k in CDBState.__annotations__:
            v = _get_attr(cdb, k)
            callback(k, v)

    def assertDictWithNdarrayEqual(self, dict1: dict, dict2: dict):
        self.assertEqual(dict1.keys(), dict2.keys())
        for key in dict1:
            val1, val2 = dict1[key], dict2[key]
            if isinstance(val1, np.ndarray):
                self.assertTrue(
                    np.array_equal(val1, val2),
                    f"Arrays at {key} are not equal: {val1} vs {val2}")
            elif isinstance(val1, dict):
                self.assertDictWithNdarrayEqual(val1, val2)
            else:
                self.assertEqual(
                    val1, val2,
                    f"Values at {key} are not equal: {val1} vs {val2}")

    def assertStateEqual(self, state1: CDBState, state2: CDBState):
        self.assertDictWithNdarrayEqual(state1, state2)


class StateSavedTests(StateTests):
    on_disk = False

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # capture state
        with captured_state_cdb(cls.cdb, save_state_to_disk=cls.on_disk):
            # clear state
            cls.do_smth_for_each_state_var(
                cls.cdb, lambda k, v: v.clear()
                if isinstance(v, (dict, set, list)) else None)
            cls.cleared_state = copy_cdb_state(cls.cdb)
        # save after state - should be equal to before
        cls.restored_state = copy_cdb_state(cls.cdb)

    def test_state_saved(self):
        nr_of_targets = len(CDBState.__annotations__)
        self.assertGreater(nr_of_targets, 0)
        self.assertEqual(len(self.initial_state), nr_of_targets)
        self.assertEqual(len(self.cleared_state), nr_of_targets)
        self.assertEqual(len(self.restored_state), nr_of_targets)

    def test_clearing_worked(self):
        self.assertNotEqual(self.initial_state, self.cleared_state)
        for k, v in self.cleared_state.items():
            with self.subTest(k):
                # length is 0
                if isinstance(v, ModelMeta):
                    self.assertFalse(v.unsup_trained)
                    self.assertFalse(v.sup_trained)
                else:
                    self.assertFalse(v)

    def test_state_restored(self):
        self.assertStateEqual(self.initial_state, self.restored_state)


class StateSavedOnDiskTests(StateSavedTests):
    on_disk = True
    _named_tempory_file = tempfile.NamedTemporaryFile

    @classmethod
    def saved_name_temp_file(cls):
        tf = cls._named_tempory_file()
        cls.temp_file_name = tf.name
        return tf

    @classmethod
    def setUpClass(cls) -> None:
        with mock.patch("builtins.open", side_effect=open) as cls.popen:
            with mock.patch("tempfile.NamedTemporaryFile",
                            side_effect=cls.saved_name_temp_file) as cls.pntf:
                return super().setUpClass()

    def test_temp_file_called(self):
        self.pntf.assert_called_once()

    def test_saved_on_disk(self):
        self.popen.assert_called()
        self.assertGreaterEqual(self.popen.call_count, 2)
        self.popen.assert_has_calls([mock.call(self.temp_file_name, 'wb'),
                                     mock.call(self.temp_file_name, 'rb')])


class StateWithTrainingTests(StateTests):
    SUPERVISED_TRAINING_JSON = os.path.join(
        os.path.dirname(__file__), "..", "resources",
        "mct_export_for_test_exp_perfect.json")

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        with captured_state_cdb(cls.cdb):
            # do training
            with open(cls.SUPERVISED_TRAINING_JSON) as f:
                data = json.load(f)
            cls.undertest.trainer.train_supervised_raw(data)
            cls.after_train_state = copy_cdb_state(cls.cdb)
        cls.restored_state = copy_cdb_state(cls.cdb)


class StateRestoredAfterTrain(StateWithTrainingTests):

    def test_train_state_changed(self):
        self.assertNotEqual(self.initial_state, self.after_train_state)

    def test_restored_state_same(self):
        self.assertStateEqual(self.initial_state, self.restored_state)
