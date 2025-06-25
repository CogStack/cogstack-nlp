import re
from typing import cast, Optional, Iterator, overload, Union, Any, Type
from collections import defaultdict

from medcat.tokenizing.tokens import (
    BaseToken, BaseEntity, BaseDocument,
    MutableDocument, MutableEntity, MutableToken,
    UnregisteredDataPathException)
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.config import Config


class Token:

    def __init__(self, document: 'Document',
                 text: str, _text_with_ws: str,
                 start_index: int, token_index: int,
                 is_punct: bool, to_skip: bool) -> None:
        self._doc = document
        self._text = text
        self._text_with_ws = _text_with_ws
        self._start_index = start_index
        self._token_index = token_index
        self._is_punct = is_punct
        self._to_skip = to_skip
        # defaults
        if self.norm is None:
            # force spacy to init ''
            self.norm = ''

    @property
    def is_punctuation(self) -> bool:
        return self._is_punct

    @is_punctuation.setter
    def is_punctuation(self, new_val: bool) -> None:
        self._is_punct = new_val

    @property
    def to_skip(self) -> bool:
        return self._to_skip

    @to_skip.setter
    def to_skip(self, new_val: bool) -> None:
        self._to_skip = new_val

    @property
    def norm(self) -> str:
        return self.lower

    @norm.setter
    def norm(self, new_val: str) -> None:
        pass  # nothing

    @property
    def base(self) -> BaseToken:
        return cast(BaseToken, self)

    @property
    def text(self) -> str:
        return self._text

    @property
    def text_versions(self) -> list[str]:
        return [self.norm, self.lower]

    @property
    def lower(self) -> str:
        return self._text.lower()

    @property
    def is_stop(self) -> bool:
        return False

    @property
    def is_digit(self) -> bool:
        return self._text.isdigit()

    @property
    def is_upper(self) -> bool:
        return self._text.isupper()

    @property
    def tag(self) -> Optional[str]:
        return None

    @property
    def lemma(self) -> str:
        return self.norm

    @property
    def text_with_ws(self) -> str:
        return self._text_with_ws

    @property
    def char_index(self) -> int:
        return self._start_index

    @property
    def index(self) -> int:
        return self._token_index

    def __str__(self):
        return "RE[T]:" + self.text

    def __repr__(self):
        return repr(str(self))

    def __hash__(self) -> int:
        return hash(self.text)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Token):
            return False
        return (
            self._doc is other._doc and
            self.text == other.text and
            self.index == other.index)


class Entity:
    ENTITY_INFO_PREFIX = "Entity:"
    _addon_extension_paths: set[str] = set()

    def __init__(self, document: 'Document',
                 text: str, start_index: int, end_index: int,
                 start_char_index: int, end_char_index: int) -> None:
        self._doc = document
        self._text = text
        self._start_index = start_index
        self._end_index = end_index
        self._start_char_index = start_char_index
        self._end_char_index = end_char_index
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

    @property
    def text(self) -> str:
        return self._text

    @property
    def label(self) -> int:
        # NOTE: may not need this?
        return -1

    @property
    def start_index(self) -> int:
        return self._start_index

    @property
    def end_index(self) -> int:
        return self._end_index

    @property
    def start_char_index(self) -> int:
        return self._start_char_index

    @property
    def end_char_index(self) -> int:
        return self._end_char_index

    def set_addon_data(self, path: str, val: Any) -> None:
        # NOTE: doc.get_addon_data will raise if not registered
        doc_dict = self._doc.get_addon_data(f"{self.ENTITY_INFO_PREFIX}{path}")
        doc_dict[(self.start_index, self.end_index)] = val

    def has_addon_data(self, path: str) -> bool:
        return bool(self.get_addon_data(path))

    def get_addon_data(self, path: str) -> Any:
        # NOTE: doc.get_addon_data will raise if not registered
        doc_dict = self._doc.get_addon_data(f"{self.ENTITY_INFO_PREFIX}{path}")
        return doc_dict[(self.start_index, self.end_index)]

    def get_available_addon_paths(self) -> list[str]:
        return [path for path in self._addon_extension_paths
                if self.get_addon_data(path)]

    @classmethod
    def register_addon_path(cls, path: str, def_val: Any = None,
                            force: bool = True) -> None:
        # NOTE: registering for document since that should be constant
        # whereas the entities may be created and recreated
        # it'll map the entity start and end index to the value
        def_val_doc: dict = defaultdict(lambda: def_val)
        Document.register_addon_path(
            f"{cls.ENTITY_INFO_PREFIX}{path}", def_val=def_val_doc,
            force=force)
        cls._addon_extension_paths.add(path)

    def __iter__(self) -> Iterator[MutableToken]:
        for tkn in self._doc._tokens[self.start_index: self.end_index]:
            yield tkn

    def __len__(self) -> int:
        # in terms of tokens
        if self.end_index == self.start_index:
            # distinguish between no tokens and 1 token
            # if there's no tokens, the start and end character matches
            return int(self.end_char_index > self.start_char_index)
        return self.end_index - self.start_index

    def __str__(self):
        return "RE[E]:" + self.text

    def __repr__(self):
        return repr(str(self))


class Document:
    _addon_extension_paths: set[str] = set()

    def __init__(self, text: str, tokens: Optional[list[MutableToken]] = None
                 ) -> None:
        self.text = text
        self._tokens = tokens or []
        self.ner_ents: list[MutableEntity] = []
        self.linked_ents: list[MutableEntity] = []

    @property
    def base(self) -> BaseDocument:
        return cast(BaseDocument, self)

    @overload
    def __getitem__(self, index: int) -> MutableToken:
        pass

    @overload
    def __getitem__(self, index: slice) -> MutableEntity:
        pass

    def __getitem__(self, index: Union[int, slice]
                    ) -> Union[MutableToken, MutableEntity]:
        tokens = self._tokens[index]
        if isinstance(tokens, Token):
            return tokens
        elif isinstance(index, slice):
            token_list = cast(list[MutableToken], tokens)
            return _entity_from_tokens(self, token_list,
                                       index.start, index.stop)
        else:
            raise ValueError(f"Unknown index: {index}")

    def __len__(self) -> int:
        return len(self._tokens)

    def get_tokens(self, start_index: int, end_index: int
                   ) -> list[MutableToken]:
        tkns = []
        for tkn in self:
            if (tkn.base.char_index >= start_index and
                    tkn.base.char_index <= end_index):
                tkns.append(tkn)
        return tkns

    def __iter__(self) -> Iterator[MutableToken]:
        yield from self._tokens

    def isupper(self) -> bool:
        return self.text.isupper()

    def set_addon_data(self, path: str, val: Any) -> None:
        if not hasattr(self.__class__, path):
            raise UnregisteredDataPathException(self.__class__, path)
        setattr(self, path, val)

    def has_addon_data(self, path: str) -> bool:
        return bool(self.get_addon_data(path))

    def get_addon_data(self, path: str) -> Any:
        if not hasattr(self.__class__, path):
            raise UnregisteredDataPathException(self.__class__, path)
        return getattr(self, path)

    def get_available_addon_paths(self) -> list[str]:
        return [path for path in self._addon_extension_paths
                if self.get_addon_data(path)]

    @classmethod
    def register_addon_path(cls, path: str, def_val: Any = None,
                            force: bool = True) -> None:
        setattr(cls, path, def_val)
        cls._addon_extension_paths.add(path)

    def __str__(self):
        return "RE[D]:" + self.text

    def __repr__(self):
        return repr(str(self))


def _entity_from_tokens(doc: Document, tokens: list[MutableToken],
                        token_start: int, token_end: int) -> Entity:
    if any(not isinstance(tkn, Token) for tkn in tokens):
        raise ValueError(
            f"Unknown tokens: {[type(tkn) for tkn in tokens]}")
    rtokens = cast(list[Token], tokens)
    text = doc.text
    if rtokens:
        start_char = rtokens[0].char_index
        # end index should need the length of the last token
        end_char = rtokens[-1].char_index + len(rtokens[-1].text)
        text = text[rtokens[0].char_index: end_char]
    elif doc._tokens:
        if token_start >= len(doc._tokens):
            start_char = len(doc.text)
        else:
            start_char = doc._tokens[token_start].base.char_index
        end_char = start_char
        text = ''
    else:
        start_char = end_char = 0
        text = ''
    return Entity(doc, text, token_start, token_end, start_char, end_char)


class RegexTokenizer(BaseTokenizer):
    REGEX = r'((\b\w+\b|\S+)\s?)'
    # group 1: text with whitespace (if present)
    # group 2: text with no whitespace

    def create_entity(self, doc: MutableDocument,
                      token_start_index: int, token_end_index: int,
                      label: str) -> MutableEntity:
        rdoc = cast(Document, doc)
        return self.entity_from_tokens(
            # rdoc._tokens[token_start_index: token_end_index + 1])
            rdoc._tokens[token_start_index: token_end_index])
        # spacy_doc = cast(Document, doc)._delegate
        # span = Span(spacy_doc, token_start_index, token_end_index, label)
        # return Entity(span)

    def entity_from_tokens(self, tokens: list[MutableToken]) -> MutableEntity:
        if not tokens:
            raise ValueError("Need at least one token for an entity")
        doc = cast(Token, tokens[0])._doc
        start_index = doc._tokens.index(tokens[0])
        end_index = doc._tokens.index(tokens[-1])
        return _entity_from_tokens(doc, tokens, start_index, end_index)

    def __call__(self, text: str) -> MutableDocument:
        tokens = re.finditer(self.REGEX, text)
        doc = Document(text)
        for tkn_index, match in enumerate(tokens):
            start_index = match.start()
            token_w_ws = match.group(1)
            token = match.group(2)
            doc._tokens.append(Token(doc, token, token_w_ws,
                                     start_index, tkn_index,
                                     False, False))
        return doc

    @classmethod
    def create_new_tokenizer(cls, config: Config) -> 'RegexTokenizer':
        return cls()

    def get_doc_class(self) -> Type[MutableDocument]:
        return Document

    def get_entity_class(self) -> Type[MutableEntity]:
        return Entity
