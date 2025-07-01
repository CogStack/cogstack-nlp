import os
import unittest.mock
import pandas as pd
import json
from typing import Optional
from collections import Counter

from medcat import cat
from medcat.data.model_card import ModelCard
from medcat.vocab import Vocab
from medcat.config import Config
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.model_creation.cdb_maker import CDBMaker
from medcat.cdb import CDB
from medcat.tokenizing.tokens import UnregisteredDataPathException
from medcat.tokenizing.tokenizers import TOKENIZER_PREFIX
from medcat.utils.cdb_state import captured_state_cdb
from medcat.components.addons.meta_cat import MetaCATAddon
from medcat.utils.defaults import AVOID_LEGACY_CONVERSION_ENVIRON
from medcat.utils.defaults import LegacyConversionDisabledError

import unittest
import tempfile

from . import EXAMPLE_MODEL_PACK_ZIP
from . import V1_MODEL_PACK_PATH, UNPACKED_V1_MODEL_PACK_PATH
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

    def test_can_load_CDB_from_model_pack(self):
        cdb = cat.CAT.load_cdb(EXAMPLE_MODEL_PACK_ZIP)
        self.assertIsInstance(cdb, CDB)


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

    def test_entities_in_correct_order(self):
        # NOTE: the issue wouldn't show up with smaller amount of text
        doc = self.model(ConvertedFunctionalityTests.TEXT * 3)
        cur_start = 0
        for ent in doc.linked_ents:
            with self.subTest(f"Ent: {ent}"):
                self.assertGreaterEqual(ent.base.start_char_index, cur_start)
                cur_start = ent.base.start_char_index


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

        # usage monitoring
        cls._temp_logs_folder = tempfile.TemporaryDirectory()
        config.general.usage_monitor.enabled = True
        config.general.usage_monitor.log_folder = cls._temp_logs_folder.name

        # CAT
        cls.cat = cat.CAT(cls.cdb, vocab)
        cls.cat.config.components.linking.train = False

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._temp_logs_folder.cleanup()

    def tearDown(self):
        # remove existing contents / empty file log file
        log_file_path = self.cat.usage_monitor.log_file
        if os.path.exists(log_file_path):
            os.remove(log_file_path)


class CATCreationTests(CATIncludingTests):
    # should be persistent as long as we don't change the underlying model
    EXPECTED_HASH = "558019fd37ed2167"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prev_hash = cls.cat.config.meta.hash

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
        self.assert_hashes_to(self.EXPECTED_HASH)

    def assert_hashes_to(self, exp_hash: str) -> None:
        self.cat._versioning(None)
        new_hash = self.cat.config.meta.hash
        self.assertNotEqual(self.prev_hash, new_hash)
        self.assertEqual(new_hash, exp_hash)
        self.assertEqual(self.cat.config.meta.history[-1], new_hash)

    def test_versioning_does_not_overpopulate_history(self):
        # run multiple times
        self.cat._versioning(None)
        self.cat._versioning(None)
        # and expect it not to append multiple times in the history
        # if there were multiple instances, the set would remove duplicates
        sorted_set = sorted(set(self.cat.config.meta.history))
        sorted_list = sorted(self.cat.config.meta.history)
        self.assertEqual(sorted_set, sorted_list)

    def test_can_get_model_card_str(self):
        model_card = self.cat.get_model_card(as_dict=False)
        self.assertIsInstance(model_card, str)

    def test_can_get_model_card_dict(self):
        model_card = self.cat.get_model_card(as_dict=True)
        self.assertIsInstance(model_card, dict)

    def test_model_card_has_required_keys(self):
        model_card = self.cat.get_model_card(as_dict=True)
        for ann in ModelCard.__annotations__:
            with self.subTest(f"Ann: {ann}"):
                self.assertIn(ann, model_card)

    def test_model_card_has_no_extra_keys(self):
        model_card = self.cat.get_model_card(as_dict=True)
        for key in model_card:
            with self.subTest(f"Key: {key}"):
                self.assertIn(key, ModelCard.__annotations__)


class CatWithMetaCATTests(CATCreationTests):
    EXPECTED_HASH = "8c3de3f171a87132"
    EXPECT_SAME_INSTANCES = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        meta_cat_cnf = ConfigMetaCAT()
        # NOTE: need to set for consistent hashing
        meta_cat_cnf.train.last_train_on = -1.0
        meta_cat_cnf.general.category_name = 'Status'
        meta_cat_cnf.general.tokenizer_name = 'bert-tokenizer'
        meta_cat_cnf.model.model_name = 'bert'
        meta_cat_cnf.model.model_variant = 'prajjwal1/bert-tiny'
        cls.addon = MetaCATAddon.create_new(
            meta_cat_cnf, cls.cat._pipeline.tokenizer)
        cls.cat.add_addon(cls.addon)
        cls.init_addons = list(cls.cat._pipeline._addons)

    def test_can_recreate_pipe(self):
        self.cat._recreate_pipe()
        addons_after = list(self.cat._pipeline._addons)
        self.assertGreater(len(self.init_addons), 0)
        self.assertEqual(len(self.init_addons), len(addons_after))
        if self.EXPECT_SAME_INSTANCES:
            self.assertEqual(self.init_addons, addons_after)
        else:
            # otherwise they should differ
            self.assertNotEqual(self.init_addons, addons_after)

    def test_get_entities_gets_monitored(self,
                                         text="Some text"):
        repeats = self.cat.config.general.usage_monitor.batch_size
        # ensure something gets written to the file
        for _ in range(repeats):
            self.cat.get_entities(text)
        log_file_path = self.cat.usage_monitor.log_file
        self.assertTrue(os.path.exists(log_file_path))
        with open(log_file_path) as f:
            contents = f.readline()
        self.assertTrue(contents)

    def test_get_entities_logs_usage(
            self,
            text="The dog is sitting outside the house."):
        # clear usage monitor buffer
        self.cat.usage_monitor.log_buffer.clear()
        self.cat.get_entities(text)
        self.assertTrue(self.cat.usage_monitor.log_buffer)
        self.assertEqual(len(self.cat.usage_monitor.log_buffer), 1)
        line = self.cat.usage_monitor.log_buffer[0]
        # the 1st element is the input text length
        input_text_length = line.split(",")[1]
        self.assertEqual(str(len(text)), input_text_length)


class CatWithMetaCATSaveLoadTests(CatWithMetaCATTests):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.mpp = cls.cat.save_model_pack(cls.temp_dir.name)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.temp_dir.cleanup()

    def test_can_save_pack(self):
        self.assertTrue(os.path.exists(self.mpp))

    def test_can_load_saved(self):
        loaded = cat.CAT.load_model_pack(self.mpp)
        self.assertIsInstance(loaded, cat.CAT)
        # test that it has an addon
        addons = list(loaded._pipeline.iter_addons())
        self.assertEqual(len(addons), 1)
        addon = addons[0]
        self.assertIsInstance(addon, MetaCATAddon)
        # test that loaded model pack has the same addon config as the addon
        self.assertIs(addon.config, loaded.config.components.addons[0])

    def test_can_load_meta_cat(self):
        addons = cat.CAT.load_addons(self.mpp)
        self.assertEqual(len(addons), 1)
        _, addon = addons[0]
        self.assertIsInstance(addon, MetaCATAddon)


class CatWithChangesMetaCATTests(CatWithMetaCATTests):
    EXPECTED_HASH = "0b22401059a08380"
    EXPECT_SAME_INSTANCES = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addon.config.general.batch_size_eval = 10


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

    def test_lists_unsup_train_in_config(self):
        self.assertTrue(self.cat.config.meta.unsup_trained)


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

    def test_lists_sup_train_in_config(self):
        self.assertTrue(self.cat.config.meta.sup_trained)

    def test_clearing_training_works(self):
        with captured_state_cdb(self.cat.cdb):
            self.cat.cdb.reset_training()
            self.assertEqual(self.cat.cdb.get_cui2count_train(), {})
            self.assertEqual(self.cat.cdb.get_name2count_train(), {})
            self.assertEqual(self.cat.config.meta.unsup_trained, [])
            self.assertEqual(self.cat.config.meta.sup_trained, [])


class CATWithDictNERSupTrainingTests(CATSupTrainingTests):
    from medcat.components.types import CoreComponentType
    from medcat.components.ner.dict_based_ner import NER as DNER
    from medcat.components.ner.vocab_based_ner import NER as VNER

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
        cls.cat._recreate_pipe()
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

    def test_can_get_multiple_entities(self):
        texts = [
            "The fittest most fit of chronic kidney failure",
            "The dog is sitting outside the house."
        ]
        ents = list(self.cat.get_entities_multi_texts(texts))
        self.assertEqual(len(ents), len(texts))
        # NOTE: text IDs are integers starting from 0
        exp_ids = set(str(i) for i in range(len(texts)))
        for ent_id_str, ent in ents:
            with self.subTest(f"Entity: {ent_id_str} [{ent}]"):
                self.assertIn(ent_id_str, exp_ids)


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
        # add for MutableEntity as well
        doc[:].register_addon_path(cls.ADDON_PATH)

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

    def test_empty_doc_has_no_addon_data_paths(self):
        avail = self.doc.get_available_addon_paths()
        datas = {
            path: (data := self.doc.get_addon_data(path), bool(data),
                   self.doc.has_addon_data(path))
            for path in avail
        }
        self.assertFalse(avail, f"Available: {avail};\nDATA: {datas}")

    def test_doc_can_have_addon_data_path(self):
        # set some data
        self.doc.set_addon_data(self.ADDON_PATH, self.EXAMPLE_VALUE)
        avail = self.doc.get_available_addon_paths()
        self.assertTrue(avail)
        datas = {
            path: (data := self.doc.get_addon_data(path), bool(data),
                   self.doc.has_addon_data(path))
            for path in avail
        }
        self.assertEqual(len(avail), 1, f"Available: {avail};\nDATA: {datas}")
        self.assertEqual(avail[0], self.ADDON_PATH)

    def test_empty_ent_has_no_addon_data_paths(self):
        ent = self.doc[:]
        avail = ent.get_available_addon_paths()
        self.assertFalse(avail)
        datas = {
            path: (data := self.doc.get_addon_data(path), bool(data),
                   self.doc.has_addon_data(path))
            for path in avail
        }
        self.assertFalse(ent.has_addon_data(self.ADDON_PATH),
                         f"Available: {avail};\nDATA: {datas}")

    def test_ent_can_have_addon_data_path(self):
        ent = self.doc[:]
        # set some data
        ent.set_addon_data(self.ADDON_PATH, self.EXAMPLE_VALUE)
        avail = ent.get_available_addon_paths()
        self.assertTrue(avail)
        self.assertEqual(len(avail), 1)
        self.assertEqual(avail[0], self.ADDON_PATH)
        self.assertTrue(ent.has_addon_data(self.ADDON_PATH))


class MethodSpy:
    def __init__(self, obj: object, method_name: str):
        self.obj = obj
        self.is_module = obj.__class__.__name__ == 'module'
        self.method_name = method_name
        self.call_args = []
        self.call_results = []
        self._patcher = None
        self._original_method = getattr(obj, method_name)

    def __enter__(self):
        def wrapper(*args, **kwargs):
            self.call_args.append((args, kwargs))
            if self.is_module:
                result = self._original_method(*args, **kwargs)
            else:
                result = self._original_method(self.obj, *args, **kwargs)
            self.call_results.append(result)
            return result

        self._patcher = unittest.mock.patch.object(
            self.obj, self.method_name, side_effect=wrapper
        )
        self._patcher.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._patcher.stop()

    def assert_called_with(self, *args, **kwargs):
        assert (args, kwargs) in self.call_args, (
            f"No such args for, {self._original_method}")

    def assert_called_once_with(self, *args, **kwargs):
        assert len(self.call_args) == 1
        self.assert_called_with(
            *args, **kwargs)

    def assert_returned(self, ret_val):
        assert ret_val in self.call_results


class CATWithDocAddonSpacyTests(CATWithDocAddonTests):
    TOKENIZING_PROVIDER = 'spacy'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._save_folder = tempfile.TemporaryDirectory()
        cls.saved_model_path = cls.cat.save_model_pack(
            cls._save_folder.name, make_archive=False)
        # NOTE: that has changed config
        cls.saved_spacy_path = cls.cat.config.general.nlp.modelname

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._save_folder.cleanup()

    def test_saves_spacy_model(self):
        # make sure was saved in the current folder
        self.assertIn(self._save_folder.name, self.saved_spacy_path)
        self.assertIn(TOKENIZER_PREFIX, self.saved_spacy_path)
        self.assertTrue(os.path.exists(self.saved_spacy_path))
        self.assertTrue(os.path.isdir(self.saved_spacy_path))

    def test_loads_spacy_model(self):
        import medcat.tokenizing.spacy_impl.tokenizers
        import spacy
        with MethodSpy(
                medcat.tokenizing.spacy_impl.tokenizers.SpacyTokenizer,
                "load_internals_from") as mock_load_internal:
            with MethodSpy(spacy, "load") as mock_load:
                model = cat.CAT.load_model_pack(self.saved_model_path)
        self.assertIsInstance(model, cat.CAT)
        mock_load_internal.assert_called_once_with(self.saved_spacy_path)
        mock_load.assert_called_once_with(
            self.saved_spacy_path,
            disable=self.cat.config.general.nlp.disabled_components)


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


class CATLegacyLoadTests(unittest.TestCase):

    def test_can_load_legacy_model_zip(self):
        self.assertIsInstance(
            cat.CAT.load_model_pack(V1_MODEL_PACK_PATH), cat.CAT)

    def test_can_load_legacy_model_unpacked(self):
        self.assertIsInstance(
            cat.CAT.load_model_pack(UNPACKED_V1_MODEL_PACK_PATH), cat.CAT)

    def test_cannot_load_legacy_with_environ_set(self):
        with unittest.mock.patch.dict(os.environ, {
                AVOID_LEGACY_CONVERSION_ENVIRON: "true"}, clear=True):
            with self.assertRaises(LegacyConversionDisabledError):
                cat.CAT.load_model_pack(V1_MODEL_PACK_PATH)


class CATSaveTests(CATIncludingTests):
    DESCRIPTION = "Test CAT save functionality"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_folder = tempfile.TemporaryDirectory()
        cls.saved_path = cls.cat.save_model_pack(
            cls.temp_folder.name, change_description=cls.DESCRIPTION)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.temp_folder.cleanup()

    def test_can_save_model_pack(self):
        self.assertTrue(os.path.exists(self.saved_path))

    def test_model_adds_description(self):
        self.assertIn(self.DESCRIPTION, self.cat.config.meta.description)


class BatchingTests(unittest.TestCase):
    NUM_TEXTS = 100
    all_texts = [
        f"Text {num:04d} -> " + "a" * num
        for num in range(NUM_TEXTS)
    ]
    total_text_length = sum(len(text) for text in all_texts)

    @classmethod
    def setUpClass(cls):
        cnf = Config()
        cls.cat = cat.CAT(cdb=CDB(cnf), vocab=Vocab())

    # per doc batching tests

    def test_batching_gets_full(self):
        batches = list(self.cat._generate_simple_batches(
            iter(self.all_texts), batch_size=self.NUM_TEXTS,
            only_cui=False))
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), self.NUM_TEXTS)
        # NOTE: the contents has the text and the index and the only_cui bool
        #       so can't check equality directly
        # self.assertEqual(batches[0], self.all_texts)

    def test_batching_gets_in_sequence(self):
        batches = list(self.cat._generate_simple_batches(
            iter(self.all_texts), batch_size=self.NUM_TEXTS // 2,
            only_cui=False))
        self.assertEqual(len(batches), 2)
        self.assertEqual(len(batches[0]), self.NUM_TEXTS // 2)
        self.assertEqual(len(batches[1]), self.NUM_TEXTS // 2)
        # self.assertEqual(batches[0] + batches[1], self.all_texts)

    def test_batching_gets_all_1_at_a_time(self):
        batches = list(self.cat._generate_simple_batches(
            iter(self.all_texts), batch_size=1, only_cui=False))
        self.assertEqual(len(batches), self.NUM_TEXTS)
        for num, batch in enumerate(batches):
            with self.subTest(f"Batch {num}"):
                self.assertEqual(len(batch), 1)
                # self.assertEqual(batch[0], f"Text {num}")

    # per character batching tests

    def test_batching_gets_full_char(self):
        batches = list(self.cat._generate_batches_by_char_length(
            iter(self.all_texts), batch_size_chars=self.total_text_length,
            only_cui=False))
        self.assertEqual(len(batches), 1)
        # has all texts
        self.assertEqual(sum(len(batch) for batch in batches), self.NUM_TEXTS)
        # has all characters
        self.assertEqual(sum(len(text[1]) for text in batches[0]),
                         self.total_text_length)

    def test_batching_gets_all_half_at_a_time(self):
        exp_chars = int(0.7 * self.total_text_length)
        batches = list(self.cat._generate_batches_by_char_length(
            iter(self.all_texts), batch_size_chars=exp_chars,
            only_cui=False))
        # NOTE: should have 2 batches at 40% overlap
        self.assertEqual(len(batches), 2)
        # each batch should have less than expected characters
        for batch_num, batch in enumerate(batches):
            with self.subTest(f"Batch {batch_num}"):
                cur_total_chars = sum(len(text[1]) for text in batch)
                self.assertLessEqual(cur_total_chars, exp_chars)
        # has all texts
        self.assertEqual(sum(len(batch) for batch in batches), self.NUM_TEXTS)
        # has all characters
        self.assertEqual(sum(len(text[1])
                             for batch in batches for text in batch),
                         self.total_text_length)

    # overal batching (i.e joint methods)

    def test_cannot_set_both_neg(self):
        with self.assertRaises(ValueError):
            list(self.cat._generate_batches(
                iter(self.all_texts), batch_size_chars=-1,
                batch_size=-1, only_cui=False))

    def test_cannot_set_both_pos(self):
        with self.assertRaises(ValueError):
            list(self.cat._generate_batches(
                iter(self.all_texts), batch_size_chars=100,
                batch_size=10, only_cui=False))

    def test_can_do_char_based(self):
        exp_chars = int(0.3 * self.total_text_length)
        batches = list(self.cat._generate_batches(
            iter(self.all_texts), batch_size_chars=exp_chars,
            batch_size=-1, only_cui=False))
        self.assertGreater(len(batches), 0)
        batch_lens = [len(batch) for batch in batches]
        # has different number of texts in some batches -> not doc based
        self.assertGreater(max(batch_lens), min(batch_lens))

    def test_can_set_batch_size_per_doc(self):
        exp_batches = 10
        batches = list(self.cat._generate_batches(
            iter(self.all_texts), batch_size=exp_batches,
            batch_size_chars=-1, only_cui=False))
        self.assertGreater(len(batches), 0)
        batch_lens = [len(batch) for batch in batches]
        # has same number of texts in each batch -> doc based
        self.assertEqual(max(batch_lens), min(batch_lens))
        self.assertEqual(max(batch_lens), exp_batches)
