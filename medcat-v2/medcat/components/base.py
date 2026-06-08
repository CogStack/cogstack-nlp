from typing import Protocol, runtime_checkable, Optional
from typing_extensions import Self
from enum import Enum, auto

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


class CoreComponentType(Enum):
    tagging = auto()
    token_normalizing = auto()
    ner = auto()
    linking = auto()
