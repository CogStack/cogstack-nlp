from medcat2.components.ner import vocab_based_ner
from medcat2.components import types
from medcat2.config import Config

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
    expected_def_components = 3
    comp_type = types.CoreComponentType.ner
    default_cls = vocab_based_ner.NER
    module = vocab_based_ner

    @classmethod
    def setUpClass(cls):
        cls.tokenizer = FakeTokenizer()
        cls.cdb_vocab = dict()
        cls.cdb = FakeCDB(Config())
        return super().setUpClass()
