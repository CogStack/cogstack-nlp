from typing import Type, Any
import os

from medcat.utils.legacy import convert_config

from medcat.config import Config
from medcat.config.config import SerialisableBaseModel
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.config.config_transformers_ner import ConfigTransformersNER

import unittest


from ... import RESOURCES_PATH
TESTS_PATH = os.path.dirname(RESOURCES_PATH)


class ValAndModelGetterTests(unittest.TestCase):
    EXP_MODEL = 'SPACY MODEL'
    EXP_PATH = 'general.nlp.spacy_model'
    MODEL = Config()
    DICT = {
        'general': {
            'nlp': {
                'spacy_model': EXP_MODEL,
            }
        }
    }

    def test_can_get_correct_val_and_model(self):
        val, model = convert_config.get_val_and_parent_model(
            self.DICT, self.MODEL, self.EXP_PATH)
        self.assertEqual(val, self.EXP_MODEL)
        self.assertEqual(model, self.MODEL.general.nlp)

    def test_can_get_val_only(self):
        val, _ = convert_config.get_val_and_parent_model(
            self.DICT, None, self.EXP_PATH)
        self.assertEqual(val, self.EXP_MODEL)

    def test_no_model_when_val_only(self):
        _, model = convert_config.get_val_and_parent_model(
            self.DICT, None, self.EXP_PATH)
        self.assertIsNone(model)

    def test_can_get_model_only(self):
        _, model = convert_config.get_val_and_parent_model(
            None, self.MODEL, self.EXP_PATH)
        self.assertEqual(model, self.MODEL.general.nlp)

    def test_no_val_when_model_only(self):
        val, _ = convert_config.get_val_and_parent_model(
            None, self.MODEL, self.EXP_PATH)
        self.assertIsNone(val)


class ConfigConverstionTests(unittest.TestCase):
    FILE_PATH = os.path.join(TESTS_PATH, "resources", "mct_v1_cnf.json")
    FAKE_DESCRIPTION = "FAKE MODEL"
    EXP_TEXT_IN_OUTPUT = True
    EXP_MAX_DOC_LEN = 5
    EXP_WORDS_TO_SKIP = {'nos'}

    @classmethod
    def setUpClass(cls):
        cls.cnf = convert_config.get_config_from_old(cls.FILE_PATH)

    def test_can_convert(self):
        self.assertIsInstance(self.cnf, Config)

    def test_migrates_correct_description(self):
        self.assertEqual(self.cnf.meta.description, self.FAKE_DESCRIPTION)

    def test_migrates_simple(self):
        self.assertEqual(self.cnf.preprocessing.max_document_length,
                         self.EXP_MAX_DOC_LEN)

    def test_migrates_partial(self):
        self.assertEqual(self.cnf.annotation_output.include_text_in_output,
                         self.EXP_TEXT_IN_OUTPUT)

    def test_preprocesses_sets(self):
        self.assertEqual(self.cnf.preprocessing.words_to_skip,
                         self.EXP_WORDS_TO_SKIP)


class PerClsConfigConversionTests(unittest.TestCase):
    # paths, classes, expected path, expected value
    # NOTE: These are hard-coded values I know I changed in the confgis
    #       before saving
    PATHS_AND_CLASSES: list[str, Type[SerialisableBaseModel], str, Any] = [
        (os.path.join(RESOURCES_PATH,
                      "mct_v1_cnf.json"), Config,
         'meta.description', "FAKE MODEL"),
        (os.path.join(RESOURCES_PATH,
         "mct_v1_meta_cat_cnf.json"), ConfigMetaCAT,
         "general.category_name", 'TEST CATEGORY'),
        (os.path.join(RESOURCES_PATH,
         "mct_v1_rel_cat_cnf.json"), ConfigRelCAT,
         "general.model_name", 'bert-unknown'),
        (os.path.join(RESOURCES_PATH,
         "mct_v1_deid_cnf.json"), ConfigTransformersNER,
         "general.name", 'NOT-DEID'),
    ]

    @classmethod
    def setUpClass(cls):
        return super().setUpClass()

    def _get_attr_nested(self, obj: SerialisableBaseModel, path: str) -> Any:
        """Get an attribute from a nested object using a dot-separated path."""
        parts = path.split('.')
        for part in parts:
            obj = getattr(obj, part)
        return obj

    def assert_can_convert(
            self, path, cls: Type[SerialisableBaseModel],
            exp_path: str, exp_value: Any):
        cnf = convert_config.get_config_from_old_per_cls(path, cls)
        self.assertIsInstance(cnf, cls, f"Failed for {cls.__name__}")
        self.assertEqual(self._get_attr_nested(cnf, exp_path), exp_value,
                         f"Failed for {cls.__name__} at {exp_path}")

    def test_can_convert(self):
        for path, cls, exp_path, exp_value in self.PATHS_AND_CLASSES:
            with self.subTest(f"Testing {cls.__name__} at {path}"):
                self.assert_can_convert(path, cls, exp_path, exp_value)
