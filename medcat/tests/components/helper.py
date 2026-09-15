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
        if isinstance(cls.default_creator, Type):
            cls._def_creator_name_opts = (cls.default_creator.__name__,)
        else:
            # classmethod
            cls._def_creator_name_opts = (".".join((
                # etiher class.method_name
                cls.default_creator.__self__.__name__,
                cls.default_creator.__name__)),
                # or just method_name
                cls.default_creator.__name__
                )

    def test_has_default(self):
        avail_components = types.get_registered_components(self.comp_type)
        self.assertEqual(len(avail_components), self.expected_def_components)
        name, cls_name = avail_components[0]
        # 1 name / cls name
        eq_name = [name == self.default for name, _ in avail_components]
        eq_cls = [cls_name in self._def_creator_name_opts
                  for _, cls_name in avail_components]
        self.assertEqual(sum(eq_name), 1)
        # NOTE: for NER both the default as well as the Dict based NER
        #       have the came class name, so may be more than 1
        self.assertGreaterEqual(sum(eq_cls), 1)
        # needs to have the same class where name is equal
        self.assertTrue(eq_cls[eq_name.index(True)])

    def test_can_create_def_component(self):
        component = types.create_core_component(
            self.comp_type,
            self.default, self.cnf, self.vtokenizer, self.fcdb, self.fvocab, None)
        self.assertIsInstance(component,
                              runtime_checkable(types.BaseComponent))
        self.assertIsInstance(component, self.default_cls)
