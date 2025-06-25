from medcat.components import types
from medcat.config.config import Config, ComponentConfig
from medcat.cdb.cdb import CDB
from medcat.vocab import Vocab
from medcat.cat import CAT
from medcat.tokenizing.tokenizers import BaseTokenizer
from .helper import FakeCDB, FVocab, FTokenizer

import unittest
import unittest.mock
import tempfile

# NOTE:
# The following 2 classes are (trivial!) examples of a component
# having been overwritten.
# After they are registered, they can be used just as the corresponding
# default implementations


class NoInitNER(types.AbstractCoreComponent):
    name = 'no-init-ner'

    def __call__(self, doc):
        return doc

    def get_type(self):
        return types.CoreComponentType.ner

    @classmethod
    def create_new_component(cls, cnf, tokenizer, cdb, vocab, model_load_path):
        return cls()


class WithInitNER(types.AbstractCoreComponent):
    name = 'with-init-ner'

    def __init__(self, tokenizer: BaseTokenizer,
                 cdb: CDB):
        super().__init__()
        self.tokenizer = tokenizer
        self.cdb = cdb

    def __call__(self, doc):
        return doc

    def get_type(self):
        return types.CoreComponentType.ner

    @classmethod
    def create_new_component(cls, cnf, tokenizer, cdb, vocab, model_load_path):
        return cls(cnf, tokenizer)


class RegisteredCompBaseTests(unittest.TestCase):
    TYPE = types.CoreComponentType.ner
    TO_REGISTR_CLS = NoInitNER

    @classmethod
    def setUpClass(cls):
        cls.TO_REGISTR = cls.TO_REGISTR_CLS.create_new_component
        types.register_core_component(cls.TYPE, cls.TO_REGISTR_CLS.name,
                                      cls.TO_REGISTR)

    @classmethod
    def tearDownClass(cls):
        # unregister component
        types._CORE_REGISTRIES[cls.TYPE].unregister_component(
            cls.TO_REGISTR_CLS.name)


class CoreCompNoInitRegistrationTests(RegisteredCompBaseTests):
    CNF = Config()
    FCDB = FakeCDB(CNF)
    FVOCAB = FVocab()
    FTOK = FTokenizer()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def register_args(self):
        return None, None, None, None, None

    def test_can_create_component(self):
        comp = types.create_core_component(self.TYPE, self.TO_REGISTR_CLS.name, *self.register_args())
        self.assertIsInstance(comp, self.TO_REGISTR_CLS)


class CoreCompWithInitRegistrationTests(CoreCompNoInitRegistrationTests):
    TO_REGISTR_CLS = WithInitNER


class CoreCompNoInitCATTests(RegisteredCompBaseTests):

    @classmethod
    def setUpClass(cls):
        # register
        super().setUpClass()
        # setup CDB/vocab
        cls.cdb = CDB(Config())
        cls.vocab = Vocab()
        # set name in component config
        comp_cnf: ComponentConfig = getattr(cls.cdb.config.components,
                                            cls.TYPE.name)
        comp_cnf.comp_name = cls.TO_REGISTR_CLS.name
        # NOTE: init arguments should be handled automatically
        cls.cat = CAT(cdb=cls.cdb, vocab=cls.vocab)

    def test_can_be_used_in_config(self):
        self.assertIsInstance(self.cat, CAT)

    def test_comp_runs(self):
        with unittest.mock.patch.object(self.TO_REGISTR_CLS, "__call__",
                                        unittest.mock.MagicMock()
                                        ) as mock_call:
            self.cat.get_entities("Some text")
            mock_call.assert_called_once()

    def test_can_save(self):
        with tempfile.TemporaryDirectory() as folder:
            full_path = self.cat.save_model_pack(folder)
        self.assertIsInstance(full_path, str)

    def test_can_save_and_load(self):
        with tempfile.TemporaryDirectory() as folder:
            full_path = self.cat.save_model_pack(folder)
            cat = CAT.load_model_pack(full_path)
        self.assertIsInstance(cat, CAT)
        comp = cat._pipeline.get_component(self.TYPE)
        self.assertIsInstance(comp, self.TO_REGISTR_CLS)


class CoreCompWithInitCATTests(CoreCompNoInitCATTests):
    TO_REGISTR_CLS = WithInitNER
