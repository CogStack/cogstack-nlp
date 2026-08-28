from typing import runtime_checkable

from medcat.tokenizing import tokenizers
from medcat.tokenizing.spacy_impl.tokenizers import SpacyTokenizer
from medcat.tokenizing.regex_impl.tokenizer import RegexTokenizer
from medcat.config import Config
from medcat.tokenizing.tokens import MutableDocument, MutableEntity, MutableToken
from medcat.utils.registry import Registry

import unittest


class DefaultTokenizerInitTests(unittest.TestCase):
    default_provider = 'spacy'
    default_cls = SpacyTokenizer
    default_creator = SpacyTokenizer.create_new_tokenizer
    exp_num_def_tokenizers = 2

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()

    def def_creator_name(self) -> str:
        return Registry.translate_name(self.default_creator)

    def test_has_default(self):
        avail_tokenizers = tokenizers.list_available_tokenizers()
        self.assertEqual(len(avail_tokenizers), self.exp_num_def_tokenizers)
        name, cls_name = [(t_name, t_cls) for t_name, t_cls in avail_tokenizers
                          if t_name == self.default_provider][0]
        self.assertEqual(name, self.default_provider)
        self.assertEqual(cls_name, self.def_creator_name())

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


class TokenizerTests(unittest.TestCase):
    default_provider = 'spacy'
    text = "Some text to tokenize"

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()

    def setUp(self) -> None:
        self.tokenizer = tokenizers.create_tokenizer(
            self.default_provider, self.cnf)
        self.doc = self.tokenizer(self.text)
        self.doc.ner_ents = self._create_ner_ents(self.doc)
        self.doc.linked_ents = self.doc.ner_ents.copy()

    def _create_ner_ents(
            self, doc: MutableDocument,
            targets: list[str] = ["text",]) -> list[MutableEntity]:
        return [
            self.tokenizer.create_entity(
                doc,
                (tkns := doc.get_tokens(
                    start := doc.base.text.index(target), start + len(target)))[0].base.index,
                tkns[-1].base.index + 1,
                label=target)
            for target in targets
        ]

    def test_getting_entity_based_on_tokens_gets_same_instance(self):
        for ent in self.doc.ner_ents:
            with self.subTest(f"Ent: {ent} in doc {self.doc}"):
                tokens = list(ent)
                got_ent = self.tokenizer.entity_from_tokens_in_doc(tokens, self.doc)
                self.assertIs(got_ent, ent)
                self.assertIn(got_ent, self.doc.ner_ents)
