import os

from medcat2.utils.legacy import conversion_all
from medcat2.cat import CAT

import shutil

import unittest
import unittest.mock

from .test_convert_vocab import TESTS_PATH


class ConversionFromZIPTests(unittest.TestCase):
    MODEL_FOLDER = os.path.join(TESTS_PATH, "resources",
                                "mct_v1_model_pack.zip")

    @classmethod
    def setUpClass(cls):
        cls._model_folder_no_zip = cls.MODEL_FOLDER.rsplit(".zip", 1)[0]
        cls._folder_existed = os.path.exists(cls._model_folder_no_zip)
        # make sure the subnames are not fixed for normal models
        with unittest.mock.patch("medcat2.utils.legacy.helpers._fix_subnames"
                                 ) as mock:
            cls.converter = conversion_all.Converter(cls.MODEL_FOLDER, None)
        mock.assert_not_called()
        cls.cat = cls.converter.convert()

    @classmethod
    def tearDownClass(cls):
        if cls.MODEL_FOLDER.endswith(".zip"):
            folder = cls._model_folder_no_zip
            if os.path.exists(folder) and not cls._folder_existed:
                shutil.rmtree(folder)

    def test_creates_cat(self):
        self.assertIsInstance(self.cat, CAT)


class ConversionFromFolderTests(ConversionFromZIPTests):
    MODEL_FOLDER = os.path.join(TESTS_PATH, "resources")
    VOCAB_NAME = 'mct_v1_vocab.dat'
    CDB_NAME = 'mct_v1_cdb.dat'
    CNF_NAME = 'mct_v1_cnf.json'

    @classmethod
    def _fix_cnf(cls, ml: int = 1_000_000):
        cls.cat.config.preprocessing.max_document_length = ml
        # NOTE: this is implementation-specific!
        if cls.cat.config.general.nlp.provider == 'spacy':
            cls.cat._pipeline._tokenizer._nlp.max_length = ml
        if cls.cat.config.components.linking.train:
            print("TRAINING WAS ENABLED ! DISABLING")
            cls.cat.config.components.linking.train = False

    @classmethod
    def setUpClass(cls):
        cls._def_vocab_name = conversion_all.Converter.vocab_name
        cls._def_cdb_name = conversion_all.Converter.cdb_name
        cls._def_cnf_name = conversion_all.Converter.config_name
        conversion_all.Converter.vocab_name = cls.VOCAB_NAME
        conversion_all.Converter.cdb_name = cls.CDB_NAME
        conversion_all.Converter.config_name = cls.CNF_NAME
        super().setUpClass()
        cls._fix_cnf()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        conversion_all.Converter.vocab_name = cls._def_vocab_name
        conversion_all.Converter.cdb_name = cls._def_cdb_name
        conversion_all.Converter.config_name = cls._def_cnf_name


class ConvertedFunctionalityTests(ConversionFromFolderTests):
    TEXT = ("Man was diagnosed with severe kidney failure and acute diabetes "
            "and presented with a light fever")
    EXPECTED_ENTS = [
        {'cui': 'C01', 'detected_name': 'kidney~failure',
            'start': 30, 'end': 44},
        {'cui': 'C02', 'detected_name': 'diabetes',
            'start': 55, 'end': 63},
        {'cui': 'C03', 'detected_name': 'fever',
            'start': 91, 'end': 96},
    ]

    @classmethod
    def assert_has_ent(cls, ent: dict) -> None:
        per_exp_bools = []
        for exp_ent in cls.EXPECTED_ENTS:
            peb = [(k, v, ent.get(k, None)) for k, v in exp_ent.items()]
            if all(p[1] == p[2] for p in peb):
                return
            per_exp_bools.append(peb)
        raise AssertionError(f"Entity {ent} not found in expected: "
                             f"{cls.EXPECTED_ENTS}. Per expected, "
                             f"this is what we got: {per_exp_bools}")

    def test_can_recognise_entities(self):
        ents = self.cat.get_entities(self.TEXT)['entities']
        self.assertEqual(len(ents), len(self.EXPECTED_ENTS))
        for ent in ents.values():
            self.assert_has_ent(ent)
