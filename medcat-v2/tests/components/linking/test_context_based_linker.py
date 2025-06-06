from medcat.components.linking import context_based_linker
from medcat.components import types
from medcat.config import Config
from medcat.vocab import Vocab
from medcat.cdb.concepts import CUIInfo, NameInfo
from medcat.components.types import TrainableComponent

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
        self.cui2info: dict[str, CUIInfo] = dict()
        self.name2info: dict[str, NameInfo] = dict()
        self.name_separator: str

    def weighted_average_function(self, nr: int) -> float:
        return nr // 2.0


class LinkingInitTests(ComponentInitTests, unittest.TestCase):
    expected_def_components = 3
    comp_type = types.CoreComponentType.linking
    default_cls = context_based_linker.Linker
    module = context_based_linker

    @classmethod
    def setUpClass(cls):
        cls.vocab = Vocab()
        cls.cdb = FakeCDB(Config())
        return super().setUpClass()


class TrainableLinkerTests(unittest.TestCase):
    cnf = Config()
    linker = context_based_linker.Linker(FakeCDB(cnf), None, cnf)

    def test_linker_is_trainable(self):
        self.assertIsInstance(self.linker, TrainableComponent)
