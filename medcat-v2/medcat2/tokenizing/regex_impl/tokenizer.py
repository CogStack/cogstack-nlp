import re
from typing import cast, Optional, Iterator, overload, Union

from medcat2.tokenizing.tokens import (
    BaseToken, BaseEntity, BaseDocument,
    MutableDocument, MutableEntity, MutableToken)
from medcat2.tokenizing.tokenizers import BaseTokenizer
from medcat2.config import Config


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

    def should_include(self) -> bool:
        return (not self.to_skip and not self.is_stop and
                not self.is_digit and not self.is_punctuation)

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

    def __init__(self, text: str, tokens: Optional[list[MutableToken]] = None
                 ) -> None:
        self.text = text
        self._tokens = tokens or []
        self.all_ents: list[MutableEntity] = []
        self.final_ents: list[MutableEntity] = []

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
        # print("GETTING", index, "out of", len(self._tokens),
        #       'ending', repr(self.text[-10:]))
        tokens = self._tokens[index]
        # if isinstance(index, slice) and index.stop > len(self._tokens):
        #     print("Looked beyond delegate length. Got:", tokens)
        if isinstance(tokens, Token):
            return tokens
        elif isinstance(index, slice):
            token_list = cast(list[MutableToken], tokens)
            return _entity_from_tokens(self, token_list,
                                       index.start, index.stop)
        else:
            raise ValueError(f"Unknown index: {index}")

    def get_tokens(self, start_index: int, end_index: int
                   ) -> Union[MutableEntity, list[MutableToken]]:
        for ent in self.all_ents:
            if (ent.base.start_index == start_index and
                    ent.base.end_index == end_index):
                return ent
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
        # print("\n\nTrying token #", token_start, "..", token_end,
        #       "out of", len(doc._tokens),
        #       "or", len(rtokens), "local tokens\n\n")
        if token_start >= len(doc._tokens):
            start_char = len(doc.text)
        else:
            start_char = doc._tokens[token_start].base.char_index
        end_char = start_char
        text = ''
    else:
        start_char = end_char = 0
        text = ''
    # print("Ent from", len(tokens), 'tokens', token_start, "..", token_end,
    #       'or', start_char, "..", end_char, "/", len(doc.text), ":",
    #       repr(doc.text[start_char:end_char]
    #            if start_char < len(doc.text) else ''))
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


def set_def_args_kwargs(config: Config) -> None:
    config.general.nlp.init_args = []
    config.general.nlp.init_kwargs = {}
