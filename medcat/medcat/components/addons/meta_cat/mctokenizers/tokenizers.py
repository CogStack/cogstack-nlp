from abc import ABC, abstractmethod
from typing import Optional, Union, overload
from tokenizers import Tokenizer

from medcat.config.config_meta_cat import ConfigMetaCAT


FAKE_TOKENIZER_PATH = "#\n/fake-path-not-exist#/"


class TokenizerWrapperBase(ABC):

    name: str

    def __init__(self, hf_tokenizer: Optional[Tokenizer] = None) -> None:
        self.hf_tokenizers = hf_tokenizer

    @overload
    def __call__(self, text: str) -> dict: ...

    @overload
    def __call__(self, text: list[str]) -> list[dict]: ...

    @abstractmethod
    def __call__(self, text: Union[str, list[str]]
                 ) -> Union[dict, list[dict]]: ...

    @abstractmethod
    def save(self, dir_path: str) -> None: ...

    @classmethod
    @abstractmethod
    def load(cls, dir_path: str, model_variant: Optional[str] = '', **kwargs
             ) -> Tokenizer: ...

    @abstractmethod
    def get_size(self) -> int: ...

    @abstractmethod
    def token_to_id(self, token: str) -> Union[int, list[int]]: ...

    @abstractmethod
    def get_pad_id(self) -> Union[Optional[int], list[int]]: ...

    def ensure_tokenizer(self) -> Tokenizer:
        if self.hf_tokenizers is None:
            raise ValueError("The tokenizer is not loaded yet")
        return self.hf_tokenizers


def init_tokenizer(cnf: ConfigMetaCAT) -> Optional[TokenizerWrapperBase]:
    tokenizer: Optional[TokenizerWrapperBase] = None
    if cnf.general.tokenizer_name == 'bbpe':
        from medcat.components.addons.meta_cat.mctokenizers.bpe_tokenizer import (  # noqa
            TokenizerWrapperBPE)
        tokenizer = TokenizerWrapperBPE.create_new()
    elif cnf.general.tokenizer_name == 'bert-tokenizer':
        from medcat.components.addons.meta_cat.mctokenizers.bert_tokenizer import (  # noqa
            TokenizerWrapperBERT)
        tokenizer = TokenizerWrapperBERT.create_new(cnf.model.model_variant)
    return tokenizer


def load_tokenizer(config: ConfigMetaCAT, tokenizer_folder: str
                   ) -> Optional[TokenizerWrapperBase]:
    tokenizer: Optional[TokenizerWrapperBase] = None
    if config.general.tokenizer_name == 'bbpe':
        from medcat.components.addons.meta_cat.mctokenizers.bpe_tokenizer import (  # noqa
            TokenizerWrapperBPE)
        tokenizer = TokenizerWrapperBPE.load(tokenizer_folder)
    elif config.general.tokenizer_name == 'bert-tokenizer':
        from medcat.components.addons.meta_cat.mctokenizers.bert_tokenizer import (  # noqa
            TokenizerWrapperBERT)
        tokenizer = TokenizerWrapperBERT.load(
            tokenizer_folder, config.model.model_variant)
    return tokenizer
