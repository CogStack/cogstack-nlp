import os
import shutil
import unittest
from typing import cast

from transformers import AutoTokenizer

from medcat.components.addons.meta_cat.meta_cat import MetaCAT
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.components.addons.meta_cat.mctokenizers.bert_tokenizer import (
    TokenizerWrapperBERT)
from medcat.storage.serialisers import deserialise, serialise

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


if __name__ == '__main__':
    unittest.main()
