from typing import Optional

from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.tokenizing.tokens import MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.cdb.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import ComponentConfig


class NoActionLinker(AbstractCoreComponent):
    name = 'no_action'

    def get_type(self):
        return CoreComponentType.linking

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        return doc

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]
            ) -> 'NoActionLinker':
        return cls()
