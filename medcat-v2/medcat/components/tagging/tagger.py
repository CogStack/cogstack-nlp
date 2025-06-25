from typing import Optional
import re

from medcat.config.config import Preprocessing
from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.tokenizing.tokens import MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import ComponentConfig


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
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]
            ) -> 'TagAndSkipTagger':
        return cls(cdb.config.preprocessing)
