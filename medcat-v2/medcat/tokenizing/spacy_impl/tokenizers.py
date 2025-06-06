from typing import Optional, Callable, cast, Any, Type
import re
import os

import spacy
from spacy.tokens import Span
from spacy.tokenizer import Tokenizer  # type: ignore
from spacy.language import Language

from medcat.tokenizing.tokens import (MutableDocument, MutableEntity,
                                      MutableToken)
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.tokenizing.spacy_impl.tokens import Document, Entity, Token
from medcat.tokenizing.spacy_impl.utils import ensure_spacy_model
from medcat.config import Config


def spacy_split_all(nlp: Language, use_diacritics: bool) -> Tokenizer:

    token_characters = r'[^A-Za-z0-9\@]'

    if use_diacritics:
        token_characters = r'[^A-Za-zÀ-ÖØ-öø-ÿ0-9\@]'

    infix_re = re.compile(token_characters)
    suffix_re = re.compile(token_characters + r'$')
    prefix_re = re.compile(r'^' + token_characters)
    return Tokenizer(nlp.vocab,
                     rules={},
                     token_match=None,
                     prefix_search=prefix_re.search,
                     suffix_search=suffix_re.search,
                     infix_finditer=infix_re.finditer
                     )


class SpacyTokenizer(BaseTokenizer):

    def __init__(self, spacy_model_name: str,
                 spacy_disabled_components: list[str],
                 use_diacritics: bool,
                 max_document_length: int,
                 tokenizer_getter: Callable[[Language, bool], Tokenizer
                                            ] = spacy_split_all,
                 stopwords: Optional[set[str]] = None,):
        ensure_spacy_model(spacy_model_name)
        if stopwords is not None:
            lang_str = os.path.basename(spacy_model_name).split('_', 1)[0]
            cls = spacy.util.get_lang_class(lang_str)
            cls.Defaults.stop_words = set(stopwords)
        self._nlp = spacy.load(spacy_model_name,
                               disable=spacy_disabled_components)
        self._nlp.tokenizer = tokenizer_getter(self._nlp, use_diacritics)
        self._nlp.max_length = max_document_length

    def create_entity(self, doc: MutableDocument,
                      token_start_index: int, token_end_index: int,
                      label: str) -> MutableEntity:
        spacy_doc = cast(Document, doc)._delegate
        span = Span(spacy_doc, token_start_index, token_end_index, label)
        return Entity(span)

    def entity_from_tokens(self, tokens: list[MutableToken]) -> MutableEntity:
        if not tokens:
            raise ValueError("Need at least one token for an entity")
        spacy_tokens = cast(list[Token], tokens)
        span = Span(spacy_tokens[0]._delegate.doc, spacy_tokens[0].index,
                    spacy_tokens[-1].index + 1)
        return Entity(span)

    def __call__(self, text: str) -> MutableDocument:
        return Document(self._nlp(text))

    @classmethod
    def get_init_args(cls, config: Config) -> list[Any]:
        nlp_cnf = config.general.nlp
        return [
            nlp_cnf.modelname,
            nlp_cnf.disabled_components,
            config.general.diacritics,
            config.preprocessing.max_document_length,
        ]

    @classmethod
    def get_init_kwargs(cls, config: Config) -> dict[str, Any]:
        return {"stopwords": config.preprocessing.stopwords}

    def get_doc_class(self) -> Type[MutableDocument]:
        return Document

    def get_entity_class(self) -> Type[MutableEntity]:
        return Entity
