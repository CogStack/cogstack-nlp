from medcat.components.linking import embedding_linker
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
    def __call__(self, text: str) -> FakeDocument:
        return FakeDocument(text)

class FakeCDB:
    def __init__(self, config: Config):
        self.config = config
        self.cui2info: dict[str, CUIInfo] = dict()
        self.name2info: dict[str, NameInfo] = dict()
        self.name_separator: str

    def weighted_average_function(self, nr: int) -> float:
        return nr // 2.0


class EmbeddingLinkerInitTests(ComponentInitTests, unittest.TestCase):
    expected_def_components = 4
    comp_type = types.CoreComponentType.linking
    default_cls = embedding_linker.Linker
    default_creator = embedding_linker.Linker.create_new_component
    module = embedding_linker

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()
        cls.cnf.components.linking = embedding_linker.EmbeddingLinking()
        cls.cnf.components.linking.comp_name = embedding_linker.Linker.name
        cls.fcdb = FakeCDB(cls.cnf)
        cls.fvocab = Vocab()
        cls.vtokenizer = FakeTokenizer()
        cls.comp_cnf = getattr(cls.cnf.components, cls.comp_type.name)

    def test_can_create_def_component(self):
        component = types.create_core_component(
            self.comp_type,
            "medcat2_embedding_linker",  # explicitly request embedding linker
            self.cnf, self.vtokenizer, self.fcdb, self.fvocab, None
        )
        self.assertIsInstance(component, self.default_cls)

    def test_has_default(self):
        avail_components = types.get_registered_components(self.comp_type)
        registered_names = [name for name, _ in avail_components]
        self.assertIn("medcat2_embedding_linker", registered_names)

class TrainableEmbeddingLinkerTests(unittest.TestCase):
    cnf = Config()
    cnf.components.linking = embedding_linker.EmbeddingLinking()
    cnf.components.linking.comp_name = embedding_linker.Linker.name
    linker = embedding_linker.Linker(FakeCDB(cnf), cnf)

    def test_linker_is_trainable(self):
        self.assertNotIsInstance(self.linker, TrainableComponent)
