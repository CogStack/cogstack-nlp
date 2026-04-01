from medcat_embedding_linker import embedding_linker
from medcat_embedding_linker import trainable_embedding_linker
from medcat.components import types
from medcat.config import Config
from medcat.data.entities import Entity
from medcat.vocab import Vocab
from medcat.cat import CAT
from medcat.cdb.concepts import CUIInfo, NameInfo
from medcat.components.types import TrainableComponent
from medcat.components.types import _DEFAULT_LINKING as DEF_LINKING
import unittest
from .helper import ComponentInitTests

from . import UNPACKED_EXAMPLE_MODEL_PACK_PATH


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
    default = "embedding_linker"
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
        self.assertIn("embedding_linker", registered_names)


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


class TrainableEmbeddingLinkerTests(unittest.TestCase):
    cnf = Config()
    cnf.components.linking = embedding_linker.EmbeddingLinking()
    cnf.components.linking.comp_name = (
        trainable_embedding_linker.TrainableEmbeddingLinker.name
    )
    linker = trainable_embedding_linker.TrainableEmbeddingLinker(FakeCDB(cnf), cnf)

    def test_linker_is_trainable(self):
        self.assertIsInstance(self.linker, TrainableComponent)


class EmbeddingModelDisambiguationTests(unittest.TestCase):
    PLACEHOLDER = "{SOME_PLACEHOLDER}"
    TEXT = f"""The issue has a lot to do with the {PLACEHOLDER}"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.model = CAT.load_model_pack(UNPACKED_EXAMPLE_MODEL_PACK_PATH)
        cls.model.config.components.linking = embedding_linker.EmbeddingLinking()
        cls.model._recreate_pipe()
        linker: embedding_linker.Linker = cls.model.pipe.get_component(
            types.CoreComponentType.linking
        )
        linker.create_embeddings()
        cls.linker = linker

    def test_is_correct_linker(self):
        self.assertIsInstance(self.linker, embedding_linker.Linker)

    def assert_has_name(self, out_ents: dict[int, Entity], name: str):
        self.assertTrue(any(ent["source_value"] == name for ent in out_ents.values()))

    def test_does_disambiguation(self):
        used_names = 0
        for name, info in self.model.cdb.name2info.items():
            if len(info["per_cui_status"]) <= 1:
                continue
            used_names += 1
            with self.subTest(name):
                cur_text = self.TEXT.replace(self.PLACEHOLDER, name)
                out_ents = self.model.get_entities(cur_text)["entities"]
                self.assert_has_name(out_ents, name)
        self.assertGreater(used_names, 0)
