from typing import Any, Optional

from medcat2.components.addons import addons

from medcat2.cat import CAT
from medcat2.cdb import CDB
from medcat2.vocab import Vocab
from medcat2.config.config import Config, ComponentConfig
from medcat2.tokenizing.tokenizers import BaseTokenizer, MutableEntity

import unittest
import unittest.mock
import tempfile


class FakeAddonNoInit:
    name = 'fake_addon'

    def __init__(self, cnf: ComponentConfig):
        assert cnf.comp_name == self.name
        self.config = cnf

    def __call__(self, doc):
        return doc

    @property
    def should_save(self) -> bool:
        return False

    def save(self, path: str) -> None:
        return

    @property
    def addon_type(self) -> str:
        return 'FAKE'

    def get_folder_name(self) -> str:
        return "addon_" + self.full_name

    @property
    def full_name(self) -> str:
        return self.addon_type + "_" + str(self.name)

    def get_output_key_val(self, ent: MutableEntity
                           ) -> tuple[str, dict[str, Any]]:
        return '', {}


class FakeAddonWithInit:
    name = 'fake_addon_w_init'

    def __init__(self, cnf: ComponentConfig,
                 tokenizer: BaseTokenizer, cdb: CDB):
        assert cnf.comp_name == self.name
        self._token = tokenizer
        self._cdb = cdb
        self.config = cnf

    def __call__(self, doc):
        return doc

    @classmethod
    def get_init_args(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                      model_load_path: Optional[str]) -> list[Any]:
        return [tokenizer, cdb]

    @classmethod
    def get_init_kwargs(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                        model_load_path: Optional[str]) -> dict[str, Any]:
        return {}

    @property
    def should_save(self) -> bool:
        return False

    def save(self, path: str) -> None:
        return

    @property
    def addon_type(self) -> str:
        return 'FAKE'

    def get_folder_name(self) -> str:
        return "addon_" + self.full_name

    @property
    def full_name(self) -> str:
        return self.addon_type + "_" + str(self.name)


class AddonsRegistrationTests(unittest.TestCase):
    addon_cls = FakeAddonNoInit

    @classmethod
    def setUpClass(cls):
        addons.register_addon(cls.addon_cls.name, cls.addon_cls)

    @classmethod
    def tearDownClass(cls):
        addons._ADDON_REGISTRY.unregister_all_components()
        addons._ADDON_REGISTRY._lazy_defaults.update(addons._DEFAULT_ADDONS)

    def test_has_registration(self):
        addon_cls = addons.get_addon_creator(self.addon_cls.name)
        self.assertIs(addon_cls, self.addon_cls)

    def test_can_create_empty_addon(self):
        addon = addons.create_addon(
            self.addon_cls.name, ComponentConfig(
                comp_name=self.addon_cls.name))
        self.assertIsInstance(addon, self.addon_cls)


class AddonUsageTests(unittest.TestCase):
    addon_cls = FakeAddonNoInit
    EXP_ADDONS = 1

    @classmethod
    def setUpClass(cls):
        addons.register_addon(cls.addon_cls.name, cls.addon_cls)
        cls.cnf = Config()
        cls.cdb = CDB(cls.cnf)
        cls.vocab = Vocab()
        cls.cnf.components.addons.append(ComponentConfig(
            comp_name=cls.addon_cls.name))
        cls.cat = CAT(cls.cdb, cls.vocab)

    def test_has_addon(self):
        self.assertTrue(self.cat._pipeline._addons)
        addon = self.cat._pipeline._addons[0]
        self.assertIsInstance(addon, self.addon_cls)

    def test_addon_runs(self):
        with unittest.mock.patch.object(self.addon_cls, "__call__",
                                        unittest.mock.MagicMock()
                                        ) as mock_call:
            self.cat.get_entities("Some text")
            mock_call.assert_called_once()

    @classmethod
    def tearDownClass(cls):
        addons._ADDON_REGISTRY.unregister_all_components()
        addons._ADDON_REGISTRY._lazy_defaults.update(addons._DEFAULT_ADDONS)

    def test_can_create_cat_with_addon(self):
        self.assertIsInstance(self.cat, CAT)
        self.assertEqual(len(self.cat._pipeline._addons), self.EXP_ADDONS)

    def test_can_save_model(self):
        with tempfile.TemporaryDirectory() as ntd:
            full_path = self.cat.save_model_pack(ntd)
        self.assertIsInstance(full_path, str)

    def test_can_save_and_load(self):
        with tempfile.TemporaryDirectory() as ntd:
            full_path = self.cat.save_model_pack(ntd)
            cat = CAT.load_model_pack(full_path)
        self.assertIsInstance(cat, CAT)
        self.assertEqual(len(self.cat._pipeline._addons), self.EXP_ADDONS)


class AddonUsageWithInitTests(AddonUsageTests):
    addon_cls = FakeAddonWithInit
