from medcat_transformer_ner import transformer_ner
from medcat.components import types
from medcat.config import Config
from medcat.vocab import Vocab
from medcat.components.types import _DEFAULT_NER as DEFAULT_NER
import unittest

from .helper import ComponentInitTests

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
    expected_def_components = len(DEFAULT_NER)
    comp_type = types.CoreComponentType.ner
    default = "transformer_ner"
    default_cls = transformer_ner.NER
    default_creator = transformer_ner.NER.create_new_component
    module = transformer_ner

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()
        cls.cnf.components.ner = transformer_ner.TransformerNER()
        cls.cnf.components.linking.comp_name = transformer_ner.NER.name
        cls.fcdb = FakeCDB(cls.cnf)
        cls.fvocab = Vocab()
        cls.vtokenizer = FakeTokenizer()
        cls.comp_cnf = getattr(cls.cnf.components, cls.comp_type.name)

    def test_has_default(self):
        avail_components = types.get_registered_components(self.comp_type)
        registered_names = [name for name, _ in avail_components]
        self.assertIn("transformer_ner", registered_names)