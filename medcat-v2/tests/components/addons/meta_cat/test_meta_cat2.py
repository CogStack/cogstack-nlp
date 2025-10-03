import os
import shutil
import unittest
from typing import cast
import tempfile

from transformers import AutoTokenizer

from medcat.components.addons.meta_cat import MetaCAT, MetaCATAddon
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.components.addons.meta_cat.mctokenizers.bert_tokenizer import (
    TokenizerWrapperBERT)
from medcat.storage.serialisers import deserialise, serialise
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.vocab import Vocab

import spacy
from spacy.tokens import Span

from .test_meta_cat import FakeTokenizer

RESOURCES_PATH = os.path.abspath(
    os.path.join(
        os.path.realpath(__file__), "..", "..", "..", "..", "resources"))


class MetaCATTests(unittest.TestCase):
    BASE_TOKENIZER = FakeTokenizer()
    SERIALISER_TYPE = 'dill'
    EXPORT_PATH = os.path.join(RESOURCES_PATH,
                               'mct_export_for_meta_cat_test.json')

    @classmethod
    def setUpClass(cls) -> None:
        tokenizer = TokenizerWrapperBERT(
            AutoTokenizer.from_pretrained('prajjwal1/bert-tiny'))
        config = ConfigMetaCAT()
        config.general.category_name = 'Status'
        config.train.nepochs = 2
        config.model.input_size = 100
        cls.meta_cat: MetaCAT = MetaCAT(
            tokenizer=tokenizer, embeddings=None, config=config)

        cls.tmp_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "tmp")

    def setUp(self):
        # make sure the folder exists
        os.makedirs(self.tmp_dir, exist_ok=True)

    # @classmethod
    def tearDown(self) -> None:
        # but make sure it's empty?
        shutil.rmtree(self.tmp_dir)

    def test_train(self):
        json_path = self.EXPORT_PATH
        results = self.meta_cat.train_from_json(
            json_path, save_dir_path=self.tmp_dir, overwrite=True)
        if self.meta_cat.config.model.phase_number != 1:
            self.assertEqual(
                results['report']['weighted avg']['f1-score'], 1.0)

    def test_save_load(self):
        json_path = self.EXPORT_PATH
        self.meta_cat.train_from_json(
            json_path, save_dir_path=self.tmp_dir, overwrite=True)
        serialise(self.SERIALISER_TYPE, self.meta_cat, self.tmp_dir,
                  overwrite=True)
        n_meta_cat = cast(MetaCAT, deserialise(self.tmp_dir))
        self.assertIsInstance(n_meta_cat, MetaCAT)
        f1 = self.meta_cat.eval(json_path)['f1']
        n_f1 = n_meta_cat.eval(json_path)['f1']

        self.assertEqual(f1, n_f1)

    def _prepare_doc_w_spangroup(self, spangroup_name: str):
        """
        Create spans under an arbitrary spangroup key
        """
        Span.set_extension('id', default=0, force=True)
        Span.set_extension('meta_anns', default=None, force=True)
        nlp = spacy.blank("en")
        doc = nlp("Pt has diabetes and copd.")
        span_0 = doc.char_span(7, 15, label="diabetes")
        assert span_0.text == 'diabetes'

        span_1 = doc.char_span(20, 24, label="copd")
        assert span_1.text == 'copd'
        doc.spans[spangroup_name] = [span_0, span_1]
        return doc


class MetaCATBertTest(MetaCATTests):
    @classmethod
    def setUpClass(cls) -> None:
        tokenizer = TokenizerWrapperBERT(
            AutoTokenizer.from_pretrained('prajjwal1/bert-tiny'))
        config = ConfigMetaCAT()
        config.general.category_name = 'Status'
        config.train.nepochs = 2
        config.model.input_size = 100
        config.train.batch_size = 64
        config.model.model_name = 'bert'

        cls.meta_cat: MetaCAT = MetaCAT(
            tokenizer=tokenizer, embeddings=None, config=config)
        cls.tmp_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "tmp")
        os.makedirs(cls.tmp_dir, exist_ok=True)

    def test_two_phase(self):
        self.meta_cat.config.model.phase_number = 1
        self.test_train()
        self.meta_cat.config.model.phase_number = 2
        self.test_train()

        self.meta_cat.config.model.phase_number = 0


class MetaCATInCATTests(unittest.TestCase):
    META_CAT_JSON_PATH = os.path.join(
        RESOURCES_PATH, "mct_export_for_meta_cat_full_text.json")

    @classmethod
    def _get_meta_cat(cls, meta_cat_dir: str):
        config = ConfigMetaCAT()
        config.general.category_name = "Status"
        config.general.category_value2id = {'Other': 0, 'Confirmed': 1}
        config.train.auto_save_model = False
        config.model.model_name = 'bert'
        config.model.model_freeze_layers = False
        config.model.num_layers = 10
        config.train.lr = 0.001
        config.train.nepochs = 20
        config.train.class_weights = [0.75, 0.3]
        config.train.metric['base'] = 'macro avg'

        meta_cat = MetaCAT(tokenizer=TokenizerWrapperBERT(
            AutoTokenizer.from_pretrained("bert-base-uncased")),
                           embeddings=None,
                           config=config)
        os.makedirs(meta_cat_dir, exist_ok=True)
        json_path = cls.META_CAT_JSON_PATH
        meta_cat.train_from_json(json_path, save_dir_path=meta_cat_dir)
        return meta_cat

    @classmethod
    def setUpClass(cls) -> None:
        cls.cdb = CDB.load(os.path.join(RESOURCES_PATH, "cdb_meta.zip"))
        cls.vocab = Vocab.load(os.path.join(RESOURCES_PATH, "vocab_meta.zip"))
        cls.vocab.init_cumsums()
        cls._temp_logs_folder = tempfile.TemporaryDirectory()
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.cdb.config.general.nlp.provider = "spacy"
        cls.cdb.config.general.nlp.modelname = "en_core_web_md"
        cls.cdb.config.components.ner.min_name_len = 2
        cls.cdb.config.components.ner.upper_case_limit_len = 3
        cls.cdb.config.general.spell_check = True
        cls.cdb.config.components.linking.train_count_threshold = 10
        cls.cdb.config.components.linking.similarity_threshold = 0.3
        cls.cdb.config.components.linking.train = True
        cls.cdb.config.components.linking.disamb_length_limit = 5
        cls.cdb.config.general.full_unlink = True
        cls.cdb.config.general.usage_monitor.enabled = True
        cls.cdb.config.general.usage_monitor.log_folder = (
            cls._temp_logs_folder.name)
        cls.meta_cat_dir = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "tmp")
        cls.meta_cat = cls._get_meta_cat(cls.meta_cat_dir)
        cls.cat = CAT(cdb=cls.cdb, config=cls.cdb.config, vocab=cls.vocab)
        addon = MetaCATAddon(
            cls.meta_cat.config, cls.cat.pipe.tokenizer, cls.meta_cat)
        cls.cat.add_addon(addon)

    @classmethod
    def tearDownClass(cls) -> None:
        if os.path.exists(cls.meta_cat_dir):
            shutil.rmtree(cls.meta_cat_dir)
        cls._temp_logs_folder.cleanup()
        cls.temp_dir.cleanup()

    def test_meta_cat_through_cat(self):
        text = ("This information is just to add text. The patient "
                "denied history of heartburn and/or gastroesophageal "
                "reflux disorder. He recently had a stroke in the last week.")
        entities = self.cat.get_entities(text)
        meta_status_values = []
        for en in entities['entities']:
            meta_status_values.append(entities['entities'][en][
                'meta_anns']['Status']['value'])

        self.assertEqual(meta_status_values, ['Other', 'Other', 'Confirmed'])


if __name__ == '__main__':
    unittest.main()
