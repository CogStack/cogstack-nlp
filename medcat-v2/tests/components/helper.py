from typing import runtime_checkable, Type, Callable

from medcat.components import types
from medcat.config.config import Config, ComponentConfig


class FakeCDB:

    def __init__(self, cnf: Config):
        self.config = cnf
        self.token_counts = {}
        self.cui2info = {}
        self.name2info = {}

    def weighted_average_function(self, v: int) -> float:
        return v * 0.5


class FVocab:
    pass


class FTokenizer:
    pass


class ComponentInitTests:
    expected_def_components = 1
    default = 'default'
    # these need to be specified when overriding
    comp_type: types.CoreComponentType
    default_cls: Type[types.BaseComponent]
    default_creator: Callable[..., types.BaseComponent]

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()
        cls.fcdb = FakeCDB(cls.cnf)
        cls.fvocab = FVocab()
        cls.vtokenizer = FTokenizer()
        cls.comp_cnf: ComponentConfig = getattr(
            cls.cnf.components, cls.comp_type.name)

    def test_has_default(self):
        avail_components = types.get_registered_components(self.comp_type)
        self.assertEqual(len(avail_components), self.expected_def_components)
        name, cls_name = avail_components[0]
        self.assertEqual(name, self.default)
        self.assertIs(cls_name, self.default_creator.__name__)

    def test_can_create_def_component(self):
        component = types.create_core_component(
            self.comp_type,
            self.default, self.cnf, self.vtokenizer, self.fcdb, self.fvocab, None)
        self.assertIsInstance(component,
                              runtime_checkable(types.BaseComponent))
        self.assertIsInstance(component, self.default_cls)
