from typing import Optional, Protocol, Callable, runtime_checkable, Union
from typing_extensions import Self
from enum import Enum, auto

from medcat.utils.registry import Registry, MedCATRegistryException
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import ComponentConfig


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
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]) -> Self:
        """Create a new component or load one off disk if load path presented.

        This may raise an exception if the wrong type of config is provided.

        Args:
            cnf (ComponentConfig): The config relevant to this components.
            tokenizer (BaseTokenizer): The base tokenizer.
            cdb (CDB): The CDB.
            vocab (Vocab): The Vocab.
            model_load_path (Optional[str]): Model load path (if present).

        Returns:
            Self: The new components.
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
    "default": ("medcat.components.tagging.tagger",
                "TagAndSkipTagger.create_new_component"),
}
_DEFAULT_NORMALIZERS: dict[str, tuple[str, str]] = {
    "default": ("medcat.components.normalizing.normalizer",
                "TokenNormalizer.create_new_component"),
}
_DEFAULT_NER: dict[str, tuple[str, str]] = {
    "default": ("medcat.components.ner.vocab_based_ner",
                "NER.create_new_component"),
    "dict": ("medcat.components.ner.dict_based_ner",
             "NER.create_new_component"),
    "transformers_ner": ("medcat.components.ner.trf.transformers_ner",
                         "TransformersNER.create_new_component"),
}
_DEFAULT_LINKING: dict[str, tuple[str, str]] = {
    "default": ("medcat.components.linking.context_based_linker",
                "Linker.create_new_component"),
    "no_action": ("medcat.components.linking.no_action_linker",
                  "NoActionLinker.create_new_component"),
    "medcat2_two_step_linker": (
        "medcat.components.linking.two_step_context_based_linker",
        "TwoStepLinker.create_new_component")
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

CompClass = Callable[[ComponentConfig, BaseTokenizer,
                      CDB, Vocab, Optional[str]], CoreComponent]


def register_core_component(comp_type: CoreComponentType,
                            comp_name: str,
                            comp_clazz: CompClass) -> None:
    """Register a new core component.

    Args:
        comp_type (CoreComponentType): The component type.
        comp_name (str): The component name.
        comp_clazz (ComplClass): The component creator.
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
                          comp_name: str) -> CompClass:
    """Get the component creator.

    Args:
        comp_type (CoreComponentType): The core component type.
        comp_name (str): The component name.

    Returns:
        Callable[..., CoreComponent]: The creator for the component.
    """
    return get_core_registry(comp_type).get_component(comp_name)


def create_core_component(
        comp_type: CoreComponentType, comp_name: str, cnf: ComponentConfig,
        tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
        model_load_path: Optional[str]) -> CoreComponent:
    """Creat a core component.

    Args:
        comp_type (CoreComponentType): The component type.
        comp_name (str): The name of the component.
        cnf (ComponentConfig): The config to be passed to creator.
        tokenizer (BaseTokenizer): The tokenizer to be passed to creator.
        cdb (CDB): The CDB to be passed to creator.
        vocab (Vocab): The vocab to be passed to the creator.
        model_load_path (Optional[str]): The optional load path to be passed
            to the creators.

    Returns:
        CoreComponent: The resulting / created component.
    """
    try:
        comp_getter = get_core_registry(comp_type).get_component(comp_name)
    except MedCATRegistryException as err:
        raise MedCATRegistryException(f"With comp type '{comp_type}'") from err
    return comp_getter(cnf, tokenizer, cdb, vocab, model_load_path)


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
