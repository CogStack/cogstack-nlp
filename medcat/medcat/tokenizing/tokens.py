from typing import Protocol, Optional, Iterator, overload, Any, Type


class BaseToken(Protocol):
    """Base token protocol.

    This represents the static (unchangeable) parts of a token.
    """

    @property
    def text(self) -> str:
        """The text represented by this token."""
        pass

    @property
    def lower(self) -> str:
        """The lower case text representation."""
        pass

    @property
    def text_versions(self) -> list[str]:
        """The different versions of text (e.g normalised and lower)"""
        pass

    @property
    def is_upper(self) -> bool:
        """Whether the text is upper case."""
        pass

    @property
    def is_stop(self) -> bool:
        """Whether the token represents a stop token."""
        pass

    @property
    def char_index(self) -> int:
        """The character index of the start of this token"""
        pass

    @property
    def index(self) -> int:
        """The index (in terms of tokens) of this token in the document."""
        pass

    @property
    def text_with_ws(self) -> str:
        """The text with tailing whitespace (where applicable)."""
        pass

    @property
    def is_digit(self) -> bool:
        """Whether the token represents a digit."""


class MutableToken(Protocol):
    """The mutable part of a token.

    This protocol describes all the parts of a token that could be expected to
    change.
    """

    @property
    def base(self) -> BaseToken:
        """The base portion of the token."""
        pass

    @property
    def is_punctuation(self) -> bool:
        """Whether the token represents punctuation."""
        pass

    @is_punctuation.setter
    def is_punctuation(self, val: bool) -> None:
        """Whether the token represents punctuation."""
        pass

    @property
    def to_skip(self) -> bool:
        """Whether the token should be skipped."""
        pass

    @to_skip.setter
    def to_skip(self, new_val: bool) -> None:
        """Whether the token should be skipped."""
        pass

    @property
    def lemma(self) -> str:
        """The lemmatised version of the text."""
        pass

    @property
    def tag(self) -> Optional[str]:
        """Optional tag (e.g) for normalization."""
        pass

    @property
    def norm(self) -> str:
        """The normalised text."""
        pass

    @norm.setter
    def norm(self, value: str) -> None:
        """The normalised text."""
        pass


class BaseEntity(Protocol):
    """Base entity protocol.

    This describes the static (unchangeable) parts of an entity or
    sequence of tokens.
    """

    @property
    def start_index(self) -> int:
        """The index of the first token in the entity."""
        pass

    @property
    def end_index(self) -> int:
        """The index of the last token in the entity."""
        pass

    @property
    def start_char_index(self) -> int:
        """The character index of the first token."""
        pass

    @property
    def end_char_index(self) -> int:
        """The character index of the last token."""
        pass

    @property
    def label(self) -> int:
        """The label of the entity (NOTE: seems unused)."""
        pass

    @property
    def text(self) -> str:
        """The text of the entire entity."""
        pass

    def __iter__(self) -> Iterator[BaseToken]:
        pass

    def __len__(self) -> int:
        pass


class MutableEntity(Protocol):
    """The mutable part of an entity.

    This represent the changeable part of an entnity. That is, parts
    that should be changed by the various components.
    """

    @property
    def base(self) -> BaseEntity:
        """The base / static entity part."""
        pass

    @property
    def detected_name(self) -> str:
        """The detected name (if any) for this entity.

        This should be set by the NER component.
        """
        pass

    @detected_name.setter
    def detected_name(self, name: str) -> None:
        """The detected name (if any) for this entity.

        This should be set by the NER component.
        """
        pass

    def set_addon_data(self, path: str, val: Any) -> None:
        """Used to add arbitrary data to the entity.

        This is generally used by addons to keep track of their data.

        NB! The path used needs to be registered using the
        `register_addon_path` class method.

        Args:
            path (str): The data ID / path.
            val (Any): The value to be added.
        """
        pass

    def has_addon_data(self, path: str) -> bool:
        """Checks whether the addon data for a specific path has been set.

        Args:
            path (str): The path to check.

        Returns:
            bool: Whether the addon data had been set.
        """
        pass

    def get_addon_data(self, path: str) -> Any:
        """Get data added to the entity.

        See `add_data` for details.

        Args:
            path (str): The data ID / path.

        Returns:
            Any: The stored value.
        """
        pass

    def get_available_addon_paths(self) -> list[str]:
        """Gets the available addon data paths for this entity.

        This will only include paths that have values set.

        Returns:
            list[str]: List of available addon data paths.
        """
        pass

    @property
    def link_candidates(self) -> list[str]:
        """The candidates for the detected name (if any) for this entity.

        This should be set by the NER component.
        """
        pass

    @link_candidates.setter
    def link_candidates(self, candidates: list[str]) -> None:
        """The candidates for the detected name (if any) for this entity.

        This should be set by the NER component.
        """
        pass

    @property
    def context_similarity(self) -> float:
        """The context similarity of the lnked entity.

        This should be set by the linker component.
        """
        pass

    @context_similarity.setter
    def context_similarity(self, val: float) -> None:
        """The context similarity of the lnked entity.

        This should be set by the linker component.
        """
        pass

    @property
    def confidence(self) -> float:
        """The confidence for the lnked entity.

        NOTE: This seems to be unused!
        """
        pass

    @confidence.setter
    def confidence(self, val: float) -> None:
        """The confidence for the lnked entity.

        NOTE: This seems to be unused!
        """
        pass

    @property
    def cui(self) -> str:
        """The CUI of the lnked entity.

        This should be set by the linker component.
        """
        pass

    @cui.setter
    def cui(self, value: str) -> None:
        """The CUI of the lnked entity.

        This should be set by the linker component.
        """
        pass

    @property
    def id(self) -> int:
        """The ID of the entity within the document.

        This counts all the entities recognised, not just ones that
        were successfully linked.

        This should be set by the NER.
        """
        pass

    @id.setter
    def id(self, value: int) -> None:
        """The ID of the entity within the document.

        This counts all the entities recognised, not just ones that
        were successfully linked.

        This should be set by the NER.
        """
        pass

    @classmethod
    def register_addon_path(cls, path: str, def_val: Any = None,
                            force: bool = True) -> None:
        """Register a custom/arbitrary data path.

        This can be used to store arbitrary data along with the entity for
        use in an addon (e.g MetaCAT).

        PS: If using this, it is important to use paths namespaced to the
        component you're using in order to avoid conflicts.

        Args:
            path (str): The path to be used. Should be prefixed by component
                name (e.g `meta_cat_id` for an ID tied to the `meta_cat` addon)
            def_val (Any): Default value. Defaults to `None`.
            force (bool): Whether to forcefully add the value.
                Defaults to True.
        """
        pass

    def __iter__(self) -> Iterator[MutableToken]:
        pass

    def __len__(self) -> int:
        pass


class BaseDocument(Protocol):
    """The base document protocol.

    Represents the unchangeable parts of the whole document.
    """

    @property
    def text(self) -> str:
        """The document raw text."""
        pass

    @overload
    def __getitem__(self, index: int) -> BaseToken:
        pass

    @overload
    def __getitem__(self, index: slice) -> BaseEntity:
        pass

    def __iter__(self) -> Iterator[BaseToken]:
        pass

    def isupper(self) -> bool:
        """Whether the entire document is upper case."""
        pass


class MutableDocument(Protocol):
    """The mutable parts of the document.

    Represents parts of the document that can / should be changed
    by the various components.
    """

    @property
    def base(self) -> BaseDocument:
        """The base document."""
        pass

    @property
    def linked_ents(self) -> list[MutableEntity]:
        """The linked entities associated with the document.

        This should be set by the linker.
        """
        pass

    @property
    def ner_ents(self) -> list[MutableEntity]:
        """All entities recognised by NER.

        This should be set by the NER component.
        """
        pass

    def __iter__(self) -> Iterator[MutableToken]:
        pass

    @overload
    def __getitem__(self, index: int) -> MutableToken:
        pass

    @overload
    def __getitem__(self, index: slice) -> MutableEntity:
        pass

    def __len__(self) -> int:
        pass

    def get_tokens(self, start_index: int, end_index: int
                   ) -> list[MutableToken]:
        """Get the tokens that span the specified character indices.

        Args:
            start_index (int): The starting character index.
            end_index (int): The ending character index.

        Returns:
            list[MutableToken]:
                The list of tokens.
        """
        pass

    def set_addon_data(self, path: str, val: Any) -> None:
        """Used to add arbitrary data to the entity.

        This is generally used by addons to keep track of their data.

        NB! The path used needs to be registered using the
        `register_addon_path` class method.

        Args:
            path (str): The data ID / path.
            val (Any): The value to be added.
        """
        pass

    def has_addon_data(self, path: str) -> bool:
        """Checks whether the addon data for a specific path has been set.

        Args:
            path (str): The path to check.

        Returns:
            bool: Whether the addon data had been set.
        """
        pass

    def get_addon_data(self, path: str) -> Any:
        """Get data added to the entity.

        See `add_data` for details.

        Args:
            path (str): The data ID / path.

        Returns:
            Any: The stored value.
        """
        pass

    def get_available_addon_paths(self) -> list[str]:
        """Gets the available addon data paths for this document.

        This will only include paths that have values set.

        Returns:
            list[str]: List of available addon data paths.
        """
        pass

    @classmethod
    def register_addon_path(cls, path: str, def_val: Any = None,
                            force: bool = True) -> None:
        """Register a custom/arbitrary data path.

        This can be used to store arbitrary data along with the entity for
        use in an addon (e.g MetaCAT).

        PS: If using this, it is important to use paths namespaced to the
        component you're using in order to avoid conflicts.

        Args:
            path (str): The path to be used. Should be prefixed by component
                name (e.g `meta_cat_id` for an ID tied to the `meta_cat` addon)
            def_val (Any): Default value. Defaults to `None`.
            force (bool): Whether to forcefully add the value.
                Defaults to True.
        """
        pass


class UnregisteredDataPathException(ValueError):

    def __init__(self, cls: Type, path: str):
        super().__init__(
            f"Unregistered path '{path}' for class: {cls}")
        self.cls = cls
        self.path = path
