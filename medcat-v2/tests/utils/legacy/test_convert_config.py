import os

from medcat.utils.legacy import convert_config

from medcat.config import Config

import unittest


TESTS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                          "..", ".."))


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
