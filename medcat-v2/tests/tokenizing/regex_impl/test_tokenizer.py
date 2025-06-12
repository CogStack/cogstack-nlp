from typing import runtime_checkable
from medcat.tokenizing.regex_impl import tokenizer

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


class EntitySimpleAddonDataTests(TestCase):
    EXAMPLE_TEXT = "Some example text"
    ADDON_PATH = "test_time_addon"

    @classmethod
    def setUpClass(cls):
        cls.tokenizer = tokenizer.RegexTokenizer()
        cls.tokenizer.get_entity_class().register_addon_path(cls.ADDON_PATH)

    def _make_tokens_entities(self):
        num_tokens = len(self.doc)
        for ent_num in range(num_tokens):
            ent = self.doc[ent_num: ent_num + 1]
            self.doc.ner_ents.append(ent)

    def _set_single_entity_data(self, ent_num: int,
                                entity: tokenizer.MutableEntity):
        entity.set_addon_data(self.ADDON_PATH, ent_num)

    def _get_expected_data(self, ent_num: int,
                           entity: tokenizer.MutableEntity):
        return ent_num

    def _set_per_entity_data(self):
        for ent_num, entity in enumerate(self.doc.ner_ents):
            self._set_single_entity_data(ent_num, entity)

    def setUp(self):
        self.doc = self.tokenizer(self.EXAMPLE_TEXT)
        # add all tokens as entities
        self._make_tokens_entities()
        # set addon data for all tokens
        self._set_per_entity_data()

    def test_can_get_addon_data(self):
        self.assertGreater(len(self.doc.ner_ents), 0)
        for ent_num, entity in enumerate(self.doc.ner_ents):
            with self.subTest(f"Entity {ent_num}: {entity}"):
                data_val = entity.get_addon_data(self.ADDON_PATH)
                self.assertEqual(data_val, self._get_expected_data(
                    ent_num, entity))


class EntityComplexAddonTests(EntitySimpleAddonDataTests):
    ADDON_PATH = "complex_data_path"

    def _set_single_entity_data(self, ent_num: int,
                                entity: tokenizer.MutableEntity):
        if (data := entity.get_addon_data(self.ADDON_PATH)) is not None:
            data[len(data)] = ent_num
        else:
            entity.set_addon_data(self.ADDON_PATH, {0: ent_num})

    def _get_expected_data(self, ent_num: int,
                           entity: tokenizer.MutableEntity):
        return {0: ent_num}
