from typing import runtime_checkable

from medcat.tokenizing import tokenizers
from medcat.tokenizing.spacy_impl.tokenizers import SpacyTokenizer
from medcat.tokenizing.regex_impl.tokenizer import RegexTokenizer
from medcat.config import Config

import unittest


class DefaultTokenizerInitTests(unittest.TestCase):
    default_provider = 'spacy'
    default_cls = SpacyTokenizer
    default_creator = SpacyTokenizer.create_new_tokenizer
    exp_num_def_tokenizers = 2

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()

    def test_has_default(self):
        avail_tokenizers = tokenizers.list_available_tokenizers()
        self.assertEqual(len(avail_tokenizers), self.exp_num_def_tokenizers)
        name, cls_name = [(t_name, t_cls) for t_name, t_cls in avail_tokenizers
                          if t_name == self.default_provider][0]
        self.assertEqual(name, self.default_provider)
        self.assertIs(cls_name, self.default_creator.__name__)

    def test_can_create_def_tokenizer(self):
        tokenizer = tokenizers.create_tokenizer(
            self.default_provider, self.cnf)
        self.assertIsInstance(tokenizer,
                              runtime_checkable(tokenizers.BaseTokenizer))
        self.assertIsInstance(tokenizer, self.default_cls)


class DefaultTokenizerInitTests2(DefaultTokenizerInitTests):
    default_provider = 'regex'
    default_cls = RegexTokenizer
    default_creator = RegexTokenizer.create_new_tokenizer
