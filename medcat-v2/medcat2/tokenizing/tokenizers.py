from typing import Protocol, Type, Any, Callable
import logging

from medcat2.config import Config
from medcat2.tokenizing.tokens import (MutableDocument, MutableEntity,
                                       MutableToken)
from medcat2.utils.registry import Registry


logger = logging.getLogger(__name__)


class BaseTokenizer(Protocol):
    """The base tokenizer protocol."""

    def create_entity(self, doc: MutableDocument,
                      token_start_index: int, token_end_index: int,
                      label: str) -> MutableEntity:
        """Create an entity from a document.

        Args:
            doc (MutableDocument): The document to use.
            token_start_index (int): The token start index.
            token_end_index (int): The token end index.
            label (str): The label.

        Returns:
            MutableEntity: The resulting entity.
        """
        pass

    def entity_from_tokens(self, tokens: list[MutableToken]) -> MutableEntity:
        """Get an entity from the list of tokens.

        Args:
            tokens (list[MutableToken]): List of tokens.

        Returns:
            MutableEntity: The resulting entity.
        """
        pass

    def __call__(self, text: str) -> MutableDocument:
        pass

    @classmethod
    def get_init_args(cls, config: Config) -> list[Any]:
        pass

    @classmethod
    def get_init_kwargs(cls, config: Config) -> dict[str, Any]:
        pass

    def get_doc_class(self) -> Type[MutableDocument]:
        """Get the document implementation class used by the tokenizer.

        This can be used (e.g) to register addon paths.

        Returns:
            Type[MutableDocument]: The document class.
        """
        pass

    def get_entity_class(self) -> Type[MutableEntity]:
        """Get the entity implementation class used by the tokenizer.

        Returns:
            Type[MutableEntity]: The entity class.
        """
        pass


_DEFAULT_TOKENIZING: dict[str, tuple[str, str]] = {
    "regex": ("medcat2.tokenizing.regex_impl.tokenizer", "RegexTokenizer"),
    "spacy": ("medcat2.tokenizing.spacy_impl.tokenizers", "SpacyTokenizer")
}

_TOKENIZERS_REGISTRY = Registry(BaseTokenizer,  # type: ignore
                                lazy_defaults=_DEFAULT_TOKENIZING)


def get_tokenizer_creator(tokenizer_name: str) -> Callable[..., BaseTokenizer]:
    """Get the creator method for the tokenizer.

    While this is generally just the class instance (i.e refers
    to the `___init__`), another callable can be used internally.

    Args:
        tokenizer_name (str): The name of the tokenizer.

    Returns:
        Callable[..., BaseTokenizer]: The creator for the tokenizer.
    """
    return _TOKENIZERS_REGISTRY.get_component(tokenizer_name)


def create_tokenizer(tokenizer_name: str, *args, **kwargs) -> BaseTokenizer:
    """Create the tokenizer given the init arguments.

    The `*args`, and `**kwargs` will be directly passed to the creator.

    Args:
        tokenizer_name (str): The tokenizer name.

    Returns:
        BaseTokenizer: The created tokenizer.
    """
    return _TOKENIZERS_REGISTRY.get_component(tokenizer_name)(*args, **kwargs)


def list_available_tokenizers() -> list[tuple[str, str]]:
    """Get the available tokenizers.

    Returns:
        list[tuple[str, str]]: The list of the name, and class name
            of the available tokenizer.
    """
    return _TOKENIZERS_REGISTRY.list_components()


def register_tokenizer(name: str, clazz: Type[BaseTokenizer]) -> None:
    """Register a new tokenizer.

    Args:
        name (str): The name of the tokenizer.
        clazz (Type[BaseTokenizer]): The class of the tokenizer (i.e creator).
    """
    _TOKENIZERS_REGISTRY.register(name, clazz)
    logger.debug("Registered tokenizer '%s': '%s.%s'",
                 name, clazz.__module__, clazz.__name__)
