import os
import pandas as pd
import json
from typing import Optional
from collections import Counter

from medcat2 import cat
from medcat2.vocab import Vocab
from medcat2.config import Config
from medcat2.model_creation.cdb_maker import CDBMaker
from medcat2.cdb import CDB
from medcat2.tokenizing.tokens import UnregisteredDataPathException

import unittest
import unittest.mock

from . import EXAMPLE_MODEL_PACK_ZIP
from .utils.legacy.test_conversion_all import ConvertedFunctionalityTests


orig_init = cat.CAT.__init__


class ModelLoadTests(unittest.TestCase):

    def assert_has_model_name(self, func):
        expected_model_packl_name = EXAMPLE_MODEL_PACK_ZIP.replace(".zip", "")

        def wrapper(*args, **kwargs):
            if 'model_load_path' in kwargs:
                self.assertEqual(kwargs['model_load_path'],
                                 expected_model_packl_name)
            else:
                self.assertEqual(args[-1], expected_model_packl_name)
            return func(*args, **kwargs)
        return wrapper

    def setUp(self):
        cat.CAT.__init__ = self.assert_has_model_name(cat.CAT.__init__)

    def tearDown(self):
        cat.CAT.__init__ = orig_init

    def test_loaded_model_knows_model_path(self):
        # NOTE: the assertion is checked due to wrapper on CAT.__init__
        inst = cat.CAT.load_model_pack(EXAMPLE_MODEL_PACK_ZIP)
        self.assertIsInstance(inst, cat.CAT)


class TrainedModelTests(unittest.TestCase):
    TRAINED_MODEL_PATH = EXAMPLE_MODEL_PACK_ZIP

    @classmethod
    def setUpClass(cls):
        cls.model = cat.CAT.load_model_pack(cls.TRAINED_MODEL_PATH)
        if cls.model.config.components.linking.train:
            print("TRAINING WAS ENABLE! NEED TO DISABLE")
            cls.model.config.components.linking.train = False


class InferenceFromLoadedTests(TrainedModelTests):

    def test_can_load_model(self):
        self.assertIsInstance(self.model, cat.CAT)

    def test_has_training(self):
        self.assertTrue(self.model.cdb.cui2info)
        self.assertTrue(self.model.cdb.name2info)

    def test_inference_works(self):
        ents = self.model.get_entities(
            ConvertedFunctionalityTests.TEXT)['entities']
        for nr, ent in enumerate(ents.values()):
            with self.subTest(f"{nr}"):
                ConvertedFunctionalityTests.assert_has_ent(ent)


class CATIncludingTests(unittest.TestCase):
    TOKENIZING_PROVIDER = 'regex'
    EXPECT_TRAIN = {}

    # paths
    VOCAB_DATA_PATH = os.path.join(
        os.path.dirname(__file__), 'resources', 'vocab_data.txt'
    )
    CDB_PREPROCESSED_PATH = os.path.join(
        os.path.dirname(__file__), 'resources', 'preprocessed4cdb.txt'
    )

    @classmethod
    def setUpClass(cls):

        # vocab

        vocab = Vocab()
        vocab.add_words(cls.VOCAB_DATA_PATH)

        # CDB
        config = Config()

        # tokenizer
        config.general.nlp.provider = cls.TOKENIZING_PROVIDER

        maker = CDBMaker(config)

        cls.cdb: CDB = maker.prepare_csvs([cls.CDB_PREPROCESSED_PATH])

        # CAT
        cls.cat = cat.CAT(cls.cdb, vocab)
        cls.cat.config.components.linking.train = False


class CATCreationTests(CATIncludingTests):
    # should be persistent as long as we don't change the underlying model
    EXPECTED_HASH = "558019fd37ed2167"

    @classmethod
    def get_cui2ct(cls, cat: Optional[cat.CAT] = None):
        if cat is None:
            cat = cls.cat
        return {
            cui: info['count_train'] for cui, info in cat.cdb.cui2info.items()
            if info['count_train']}

    def test_has_expected_training(self):
        self.assertEqual(self.get_cui2ct(), self.EXPECT_TRAIN)

    def test_versioning_updates_config_hash(self):
        prev_hash = self.cat.config.meta.hash
        self.cat._versioning()
        new_hash = self.cat.config.meta.hash
        self.assertNotEqual(prev_hash, new_hash)
        self.assertEqual(new_hash, self.EXPECTED_HASH)


class CATUnsupTrainingTests(CATCreationTests):
    SELF_SUPERVISED_DATA_PATH = os.path.join(
        os.path.dirname(__file__), 'resources', 'selfsupervised_data.txt'
    )
    EXPECT_TRAIN = {'C01': 2, 'C02': 2, 'C03': 2, 'C04': 1, 'C05': 1}
    # NOTE: should remain consistent unless we change the model or data
    EXPECTED_HASH = "e9989cc2dde739ff"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        data = pd.read_csv(cls.SELF_SUPERVISED_DATA_PATH)
        cls.cat.trainer.train_unsupervised(data.text.values)


class CATSupTrainingTests(CATUnsupTrainingTests):
    SUPERVISED_DATA_PATH = os.path.join(
        os.path.dirname(__file__), 'resources', 'supervised_mct_export.json'
    )
    # NOTE: should remain consistent unless we change the model or data
    EXPECTED_HASH = "7bfe01e8e36eb07d"

    @classmethod
    def _get_cui_counts(cls) -> dict[str, int]:
        counter = Counter()
        data = cls._get_data()
        for proj in data['projects']:
            for doc in proj['documents']:
                for ann in doc['annotations']:
                    counter[ann['cui']] += 1
        return counter

    @classmethod
    def _get_data(cls) -> dict:
        with open(cls.SUPERVISED_DATA_PATH) as f:
            return json.load(f)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # copy from parent
        cls.EXPECT_TRAIN = CATUnsupTrainingTests.EXPECT_TRAIN.copy()
        cui_counts_in_data = cls._get_cui_counts()
        # add extra CUIs in supervised training example
        for cui, extra_cnt in cui_counts_in_data.items():
            cls.EXPECT_TRAIN[cui] += extra_cnt
        cls._perform_training()

    @classmethod
    def _perform_training(cls):
        data = cls._get_data()
        cls.cat.trainer.train_supervised_raw(data)


class CATWithDictNERSupTrainingTests(CATSupTrainingTests):
    from medcat2.components.types import CoreComponentType
    from medcat2.components.ner.dict_based_ner import NER as DNER
    from medcat2.components.ner.vocab_based_ner import NER as VNER

    @classmethod
    def _dummy_pt(cls):
        pass

    @classmethod
    def setUpClass(cls):
        # NOTE: need to do training AFTER changes
        #       so stopping it from happening here
        orig_training = cls._perform_training
        cls._perform_training = cls._dummy_pt
        super().setUpClass()
        cls._perform_training = orig_training
        cls.cdb.config.components.ner.comp_name = 'dict'
        cls.cat._recrate_pipe()
        # cls.cat.cdb.reset_training()
        cls._perform_training()

    def test_has_dict_based_ner(self):
        comp = self.cat._pipeline.get_component(self.CoreComponentType.ner)
        self.assertNotIsInstance(comp, self.VNER)
        self.assertIsInstance(comp, self.DNER)

    def test_can_get_entities(self,
                              expected_cuis: list[str] = ['C01', 'C05']):
        _ents = self.cat.get_entities(
            "The fittest most fit of chronic kidney failure", only_cui=True)
        ents = _ents['entities']
        self.assertEqual(len(ents), len(expected_cuis))
        self.assertEqual(set(ents.values()), set(expected_cuis))


class CATWithDocAddonTests(CATIncludingTests):
    EXAMPLE_TEXT = "Example text to tokenize"
    ADDON_PATH = 'SMTH'
    EXAMPLE_VALUE = 'something else'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        doc = cls.cat(cls.EXAMPLE_TEXT)
        cls.doc_cls = doc.__class__
        cls.doc_cls.register_addon_path(cls.ADDON_PATH)

    def setUp(self):
        self.doc = self.cat(self.EXAMPLE_TEXT)

    def test_can_set_value(self):
        self.doc.set_addon_data(self.ADDON_PATH, self.EXAMPLE_VALUE)

    def test_cannot_set_incorrect_value(self):
        with self.assertRaises(UnregisteredDataPathException):
            self.doc.set_addon_data(self.ADDON_PATH * 2 + "#",
                                    self.EXAMPLE_TEXT)

    def test_cannot_get_incorrect_value(self):
        with self.assertRaises(UnregisteredDataPathException):
            self.doc.get_addon_data(self.ADDON_PATH * 2 + "#")

    def test_can_load_value(self):
        self.doc.set_addon_data(self.ADDON_PATH, self.EXAMPLE_VALUE)
        got = self.doc.get_addon_data(self.ADDON_PATH)
        self.assertEqual(self.EXAMPLE_VALUE, got)


class CATWithDocAddonSpacyTests(CATWithDocAddonTests):
    TOKENIZING_PROVIDER = 'spacy'


class CATWithEntityAddonTests(CATIncludingTests):
    EXAMPLE_TEXT = "Example text to tokenize"
    EXAMPLE_ENT_START = 0
    EXAMPLE_ENT_END = 2
    ADDON_PATH = 'SMTH'
    EXAMPLE_VALUE = 'something else'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        doc = cls.cat(cls.EXAMPLE_TEXT)
        doc.__getitem__
        entity = doc[0:-1]
        cls.entity_cls = entity.__class__
        cls.entity_cls.register_addon_path(cls.ADDON_PATH)

    def setUp(self):
        self.doc = self.cat(self.EXAMPLE_TEXT)
        self.entity = self.doc[self.EXAMPLE_ENT_START: self.EXAMPLE_ENT_END]

    def test_can_add_data(self):
        self.entity.set_addon_data(self.ADDON_PATH, self.EXAMPLE_VALUE)

    def test_cannot_add_data_to_wrong_path(self):
        with self.assertRaises(UnregisteredDataPathException):
            self.entity.set_addon_data(self.ADDON_PATH * 2 + "£",
                                       self.EXAMPLE_VALUE)

    def test_cannot_get_data_to_wrong_path(self):
        with self.assertRaises(UnregisteredDataPathException):
            self.entity.get_addon_data(self.ADDON_PATH * 2 + "£")

    def test_can_get_data(self):
        self.entity.set_addon_data(self.ADDON_PATH, self.EXAMPLE_VALUE)
        got = self.entity.get_addon_data(self.ADDON_PATH)
        self.assertEqual(self.EXAMPLE_VALUE, got)

    def test_data_is_persistent(self):
        self.entity.set_addon_data(self.ADDON_PATH, self.EXAMPLE_VALUE)
        ent = self.doc[self.EXAMPLE_ENT_START: self.EXAMPLE_ENT_END]
        # new instance
        self.assertFalse(ent is self.entity)
        got = ent.get_addon_data(self.ADDON_PATH)
        self.assertEqual(self.EXAMPLE_VALUE, got)


class CATWithEntityAddonSpacyTests(CATWithEntityAddonTests):
    TOKENIZING_PROVIDER = 'spacy'
