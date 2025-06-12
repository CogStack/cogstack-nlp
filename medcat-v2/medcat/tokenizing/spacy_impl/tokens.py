from typing import Iterator, Union, Optional, overload, cast, Any
import logging

from spacy.tokens import Token as SpacyToken
from spacy.tokens import Span as SpacySpan
from spacy.tokens import Doc as SpacyDoc

from medcat.tokenizing.tokens import (BaseToken, MutableToken,
                                      BaseEntity, MutableEntity,
                                      BaseDocument,
                                      UnregisteredDataPathException)


logger = logging.getLogger(__name__)


# set extensions as soon as this is loaded
SpacyToken.set_extension('norm', default=None, force=True)
SpacyToken.set_extension('skip', default=False, force=True)
SpacyToken.set_extension('is_punctuation', default=False, force=True)


class Token:

    def __init__(self, delegate: SpacyToken) -> None:
        self._delegate = delegate

    @property
    def is_punctuation(self) -> bool:
        return self._delegate._.is_punctuation

    @is_punctuation.setter
    def is_punctuation(self, new_val: bool) -> None:
        self._delegate._.is_punctuation = new_val

    @property
    def to_skip(self) -> bool:
        return self._delegate._.skip

    @to_skip.setter
    def to_skip(self, new_val: bool) -> None:
        self._delegate._.skip = new_val

    @property
    def norm(self) -> str:
        return self._delegate._.norm or ''

    @norm.setter
    def norm(self, new_val: str) -> None:
        self._delegate._.norm = new_val

    @property
    def base(self) -> BaseToken:
        return cast(BaseToken, self)

    @property
    def text(self) -> str:
        return self._delegate.text

    @property
    def text_versions(self) -> list[str]:
        return [self.norm, self.lower]

    @property
    def lower(self) -> str:
        return self._delegate.lower_

    @property
    def is_stop(self) -> bool:
        return self._delegate.is_stop

    @property
    def is_digit(self) -> bool:
        return self._delegate.is_digit

    @property
    def is_upper(self) -> bool:
        return self._delegate.is_upper

    @property
    def tag(self) -> Optional[str]:
        return self._delegate.tag_

    @property
    def lemma(self) -> str:
        return self._delegate.lemma_

    @property
    def text_with_ws(self) -> str:
        return self._delegate.text_with_ws

    @property
    def char_index(self) -> int:
        return self._delegate.idx

    @property
    def index(self) -> int:
        return self._delegate.i

    def __str__(self):
        return "M2W[T]:" + str(self._delegate)

    def __repr__(self):
        return repr(str(self))

    def __hash__(self) -> int:
        return hash(self._delegate)

    def __eq__(self, value) -> bool:
        if not isinstance(value, Token):
            return False
        return self._delegate == value._delegate


class Entity:
    _addon_extension_paths: set[str] = set()

    def __init__(self, delegate: SpacySpan) -> None:
        self._delegate = delegate
        # defaults
        self.link_candidates: list[str] = []
        self.context_similarity: float = 0.0
        self.confidence: float = 0.0
        self.cui = ''
        self.id = -1  # TODO - what's the default?
        self.detected_name = ''

    @property
    def base(self) -> BaseEntity:
        return cast(BaseEntity, self)

    def set_addon_data(self, path: str, val: Any) -> None:
        if not self._delegate.has_extension(path):
            raise UnregisteredDataPathException(self.__class__, path)
        return setattr(self._delegate._, path, val)

    def has_addon_data(self, path: str) -> bool:
        return bool(self.get_addon_data(path))

    def get_addon_data(self, path: str) -> Any:
        if not self._delegate.has_extension(path):
            raise UnregisteredDataPathException(self.__class__, path)
        return getattr(self._delegate._, path)

    def get_available_addon_paths(self) -> list[str]:
        return [path for path in self._addon_extension_paths
                if self.has_addon_data(path)]

    @classmethod
    def register_addon_path(cls, path: str, def_val: Any = None,
                            force: bool = True) -> None:
        SpacySpan.set_extension(path, default=def_val, force=force)
        cls._addon_extension_paths.add(path)
        # 'id', 'cui', 'id', 'cui', 'id', 'cui', 'id', 'cui', 'id', 'cui'

    @property
    def text(self) -> str:
        return self._delegate.text

    @property
    def label(self) -> int:
        return self._delegate.label

    @property
    def start_index(self) -> int:
        return self._delegate[0].i

    @property
    def end_index(self) -> int:
        return self._delegate[-1].i

    @property
    def start_char_index(self) -> int:
        return self._delegate.start_char

    @property
    def end_char_index(self) -> int:
        return self._delegate.end_char

    def __iter__(self) -> Iterator[MutableToken]:
        for tkn in self._delegate:
            yield Token(tkn)

    def __len__(self) -> int:
        return len(self._delegate)

    def __str__(self):
        return "M2W[T]:" + str(self._delegate)

    def __repr__(self):
        return repr(str(self))


class Document:
    _addon_extension_paths: set[str] = set()

    def __init__(self, delegate: SpacyDoc) -> None:
        self._delegate = delegate
        self.ner_ents: list[MutableEntity] = []
        self.linked_ents: list[MutableEntity] = []

    @property
    def base(self) -> BaseDocument:
        return cast(BaseDocument, self)

    @property
    def text(self) -> str:
        return self._delegate.text

    @overload
    def __getitem__(self, index: int) -> MutableToken:
        pass

    @overload
    def __getitem__(self, index: slice) -> MutableEntity:
        pass

    def __getitem__(self, index: Union[int, slice]
                    ) -> Union[MutableToken, MutableEntity]:
        delegated = self._delegate[index]
        if isinstance(delegated, SpacyToken):
            return Token(delegated)
        return Entity(delegated)

    def __len__(self) -> int:
        return len(self._delegate)

    def get_tokens(self, start_index: int, end_index: int
                   ) -> list[MutableToken]:
        tkns = []
        for tkn in self:
            if (tkn.base.char_index >= start_index and
                    tkn.base.char_index <= end_index):
                tkns.append(tkn)
        return tkns

    def set_addon_data(self, path: str, val: Any) -> None:
        if not self._delegate.has_extension(path):
            raise UnregisteredDataPathException(self.__class__, path)
        setattr(self._delegate._, path, val)

    def has_addon_data(self, path: str) -> bool:
        return bool(self.get_addon_data(path))

    def get_addon_data(self, path: str) -> Any:
        if not self._delegate.has_extension(path):
            raise UnregisteredDataPathException(self.__class__, path)
        return getattr(self._delegate._, path)

    def get_available_addon_paths(self) -> list[str]:
        return [path for path in self._addon_extension_paths
                if self.has_addon_data(path)]

    @classmethod
    def register_addon_path(cls, path: str, def_val: Any = None,
                            force: bool = True) -> None:
        SpacyDoc.set_extension(path, default=def_val, force=force)
        cls._addon_extension_paths.add(path)

    def __iter__(self) -> Iterator[MutableToken]:
        for tkn in iter(self._delegate):
            yield Token(tkn)

    def isupper(self) -> bool:
        return self._delegate.text.isupper()

    def __str__(self):
        return "M2W[T]:" + str(self._delegate)

    def __repr__(self):
        return repr(str(self))
