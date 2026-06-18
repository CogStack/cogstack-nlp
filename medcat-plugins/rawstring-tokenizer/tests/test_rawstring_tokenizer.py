from typing import runtime_checkable
from medcat.tokenizing import tokenizers
from medcat_rawstring_tokenizer.tokenizer import RawstringTokenizer
from medcat.config import Config
from medcat.tokenizing.tokens import MutableDocument, MutableEntity, MutableToken
from medcat.utils.registry import Registry
from medcat.tokenizing.tokenizers import register_tokenizer

import unittest


class RawstringTokenizerInitTests(unittest.TestCase):
    default_provider = 'rawstring_tokenizer'
    default_cls = RawstringTokenizer
    default_creator = RawstringTokenizer.create_new_tokenizer
    # spacy, regex, and now this
    exp_num_def_tokenizers = 3

    @classmethod
    def setUpClass(cls):
        register_tokenizer('rawstring_tokenizer', RawstringTokenizer.create_new_tokenizer)
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


class TokenizerTests(unittest.TestCase):
    default_provider = 'rawstring_tokenizer'
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
        token_start = 1
        token_end = 2
        return [
            self.tokenizer.create_entity(
                doc=doc,
                token_start_index=token_start,
                token_end_index=token_end,
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
