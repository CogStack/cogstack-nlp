from typing import runtime_checkable
from medcat2.tokenizing.regex_impl import tokenizer

from unittest import TestCase


class TokenizerTests(TestCase):
    TEXT_SIMPLE = ("This is - some simple test and 32 numbers 2-tokenize! "
                   "And then some!")
    EXP_TOKENS = ["This", "is", "-", "some", "simple", "test", "and", "32",
                  "numbers", "2", "-tokenize!", "And", "then", "some", "!"]
    BIG_NUMBER = 10_000_000

    @classmethod
    def setUpClass(cls):
        cls.tokenizer = tokenizer.RegexTokenizer()
        cls.doc = cls.tokenizer(cls.TEXT_SIMPLE)
        cls.tokens = cls.doc.get_tokens(0, cls.BIG_NUMBER)

    def test_gets_document(self):
        self.assertIsInstance(self.doc, tokenizer.Document)
        self.assertIsInstance(self.doc,
                              runtime_checkable(tokenizer.BaseDocument))

    def test_doc_has_correct_num_tokens(self):
        self.assertEqual(len(self.tokens), len(self.EXP_TOKENS))

    def test_doc_has_tokens(self):
        self.assertTrue(all(isinstance(tkn, tokenizer.Token)
                            for tkn in self.tokens))

    def test_doc_has_correct_tokens(self):
        self.assertEqual([tkn.base.text for tkn in self.tokens],
                         self.EXP_TOKENS)
