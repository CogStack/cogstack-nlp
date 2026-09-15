from unittest import TestCase
from typing import Protocol, Type, runtime_checkable

from medcat.utils import registry


@runtime_checkable
class DummyProtocol(Protocol):

    def get_value(self) -> str:
        pass


class DummyDerivClass1(DummyProtocol):

    def get_value(self) -> str:
        return 'VER1'


class DummyDerivClass2(DummyProtocol):

    def get_value(self) -> str:
        return 'VER2'


class BaseRegistryTests(TestCase):
    COMP_NAME_TO_REGISTER1 = 'comp'
    UNKNOWN_COMP_NAME = 'NO-EXIST'
    COMP_NAME_TO_REGISTER1 = 'comp1'
    TYPE_TO_REGISTER1 = DummyDerivClass1
    COMP_NAME_TO_REGISTER2 = 'comp2'
    TYPE_TO_REGISTER2 = DummyDerivClass2

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = registry.Registry(DummyProtocol)

    def setUp(self) -> None:
        self.registry.unregister_all_components()

    def add_default_component1(self):
        self.registry.register(self.COMP_NAME_TO_REGISTER1,
                               self.TYPE_TO_REGISTER1)

    def add_default_component2(self):
        self.registry.register(self.COMP_NAME_TO_REGISTER2,
                               self.TYPE_TO_REGISTER2)

    def assert_registered(self, comp_name: str, exp_type: Type[DummyProtocol]):
        ct1 = self.registry.get_component(comp_name)
        self.assertIs(ct1, exp_type)


class SimpleRegistryTests(BaseRegistryTests):

    def test_fails_unknown_component(self):
        with self.assertRaises(registry.MedCATRegistryException):
            self.registry.get_component(self.UNKNOWN_COMP_NAME)

    def test_contains_no_unkonwn_component(self):
        self.assertNotIn(self.UNKNOWN_COMP_NAME, self.registry)


class RegistryWith1ItemTests(BaseRegistryTests):

    def setUp(self) -> None:
        super().setUp()
        self.add_default_component1()

    def test_registered_component_available(self):
        comp_type = self.registry.get_component(self.COMP_NAME_TO_REGISTER1)
        self.assertIs(comp_type, self.TYPE_TO_REGISTER1)

    def test_unregistered_component_not_available(self):
        self.assertNotIn(self.UNKNOWN_COMP_NAME, self.registry)
        with self.assertRaises(registry.MedCATRegistryException):
            self.registry.get_component(self.UNKNOWN_COMP_NAME)

    def test_getitem_same_as_get_component(self):
        self.assertIs(
            self.registry.get_component(self.COMP_NAME_TO_REGISTER1),
            self.registry[self.COMP_NAME_TO_REGISTER1])

    def test_lists_registered_components(self):
        reg_comps = self.registry.list_components()
        self.assertEqual(len(reg_comps), 1)  # 1 at a time


class RegistryWith2ItemsTests(BaseRegistryTests):

    def setUp(self) -> None:
        super().setUp()
        self.add_default_component1()
        self.add_default_component2()

    def test_gets_correct_component(self):
        with self.subTest("1st"):
            self.assert_registered(self.COMP_NAME_TO_REGISTER1,
                                   self.TYPE_TO_REGISTER1)
        with self.subTest("2nd"):
            self.assert_registered(self.COMP_NAME_TO_REGISTER2,
                                   self.TYPE_TO_REGISTER2)

    def test_lists_registered_components(self):
        reg_comps = self.registry.list_components()
        self.assertEqual(len(reg_comps), 2)  # both registered


class UnregisteringWithRegistryTests(BaseRegistryTests):

    def setUp(self):
        super().setUp()
        self.add_default_component1()
        self.add_default_component2()
        self.registry.unregister_component(self.COMP_NAME_TO_REGISTER1)

    def test_has_unregistered1(self):
        self.assertNotIn(self.COMP_NAME_TO_REGISTER1, self.registry)

    def test_has_kept_other(self):
        self.assertIn(self.COMP_NAME_TO_REGISTER2, self.registry)

    def test_lists_registered_component(self):
        reg_comps = self.registry.list_components()
        self.assertEqual(len(reg_comps), 1)  # 1 left


class UnregisterAllWithRegistryTests(BaseRegistryTests):

    def setUp(self):
        super().setUp()
        self.add_default_component1()
        self.add_default_component2()
        self.registry.unregister_all_components()

    def test_has_unregistered1(self):
        self.assertNotIn(self.COMP_NAME_TO_REGISTER1, self.registry)

    def test_has_unregistered2(self):
        self.assertNotIn(self.COMP_NAME_TO_REGISTER2, self.registry)

    def test_lists_no_components(self):
        reg_comps = self.registry.list_components()
        self.assertEqual(len(reg_comps), 0)  # none left


class RegistryWithDefaultsTests(TestCase):
    LAZY_DEFAULTS = {
        "COMP#1": ("tests.utils.test_registry", "DummyDerivClass1"),
        "COMP#2": ("tests.utils.test_registry", "DummyDerivClass2"),
    }
    EXPECTED_COMPS = [
        DummyDerivClass1,
        DummyDerivClass2
    ]

    def setUp(self) -> None:
        self.registry = registry.Registry(
            DummyProtocol, lazy_defaults=self.LAZY_DEFAULTS)

    def test_has_lazy_components(self):
        for name in self.LAZY_DEFAULTS:
            with self.subTest(name):
                self.assertIn(name, self.registry)

    def test_can_get_lazy_defaults(self):
        for name, expected in zip(self.LAZY_DEFAULTS, self.EXPECTED_COMPS):
            with self.subTest(name):
                comp = self.registry.get_component(name)
                self.assertIs(comp, expected)
                self.assertIn(name, self.registry)

    def test_lists_registered_components(self):
        reg_comps = self.registry.list_components()
        comp_names = [n for n, _ in reg_comps]
        comp_classes = [c for _, c in reg_comps]
        self.assertEqual(len(reg_comps), len(self.LAZY_DEFAULTS))
        self.assertEqual(set(comp_names), set(self.LAZY_DEFAULTS))
        exp_classes = [c for _, c in self.LAZY_DEFAULTS.values()]
        self.assertEqual(set(comp_classes), set(exp_classes))
