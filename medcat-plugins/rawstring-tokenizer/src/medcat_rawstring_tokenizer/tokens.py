from typing import Any, Iterator, Optional, Union, cast, overload
from bisect import bisect_right
from medcat.tokenizing.tokens import (BaseToken, MutableToken,
                                      BaseEntity, MutableEntity,
                                      BaseDocument,
                                      UnregisteredDataPathException)

import unicodedata
import re


# keep both hyphens and slashes within words
_WORD_RE = re.compile(r"[^\W_]+(?:[^\W_]+)*", re.UNICODE)
# _WORD_RE = re.compile(r"[^\W_]+(?:[-/][^\W_]+)*", re.UNICODE)


def _iter_word_spans(
    text: str, 
    base_char_index: int = 0
    ) -> Iterator[tuple[str, int, int]]:
    for match in _WORD_RE.finditer(text):
        yield (match.group(0), 
               base_char_index + match.start(), 
               base_char_index + match.end())

class Token:
    def __init__(self, 
                 text: str, 
                 index: int, 
                 char_index: int, 
                 end_char_index: int) -> None:
        # --- BaseToken fields ---
        self._text = text
        self._index = index
        self._char_index = char_index
        self._end_char_index = end_char_index
        # --- MutableToken fields ---
        self._norm: str = text.lower()
        self._to_skip: bool = False
        self._is_punctuation: bool = (
            text != "" and unicodedata.category(text[0]).startswith("P")
        )

    # --- BaseToken ---
    @property
    def text(self) -> str: return self._text
    @property
    def lower(self) -> str: return self._text.lower()
    @property
    def text_versions(self) -> list[str]: return [self._norm, self.lower]
    @property
    def is_upper(self) -> bool: return self._text.isupper()
    @property
    def is_stop(self) -> bool: return False  # handled by transformers
    @property
    def is_digit(self) -> bool: return self._text.isdigit()
    @property
    def char_index(self) -> int: return self._char_index
    @property
    def index(self) -> int: return self._index
    @property
    def end_char_index(self) -> int: return self._end_char_index
    @property
    def text_with_ws(self) -> str: return self._text

    # --- MutableToken ---
    @property
    def base(self) -> BaseToken: return cast(BaseToken, self)
    @property
    def is_punctuation(self) -> bool: return self._is_punctuation
    @is_punctuation.setter
    def is_punctuation(self, val: bool) -> None: self._is_punctuation = val
    @property
    def to_skip(self) -> bool: return self._to_skip
    @to_skip.setter
    def to_skip(self, val: bool) -> None: self._to_skip = val
    @property
    def lemma(self) -> str: return self._text  # no lemmatization, return text as lemma
    @property
    def tag(self) -> Optional[str]: return None
    @property
    def norm(self) -> str: return self._norm
    @norm.setter
    def norm(self, val: str) -> None: self._norm = val
    
class Entity:
    _addon_extension_paths: set[str] = set()

    def __init__(self, text: str, start_index: int, end_index: int,
                 start_char: int, end_char: int, label: str = "") -> None:
        # --- BaseEntity fields ---
        # Token span is [start_index, end_index]: end is exclusive.
        # Character span is [start_char, end_char]: end is exclusive.
        self._text = text
        self._start_index = start_index
        self._end_index = end_index
        self._start_char = start_char
        self._end_char = end_char
        self._label = label
        self._addon_data: dict[str, Any] = {}
        # --- MutableEntity fields ---
        self.cui: str = ''
        self.detected_name: str = label
        self.link_candidates: list[str] = []
        self.context_similarity: float = 0.0
        self.confidence: float = 0.0
        self.id: int = -1

    # --- BaseEntity ---
    @property
    def base(self) -> BaseEntity: return cast(BaseEntity, self)
    @property
    def text(self) -> str: return self._text
    @property
    def label(self) -> str: return self._label
    @property
    def start_index(self) -> int: return self._start_index
    # This requires -1 for compatibility
    @property
    def end_index(self) -> int: return self._end_index - 1 
    @property
    def start_char_index(self) -> int: return self._start_char
    @property
    def end_char_index(self) -> int: return self._end_char # exclusive end index

    def __iter__(self) -> Iterator[MutableToken]:
        for i, (text, char_index, end_char_index) in enumerate(
            _iter_word_spans(self._text, self._start_char)):
            yield Token(text, self._start_index + i, char_index, end_char_index)

    def __len__(self) -> int: return max(0, self._end_index - self._start_index)

    # --- addon data ---
    def set_addon_data(self, path: str, val: Any) -> None:
        if path not in self._addon_extension_paths:
            raise UnregisteredDataPathException(self.__class__, path)
        self._addon_data[path] = val

    def has_addon_data(self, path: str) -> bool:
        return bool(self._addon_data.get(path))

    def get_addon_data(self, path: str) -> Any:
        if path not in self._addon_extension_paths:
            raise UnregisteredDataPathException(self.__class__, path)
        return self._addon_data.get(path)

    def get_available_addon_paths(self) -> list[str]:
        return [p for p in self._addon_extension_paths if self.has_addon_data(p)]

    @classmethod
    def register_addon_path(cls, path: str, def_val: Any = None,
                            force: bool = True) -> None:
        cls._addon_extension_paths.add(path)


class Document:
    _addon_extension_paths: set[str] = set()

    def __init__(self, text: str) -> None:
        self._text = text
        self._addon_data: dict[str, Any] = {}
        self.ner_ents: list[MutableEntity] = []
        self.linked_ents: list[MutableEntity] = []
        self._char_indices: Optional[list[int]] = None
        self._tokens: list[Token] = [
            Token(token_text, token_index, char_index, end_char_index)
            for token_index, (token_text, char_index, end_char_index) in 
            enumerate(_iter_word_spans(text))
        ]

    @property
    def base(self) -> BaseDocument: return cast(BaseDocument, self)

    @property
    def text(self) -> str: return self._text

    @overload
    def __getitem__(self, index: int) -> MutableToken:
        pass

    @overload
    def __getitem__(self, index: slice) -> list[MutableToken]:
        pass

    def __getitem__(self, index: Union[int, slice]
                    ) -> Union[MutableToken, list[MutableToken]]:
        if isinstance(index, int):
            if index < 0:
                index += len(self._tokens)
            if index < 0 or index >= len(self._tokens):
                raise IndexError("Document index out of range")
            return self._tokens[index]

        start, stop, step = index.indices(len(self._tokens))
        if step != 1:
            raise ValueError("Token slices must use step=1")
        return self._tokens[start:stop]

    def __iter__(self) -> Iterator[MutableToken]:
        return iter(self._tokens)

    def __len__(self) -> int:
        return len(self._tokens)

    def isupper(self) -> bool:
        return self._text.isupper()
    
    def _ensure_char_indices(self) -> list[int]:
        if self._char_indices is None:
            self._char_indices = [tkn.char_index for tkn in self._tokens]
        return self._char_indices

    def get_tokens(self, start_index: int, end_index: int
                   ) -> list[MutableToken]:
        # Keep MedCAT compatibility (inclusive end index), then resolve to
        # full tokens by overlap so partial subword offsets map to words.
        span_start = max(0, start_index)
        span_end_exclusive = max(span_start, end_index) + 1

        token_char_indices = self._ensure_char_indices()
        lo = max(0, bisect_right(token_char_indices, span_start) - 1)
        hi = min(
            len(self._tokens), 
            bisect_right(token_char_indices, span_end_exclusive - 1) + 1
        )

        return [
            token for token in self._tokens[lo:hi]
            if token.end_char_index > span_start and 
            token.char_index < span_end_exclusive
        ]


    def set_addon_data(self, path: str, val: Any) -> None:
        if path not in self._addon_extension_paths:
            raise UnregisteredDataPathException(self.__class__, path)
        self._addon_data[path] = val

    def has_addon_data(self, path: str) -> bool:
        return bool(self._addon_data.get(path))

    def get_addon_data(self, path: str) -> Any:
        if path not in self._addon_extension_paths:
            raise UnregisteredDataPathException(self.__class__, path)
        return self._addon_data.get(path)

    def get_available_addon_paths(self) -> list[str]:
        return [p for p in self._addon_extension_paths if self.has_addon_data(p)]

    @classmethod
    def register_addon_path(cls, path: str, def_val: Any = None,
                            force: bool = True) -> None:
        cls._addon_extension_paths.add(path)