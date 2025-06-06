from medcat.components import types

from medcat.tokenizing.tokens import BaseDocument, MutableDocument
from medcat.utils.registry import MedCATRegistryException

import unittest


class FakeCoreComponent(types.AbstractCoreComponent):
    name = None

    def __init__(self, comp_type: types.CoreComponentType,
                 name: str = "test-fake-component"):
        self.name = name
        self.comp_type = comp_type

    def get_type(self) -> types.CoreComponentType:
        return self.comp_type

    def __call__(self, raw: BaseDocument, mutable: MutableDocument
                 ) -> MutableDocument:
        return mutable


class TypesRegistrationTests(unittest.TestCase):
    # NOTE: if/when default commponents get added, this needs to change
    _DEF_COMPS = len(types._DEFAULT_LINKING)
    COMP_TYPE = types.CoreComponentType.linking
    WRONG_TYPE = types.CoreComponentType.ner
    COMP_NAME = "test-linker"
    BCC = FakeCoreComponent

    def setUp(self):
        types.register_core_component(self.COMP_TYPE, self.COMP_NAME, self.BCC)
        self.registered = types.create_core_component(
            self.COMP_TYPE, self.COMP_NAME, self.COMP_TYPE)

    def tearDown(self):
        for registry in types._CORE_REGISTRIES.values():
            for comp_name, _ in registry.list_components():
                comp_cls = registry.get_component(comp_name)
                cls_path = comp_cls.__module__ + "." + comp_cls.__name__
                if not cls_path.startswith("medcat."):
                    registry.unregister_component(comp_name)
        # register defaults
        for registry, def_lazy in [
            (types._CORE_REGISTRIES[types.CoreComponentType.tagging],
             types._DEFAULT_TAGGERS),
            (types._CORE_REGISTRIES[
                types.CoreComponentType.token_normalizing],
                types._DEFAULT_NORMALIZERS),
            (types._CORE_REGISTRIES[types.CoreComponentType.ner],
             types._DEFAULT_NER),
            (types._CORE_REGISTRIES[types.CoreComponentType.linking],
             types._DEFAULT_LINKING),
        ]:
            for comp_name, comp_info in def_lazy.items():
                # unregister if already fully registered
                if comp_name not in registry._lazy_defaults:
                    # i.e removed from lazy defaults
                    registry.unregister_component(comp_name)
                    # and only register if not already registered
                    # as lazy default
                    registry._lazy_defaults[comp_name] = comp_info

    def test_registered_is_core_component(self):
        self.assertIsInstance(self.registered, types.CoreComponent)

    def test_registered_is_fake_component(self):
        self.assertIsInstance(self.registered, FakeCoreComponent)

    def test_does_not_get_incorrect_type(self):
        with self.assertRaises(MedCATRegistryException):
            types.create_core_component(self.WRONG_TYPE, self.COMP_NAME)

    def test_does_not_get_incorrect_name(self):
        with self.assertRaises(MedCATRegistryException):
            types.create_core_component(self.COMP_TYPE, "#" + self.COMP_NAME)

    def test_lists_registered_component(self):
        comps = types.get_registered_components(self.COMP_TYPE)
        self.assertEqual(len(comps), 1 + self._DEF_COMPS)
        self.assertTrue(any(comp_name == self.COMP_NAME
                            for comp_name, _ in comps))
        self.assertTrue(any(comp_cls == self.BCC.__name__
                            for _, comp_cls in comps))
