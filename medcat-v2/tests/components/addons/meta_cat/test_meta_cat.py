from typing import runtime_checkable, Type, Any

from medcat2.components.addons.meta_cat import meta_cat
from medcat2.components.addons.addons import AddonComponent
from medcat2.storage.serialisables import Serialisable, ManualSerialisable
from medcat2.storage.serialisers import serialise, AvailableSerialisers
from medcat2.config.config_meta_cat import ConfigMetaCAT
from medcat2.config.config import Config

import unittest
import tempfile

from medcat2.cat import CAT
from medcat2.tokenizing.spacy_impl.tokenizers import SpacyTokenizer

from .... import EXAMPLE_MODEL_PACK_ZIP


class FakeEntity:

    @classmethod
    def register_addon_path(self, path: str, def_val: Any, force: bool = True):
        pass


class FakeTokenizer:

    @classmethod
    def get_entity_class(cls) -> Type:
        return FakeEntity

    @classmethod
    def get_doc_class(cls) -> Type:
        return FakeEntity


class MetaCATBaseTests(unittest.TestCase):
    SER_TYPE = AvailableSerialisers.dill
    VOCAB_SIZE = 10
    PAD_IDX = 5
    TOKENIZER_CLS = FakeTokenizer

    @classmethod
    def setUpClass(cls):
        cls.cnf = ConfigMetaCAT()
        cls.cnf.comp_name = meta_cat.MetaCATAddon.addon_type
        cls.cnf.general.vocab_size = cls.VOCAB_SIZE
        cls.cnf.model.padding_idx = cls.PAD_IDX
        cls.cnf.general.tokenizer_name = 'bert-tokenizer'
        cls.cnf.model.model_variant = 'prajjwal1/bert-tiny'
        cls.cnf.general.category_name = 'FAKE_category'
        cls.cnf.general.category_value2id = {
            'Future': 0, 'Past': 2, 'Recent': 1}
        cls.tokenizer = cls.TOKENIZER_CLS()
        cls.meta_cat = meta_cat.MetaCATAddon.create_new(cls.cnf, cls.tokenizer)


class MetaCATTests(MetaCATBaseTests):

    def test_is_addon(self):
        self.assertIsInstance(self.meta_cat, runtime_checkable(AddonComponent))

    def test_is_manually_serialisable(self):
        self.assertIsInstance(self.meta_cat, ManualSerialisable)

    def test_is_serialisable_meta_cat(self):
        self.assertIsInstance(self.meta_cat.mc,
                              runtime_checkable(Serialisable))


class MetaCATWithCATTests(MetaCATBaseTests):
    _DEF_CNF = Config()
    TOKENIZER_CLS = lambda: SpacyTokenizer(  # noqa
        MetaCATWithCATTests._DEF_CNF.general.nlp.modelname,
        MetaCATWithCATTests._DEF_CNF.general.nlp.disabled_components,
        MetaCATWithCATTests._DEF_CNF.general.diacritics,
        MetaCATWithCATTests._DEF_CNF.preprocessing.max_document_length)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat = CAT.load_model_pack(EXAMPLE_MODEL_PACK_ZIP)
        cls.cat.add_addon(cls.meta_cat)

    def assert_has_meta_cat(self, cat: CAT, same: bool = True):
        self.assertEqual(len(cat._pipeline._addons), 1)
        addon = self.cat._pipeline._addons[0]
        if same:
            self.assertIs(addon, self.meta_cat)
        else:
            self.assertEqual(addon, self.meta_cat)

    def test_has_added_meta_cat(self):
        self.assert_has_meta_cat(self.cat, True)

    def test_can_save(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            serialise(self.SER_TYPE, self.cat, temp_dir)

    def test_can_save_and_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_name = self.cat.save_model_pack(
                temp_dir, serialiser_type=self.SER_TYPE)
            cat2 = CAT.load_model_pack(file_name)
        self.assert_has_meta_cat(cat2, False)

    def test_turns_up_in_output(self):
        ents = self.cat.get_entities(
            "This is a fit text for rich and chronic disease like fittest.")
        self.assertGreater(len(ents['entities']), 0)
        for eid, ent in ents['entities'].items():
            with self.subTest(str(eid)):
                self.assertIn(meta_cat.MetaCATAddon.output_key, ent)
                val = ent[meta_cat.MetaCATAddon.output_key]
                self.assertIn(self.meta_cat.name, val)
