from typing import Optional, Protocol, Callable, runtime_checkable, Union, Any
from enum import Enum, auto

from medcat.utils.registry import Registry
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.cdb import CDB
from medcat.vocab import Vocab


class CoreComponentType(Enum):
    tagging = auto()
    token_normalizing = auto()
    ner = auto()
    linking = auto()


@runtime_checkable
class BaseComponent(Protocol):

    @property
    def full_name(self) -> Optional[str]:
        """Name with the component type (e.g ner, linking, meta)."""
        pass

    @property
    def name(self) -> str:
        """The name of the component."""
        pass

    def is_core(self) -> bool:
        """Whether the component is a core component or not.

        Returns:
            bool: Whether this is a core component.
        """
        pass

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        pass

    @classmethod
    def get_init_args(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                      model_load_path: Optional[str]) -> list[Any]:
        """Get the init arguments for the component.

        Args:
            tokenizer (BaseTokenizer): The tokenizer.
            cdb (CDB): The CDB.
            vocab (Vocab): The Vocab.
            model_load_path (Optional[str]): The model load path (or None).

        Returns:
            list[Any]: The list of init arguments.
        """
        pass

    @classmethod
    def get_init_kwargs(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                        model_load_path: Optional[str]) -> dict[str, Any]:
        """Get init keyword arguments for the component.

        Args:
            tokenizer (BaseTokenizer): The tokenizer.
            cdb (CDB): The CDB.
            vocab (Vocab): The Vocab.
            model_load_path (Optional[str]): The model load path (or None).

        Returns:
            dict[str, Any]: The keywrod arguments.
        """
        pass


@runtime_checkable
class CoreComponent(BaseComponent, Protocol):

    def get_type(self) -> CoreComponentType:
        pass


class AbstractCoreComponent(CoreComponent):
    NAME_PREFIX = "core_"

    @property
    def full_name(self) -> str:
        return self.get_type().name + ":" + str(self.name)

    def is_core(self) -> bool:
        return True


@runtime_checkable
class HashableComponet(Protocol):

    def get_hash(self) -> str:
        pass


@runtime_checkable
class TrainableComponent(Protocol):

    def train(self, cui: str,
              entity: MutableEntity,
              doc: MutableDocument,
              negative: bool = False,
              names: Union[list[str], dict] = []) -> None:
        """Train the component.

        This should only apply to the linker.

        Args:
            cui (str): The CUI to train.
            entity (BaseEntity): The entity we're at.
            doc (BaseDocument): The document within which we're working.
            negative (bool): Whether or not the example is negative.
                Defaults to False.
            names (list[str]/dict):
                Optionally used to update the `status` of a name-cui
                pair in the CDB.
        """
        pass


_DEFAULT_TAGGERS: dict[str, tuple[str, str]] = {
    "default": ("medcat.components.tagging.tagger", "TagAndSkipTagger"),
}
_DEFAULT_NORMALIZERS: dict[str, tuple[str, str]] = {
    "default": ("medcat.components.normalizing.normalizer",
                "TokenNormalizer"),
}
_DEFAULT_NER: dict[str, tuple[str, str]] = {
    "default": ("medcat.components.ner.vocab_based_ner", "NER"),
    "dict": ("medcat.components.ner.dict_based_ner", "NER"),
    "transformers_ner": ("medcat.components.ner.trf.transformers_ner",
                         "TransformersNER.create_new"),
}
_DEFAULT_LINKING: dict[str, tuple[str, str]] = {
    "default": ("medcat.components.linking.context_based_linker", "Linker"),
    "no_action": ("medcat.components.linking.no_action_linker",
                  "NoActionLinker"),
    "medcat2_two_step_linker": (
        "medcat.components.linking.two_step_context_based_linker",
        "TwoStepLinker")
}


_CORE_REGISTRIES: dict[CoreComponentType, Registry[CoreComponent]] = {
    CoreComponentType.tagging: Registry(
        CoreComponent, lazy_defaults=_DEFAULT_TAGGERS),  # type: ignore
    CoreComponentType.token_normalizing: Registry(
        CoreComponent, lazy_defaults=_DEFAULT_NORMALIZERS),  # type: ignore
    CoreComponentType.ner: Registry(CoreComponent,  # type: ignore
                                    lazy_defaults=_DEFAULT_NER),
    CoreComponentType.linking: Registry(CoreComponent,  # type: ignore
                                        lazy_defaults=_DEFAULT_LINKING),
}


def register_core_component(comp_type: CoreComponentType,
                            comp_name: str,
                            comp_clazz: Callable[..., CoreComponent]) -> None:
    """Register a new core component.

    Args:
        comp_type (CoreComponentType): The component type.
        comp_name (str): The component name.
        comp_clazz (Callable[..., CoreComponent]): The component creator.
    """
    _CORE_REGISTRIES[comp_type].register(comp_name, comp_clazz)


def get_core_registry(comp_type: CoreComponentType) -> Registry[CoreComponent]:
    """Get the registry for a core component type.

    Args:
        comp_type (CoreComponentType): The core component type.

    Returns:
        Registry[CoreComponent]: The corresponding registry.
    """
    return _CORE_REGISTRIES[comp_type]


def get_component_creator(comp_type: CoreComponentType,
                          comp_name: str) -> Callable[..., CoreComponent]:
    """Get the component creator.

    Args:
        comp_type (CoreComponentType): The core component type.
        comp_name (str): The component name.

    Returns:
        Callable[..., CoreComponent]: The creator for the component.
    """
    return get_core_registry(comp_type).get_component(comp_name)


def create_core_component(comp_type: CoreComponentType,
                          comp_name: str,
                          *args, **kwargs) -> CoreComponent:
    """Creat a core component.

    All `*args` and `**kwrags` are passed directly to the component creator.

    Args:
        comp_type (CoreComponentType): The component type.
        comp_name (str): The name of the component.

    Returns:
        CoreComponent: The resulting / created component.
    """
    comp_getter = get_core_registry(comp_type).get_component(comp_name)
    return comp_getter(*args, **kwargs)


def get_registered_components(comp_type: CoreComponentType
                              ) -> list[tuple[str, str]]:
    """Get all registered components (name and class name for each).

    Args:
        comp_type (CoreComponentType): The core component type.

    Returns:
        list[tuple[str, str]]: The name and class name for each
            registered component.
    """
    registry = get_core_registry(comp_type)
    return registry.list_components()
