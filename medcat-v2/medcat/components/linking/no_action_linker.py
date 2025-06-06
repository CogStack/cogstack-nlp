from typing import Any, Optional

from medcat.components.types import CoreComponentType, AbstractCoreComponent
from medcat.tokenizing.tokens import MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.cdb.cdb import CDB
from medcat.vocab import Vocab


class NoActionLinker(AbstractCoreComponent):
    name = 'no_action'

    def get_type(self):
        return CoreComponentType.linking

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        return doc

    @classmethod
    def get_init_args(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                      model_load_path: Optional[str]) -> list[Any]:
        return []

    @classmethod
    def get_init_kwargs(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                        model_load_path: Optional[str]) -> dict[str, Any]:
        return {}
