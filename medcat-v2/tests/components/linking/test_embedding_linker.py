from medcat.components.linking import embedding_linker
from medcat.components import types
from medcat.config import Config
from medcat.vocab import Vocab
from medcat.cdb.concepts import CUIInfo, NameInfo
from medcat.components.types import TrainableComponent
from medcat.components.types import _DEFAULT_LINKING as DEF_LINKING
import unittest
from ..helper import ComponentInitTests

class FakeDocument:
    linked_ents = []
    ner_ents = []
    def __init__(self, text):
        self.text = text

class FakeTokenizer:
    def __call__(self, text: str) -> FakeDocument:
        return FakeDocument(text)

class FakeCDB:
    def __init__(self, config: Config):
        self.is_dirty = False
        self.config = config
        self.cui2info: dict[str, CUIInfo] = dict()
        self.name2info: dict[str, NameInfo] = dict()
        self.name_separator: str

    def weighted_average_function(self, nr: int) -> float:
        return nr // 2.0


class EmbeddingLinkerInitTests(ComponentInitTests, unittest.TestCase):
    expected_def_components = len(DEF_LINKING)
    comp_type = types.CoreComponentType.linking
    default = 'medcat2_embedding_linker'
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

    def test_has_default(self):
        avail_components = types.get_registered_components(self.comp_type)
        registered_names = [name for name, _ in avail_components]
        self.assertIn("medcat2_embedding_linker", registered_names)

class NonTrainableEmbeddingLinkerTests(unittest.TestCase):
    cnf = Config()
    cnf.components.linking = embedding_linker.EmbeddingLinking()
    cnf.components.linking.comp_name = embedding_linker.Linker.name
    linker = embedding_linker.Linker(FakeCDB(cnf), cnf)

    def test_linker_is_not_trainable(self):
        self.assertNotIsInstance(self.linker, TrainableComponent)

    def test_linker_processes_document(self):
        doc = FakeDocument("Test Document")
        self.linker(doc) 