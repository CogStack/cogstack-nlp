from medcat.components.ner import vocab_based_ner
from medcat.components import types
from medcat.config import Config
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.vocab import Vocab

import unittest

from ..helper import ComponentInitTests


class FakeDocument:

    def __init__(self, text):
        self.text = text


class FakeTokenizer:

    def __call__(selt, text: str) -> FakeDocument:
        return FakeDocument(text)


class FakeCDB:

    def __init__(self, config: Config):
        self.config = config


class NerInitTests(ComponentInitTests, unittest.TestCase):
    expected_def_components = len(types._DEFAULT_NER)
    comp_type = types.CoreComponentType.ner
    default_cls = vocab_based_ner.NER
    default_creator = vocab_based_ner.NER.create_new_component
    module = vocab_based_ner

    @classmethod
    def setUpClass(cls):
        cls.tokenizer = FakeTokenizer()
        cls.cdb_vocab = dict()
        cls.cdb = FakeCDB(Config())
        return super().setUpClass()


class TokensToRawNameTests(unittest.TestCase):
    AVOID_TARGETS = [
        "~~", "~\n~", "~\n",
    ]
    EMPTY_TOKEN_TEXTS = [
        "my string  double space",
        "my string \n with newline",
        "my string ends newline\n",
    ]

    @classmethod
    def setUpClass(cls) -> None:
        config = Config()
        config.general.nlp.provider = 'spacy'
        vocab = Vocab()
        cdb = CDB(config)
        cls.cat = CAT(cdb, vocab, config)

    def test_ignores_empty_tokens(self):
        for text in self.EMPTY_TOKEN_TEXTS:
            tkns = list(self.cat(text))
            with self.subTest(f"{text}"):
                opts = vocab_based_ner.tokens_to_raw_name_opts(
                    tkns, "~", False
                )
                for opt in opts:
                    for target in self.AVOID_TARGETS:
                        self.assertNotIn(target, opt)
