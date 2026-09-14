from medcat.config import config
from medcat.storage.serialisables import Serialisable
from medcat.storage.serialisers import serialise, deserialise

import tempfile

import unittest


class ConfigTests(unittest.TestCase):
    CHANGED_NLP = '#NON#-#EXISTENT#'
    TO_MERGE_SIMPLE = {
        "general": {
            "nlp": {
                "provider": CHANGED_NLP,
            },
        },
    }
    TO_MERGE_INCORRECT = {
        "general": 1,
    }
    TO_MERGE_INCORRECT_VAL = {
        "general": {
            "nlp": {
                "provider": -1,
            },
        },
    }
    NEW_KEY_PATH = 'general.nlp.this_key_is_new_woo'
    TO_MERGE_NEW_VAL = 123
    TO_MERGE_NEW_KEY = {
        NEW_KEY_PATH.split(".")[0]: {
            NEW_KEY_PATH.split(".")[1]: {
                NEW_KEY_PATH.split(".")[2]: TO_MERGE_NEW_VAL,
            }
        }
    }
    NEW_KEY_PATH_INCORRECT = 'cdb_maker.this_key_is_new_woo'
    TO_MERGE_NEW_KEY_INCORRECT = {
        NEW_KEY_PATH_INCORRECT.split(".")[0]: {
            NEW_KEY_PATH_INCORRECT.split(".")[1]: TO_MERGE_NEW_VAL,
        }
    }

    def setUp(self):
        self.cnf = config.Config()

    def test_is_serialisable(self):
        self.assertIsInstance(self.cnf, Serialisable)

    def test_can_merge(self):
        self.assertNotEqual(self.cnf.general.nlp.provider, self.CHANGED_NLP)
        self.cnf.merge_config(self.TO_MERGE_SIMPLE)
        self.assertEqual(self.cnf.general.nlp.provider, self.CHANGED_NLP)

    def test_fails_to_merge_incorrect_model(self):
        with self.assertRaises(config.IncorrectConfigValues):
            self.cnf.merge_config(self.TO_MERGE_INCORRECT)

    def test_fails_to_merge_incorrect_value(self):
        with self.assertRaises(config.IncorrectConfigValues):
            self.cnf.merge_config(self.TO_MERGE_INCORRECT_VAL)

    def test_can_merge_new_value_where_allowed(self):
        self.cnf.merge_config(self.TO_MERGE_NEW_KEY)
        cur = self.cnf
        for path in self.NEW_KEY_PATH.split("."):
            cur = getattr(cur, path)
        self.assertEqual(cur, self.TO_MERGE_NEW_VAL)

    def test_cannot_merge_new_value_not_allowed(self):
        with self.assertRaises(config.IncorrectConfigValues):
            self.cnf.merge_config(self.TO_MERGE_NEW_KEY_INCORRECT)


class ComponentConfigTests(unittest.TestCase):

    def setUp(self):
        self.cnf = config.ComponentConfig()

    def _make_change(self):
        self.cnf.comp_name = 'something_else'

    def test_raw_config_not_dirty(self):
        self.assertFalse(self.cnf.is_dirty)

    def test_changed_config_dirty(self):
        self._make_change()
        self.assertTrue(self.cnf.is_dirty)


class ChainedDirtiableComponentTests(ComponentConfigTests):
    class MultiLevelDirtiable(config.DirtiableBaseModel):
        part_a: config.ComponentConfig = config.ComponentConfig()
        part_b: config.ComponentConfig = config.ComponentConfig()

    def setUp(self):
        self.cnf = self.MultiLevelDirtiable()

    def _make_change(self):
        # this is a change not within the outer, but within the inner dirtiable
        self.cnf.part_a.comp_name = 'SOMETHING-else'

    def test_outer_remains_undirty_raw(self):
        self._make_change()
        self.assertFalse(self.cnf._is_dirty)


class SerialisableTests(unittest.TestCase):
    provider = 'something'

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.cnf_path = cls.temp_dir.name
        cls.cnf = config.Config()
        cls.cnf.general.nlp.provider = cls.provider
        serialise('dill', cls.cnf, cls.cnf_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_can_deserialise(self):
        cnf = deserialise(self.cnf_path)
        self.assertIsInstance(cnf, config.Config)
        self.assertEqual(cnf, self.cnf)

    def test_can_use_convenience_method(self):
        cnf = config.Config.load(self.cnf_path)
        self.assertIsInstance(cnf, config.Config)
        self.assertEqual(cnf, self.cnf)
