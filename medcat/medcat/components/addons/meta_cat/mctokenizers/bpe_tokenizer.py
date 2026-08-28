import os
from typing import Optional, Union, overload
from tokenizers import ByteLevelBPETokenizer

from medcat.components.addons.meta_cat.mctokenizers.tokenizers import (
    TokenizerWrapperBase)


FAKE_TOKENIZER_PATH = "#\n/fake-path-not-exist#/"


class TokenizerWrapperBPE(TokenizerWrapperBase):
    """Wrapper around a huggingface tokenizer so that it works with the
    MetaCAT models.

    Args:
        tokenizers.ByteLevelBPETokenizer:
            A huggingface BBPE tokenizer.
    """
    name = 'bbpe'

    def __init__(self, hf_tokenizers: Optional[ByteLevelBPETokenizer] = None
                 ) -> None:
        super().__init__(hf_tokenizers)

        if self.hf_tokenizers is not None:
            # For whatever reason added tokens do not persist with
            # this tokenizer, what to do
            self.hf_tokenizers.add_tokens(['<PAD>'])

    @overload
    def __call__(self, text: str) -> dict: ...

    @overload
    def __call__(self, text: list[str]) -> list[dict]: ...

    def __call__(self, text: Union[str, list[str]]) -> Union[dict, list[dict]]:
        """Tokenize some text

        Args:
            text (Union[str, list[str]]):
                Text/texts to be tokenized.

        Returns:
            Union(dict, list[dict]):
                Dictionary/ies containing `offset_mapping`, `input_ids` and
                `tokens` corresponding to the input text/s.

        Raises:
            Exception: If the input is something other than text or a list
                of text.
        """
        self.hf_tokenizers = self.ensure_tokenizer()

        if isinstance(text, str):
            result = self.hf_tokenizers.encode(text)

            return {'offset_mapping': result.offsets,
                    'input_ids': result.ids,
                    'tokens': result.tokens,
                    }
        elif isinstance(text, list):
            results = self.hf_tokenizers.encode_batch(text)
            output = []
            for result in results:
                output.append({
                    'offset_mapping': result.offsets,
                    'input_ids': result.ids,
                    'tokens': result.tokens,
                })

            return output
        else:
            raise Exception(
                "Unsupported input type, supported: text/list, but got: "
                f"{type(text)}")

    def save(self, dir_path: str) -> None:
        self.hf_tokenizers = self.ensure_tokenizer()

        if self.hf_tokenizers is None:
            raise ValueError("The tokenizer is not loaded yet")

        self.hf_tokenizers.save_model(dir_path, prefix=self.name)

    @classmethod
    def load(cls, dir_path: str, model_variant: Optional[str] = '', **kwargs
             ) -> "TokenizerWrapperBPE":
        tokenizer = cls()
        vocab_file = os.path.join(dir_path, f'{tokenizer.name}-vocab.json')
        merges_file = os.path.join(dir_path, f'{tokenizer.name}-merges.txt')
        tokenizer.hf_tokenizers = ByteLevelBPETokenizer.from_file(
            vocab_filename=vocab_file, merges_filename=merges_file, **kwargs)
        # For whatever reason added tokens do not persist with this tokenizer,
        # so we added it at each load
        tokenizer.hf_tokenizers.add_tokens(['<PAD>'])
        return tokenizer

    @classmethod
    def create_new(cls):
        tokenizer = ByteLevelBPETokenizer()
        return cls(tokenizer)

    def get_size(self) -> int:
        self.hf_tokenizers = self.ensure_tokenizer()
        return self.hf_tokenizers.get_vocab_size()

    def token_to_id(self, token: str) -> Union[int, list[int]]:
        self.hf_tokenizers = self.ensure_tokenizer()
        return self.hf_tokenizers.token_to_id(token)

    def get_pad_id(self) -> Union[int, list[int]]:
        pad = self.token_to_id('<PAD>')
        if pad is None:
            raise Exception(
                "No <PAD> token in the vocabulary of the tokenizer, "
                "please add it")
        return pad
