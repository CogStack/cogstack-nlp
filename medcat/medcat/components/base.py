from typing import Protocol, runtime_checkable, Optional
from typing_extensions import Self
from enum import Enum

from pydantic import BaseModel

from medcat.tokenizing.tokens import MutableDocument
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import ComponentConfig


@runtime_checkable
class BaseComponent(Protocol):

    @property
    def full_name(self) -> Optional[str]:
        """Name with the component type (e.g ner, linking, meta)."""
        pass

    @property
    def name(self) -> str:
        """The name of the component."""
        pass

    def is_core(self) -> bool:
        """Whether the component is a core component or not.

        Returns:
            bool: Whether this is a core component.
        """
        pass

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        pass

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]) -> Self:
        """Create a new component or load one off disk if load path presented.

        This may raise an exception if the wrong type of config is provided.

        Args:
            cnf (ComponentConfig): The config relevant to this components.
            tokenizer (BaseTokenizer): The base tokenizer.
            cdb (CDB): The CDB.
            vocab (Vocab): The Vocab.
            model_load_path (Optional[str]): Model load path (if present).

        Returns:
            Self: The new components.
        """
        pass

class CollectionContract(BaseModel, frozen=True):
    """Contract for a collection field — what each item in the collection provides."""
    field: str                        # e.g. 'ner_ents'
    must_provide: frozenset[str]      # fields every item must have
    may_provide: frozenset[str] = frozenset()


class ComponentContract(BaseModel, frozen=True):
    needs: frozenset[str]
    must_provide: frozenset[str]
    may_provide: frozenset[str] = frozenset()
    collection_contracts: frozenset[CollectionContract] = frozenset()


class CoreComponentType(Enum):
    tagging = ComponentContract(
        needs=frozenset(),
        must_provide=frozenset(),
        # doesn't write for every token
        may_provide=frozenset({'token.is_punctuation', 'token.to_skip'}),
        collection_contracts=frozenset(),
    )
    token_normalizing = ComponentContract(
        needs=frozenset(),
        # should write for every token
        must_provide=frozenset({'token.norm'}),
        may_provide=frozenset(),
        collection_contracts=frozenset(),
    )
    ner = ComponentContract(
        needs=frozenset({'token.to_skip'}),
        must_provide=frozenset({'doc.ner_ents'}),   # the list must exist
        may_provide=frozenset(),
        collection_contracts=frozenset({
            CollectionContract(
                field='doc.ner_ents',
                must_provide=frozenset({'detected_name'}),
            )
        }),
    )
    linking = ComponentContract(
        needs=frozenset({'doc.ner_ents'}),
        # must write, but may be empty list
        must_provide=frozenset({'doc.linked_ents'}),
        may_provide=frozenset({}),
        collection_contracts=frozenset({
            CollectionContract(
                field='doc.linked_ents',
                must_provide=frozenset({'cui', 'context_similarity'}),
            ),
        }),
    )
