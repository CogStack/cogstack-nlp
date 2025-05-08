from typing import Any, Optional
import re

from medcat2.config.config import Preprocessing
from medcat2.components.types import CoreComponentType, AbstractCoreComponent
from medcat2.tokenizing.tokens import MutableDocument
from medcat2.tokenizing.tokenizers import BaseTokenizer
from medcat2.cdb import CDB
from medcat2.vocab import Vocab


class TagAndSkipTagger(AbstractCoreComponent):
    name = 'tag-and-skip-tagger'

    def __init__(self, preprocessing: Preprocessing) -> None:
        self.word_skipper = re.compile('^({})$'.format(
            '|'.join(preprocessing.words_to_skip)))
        # Very aggressive punct checker, input will be lowercased
        self.punct_checker = re.compile(r'[^a-z0-9]+')
        self.cnf_p = preprocessing

    def get_type(self) -> CoreComponentType:
        return CoreComponentType.tagging

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        for token in doc:
            if (self.punct_checker.match(token.base.lower) and
                    token.base.text not in self.cnf_p.keep_punct):
                # There can't be punct in a token if it also has text
                token.is_punctuation = True
                token.to_skip = True
            elif self.word_skipper.match(token.base.lower):
                # Skip if specific strings
                token.to_skip = True
            elif self.cnf_p.skip_stopwords and token.base.is_stop:
                token.to_skip = True

        return doc

    @classmethod
    def get_init_args(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                      model_load_path: Optional[str]) -> list[Any]:
        return [cdb.config.preprocessing]

    @classmethod
    def get_init_kwargs(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                        model_load_path: Optional[str]) -> dict[str, Any]:
        return {}
