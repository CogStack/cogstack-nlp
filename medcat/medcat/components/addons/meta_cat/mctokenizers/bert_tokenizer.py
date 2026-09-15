import logging
import os
from typing import Optional, Union, overload
from transformers.models.bert.tokenization_bert_fast import BertTokenizerFast

from medcat.components.addons.meta_cat.mctokenizers.tokenizers import (
    TokenizerWrapperBase)


FAKE_TOKENIZER_PATH = "#\n/fake-path-not-exist#/"


class TokenizerWrapperBERT(TokenizerWrapperBase):
    """Wrapper around a huggingface BERT tokenizer so that it works with the
    MetaCAT models.

    Args:
        transformers.models.bert.tokenization_bert_fast.BertTokenizerFast:
            A huggingface Fast BERT.
    """
    name = 'bert-tokenizer'

    def __init__(self, hf_tokenizers: Optional[BertTokenizerFast] = None
                 ) -> None:
        super().__init__(hf_tokenizers)

    @overload
    def __call__(self, text: str) -> dict: ...

    @overload
    def __call__(self, text: list[str]) -> list[dict]: ...

    def __call__(self, text: Union[str, list[str]]) -> Union[dict, list[dict]]:
        self.hf_tokenizers = self.ensure_tokenizer()
        if isinstance(text, str):
            result = self.hf_tokenizers.encode_plus(
                text, return_offsets_mapping=True, add_special_tokens=False)

            return {'offset_mapping': result['offset_mapping'],
                    'input_ids': result['input_ids'],
                    'tokens':  self.hf_tokenizers.convert_ids_to_tokens(
                        result['input_ids']),
                    }
        elif isinstance(text, list):
            results = self.hf_tokenizers._batch_encode_plus(
                text, return_offsets_mapping=True, add_special_tokens=False)
            output = []
            for ind in range(len(results['input_ids'])):
                output.append({
                    'offset_mapping': results['offset_mapping'][ind],
                    'input_ids': results['input_ids'][ind],
                    'tokens':  self.hf_tokenizers.convert_ids_to_tokens(
                        results['input_ids'][ind]),
                })
            return output
        else:
            raise Exception("Unsupported input type, supported: text/list, "
                            f"but got: {type(text)}")

    def save(self, dir_path: str) -> None:
        self.hf_tokenizers = self.ensure_tokenizer()
        path = os.path.join(dir_path, self.name)
        self.hf_tokenizers.save_pretrained(path)

    @classmethod
    def load(cls, dir_path: str, model_variant: Optional[str] = '', **kwargs
             ) -> "TokenizerWrapperBERT":
        tokenizer = cls()
        if dir_path != FAKE_TOKENIZER_PATH:
            path = os.path.join(dir_path, cls.name)
            tokenizer.hf_tokenizers = BertTokenizerFast.from_pretrained(
                path, **kwargs)
        else:
            # NOTE: the variable is a string since it's called from meta_cat.py
            #       using a string (in 2 places), but the super class requires
            #       the argument here to be `Optional`.
            variant = str(model_variant)
            logging.warning("Could not load tokenizer (no path provided). "
                            f"Loading from library for model variant: "
                            f"{variant}")
            tokenizer.hf_tokenizers = BertTokenizerFast.from_pretrained(
                variant)
        return tokenizer

    @classmethod
    def create_new(cls, model_variant: Optional[str]
                   ) -> 'TokenizerWrapperBERT':
        return cls.load(FAKE_TOKENIZER_PATH, model_variant)

    def get_size(self) -> int:
        self.hf_tokenizers = self.ensure_tokenizer()
        return len(self.hf_tokenizers.vocab)

    def token_to_id(self, token: str) -> Union[int, list[int]]:
        self.hf_tokenizers = self.ensure_tokenizer()
        return self.hf_tokenizers.convert_tokens_to_ids(token)

    def get_pad_id(self) -> Optional[int]:
        self.hf_tokenizers = self.ensure_tokenizer()
        return self.hf_tokenizers.pad_token_id
