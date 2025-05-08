from typing import Any, Optional

from medcat2.components.types import CoreComponentType, AbstractCoreComponent
from medcat2.tokenizing.tokens import MutableDocument
from medcat2.tokenizing.tokenizers import BaseTokenizer
from medcat2.cdb.cdb import CDB
from medcat2.vocab import Vocab


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
