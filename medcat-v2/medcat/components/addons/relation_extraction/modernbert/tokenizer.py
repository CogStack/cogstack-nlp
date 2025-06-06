import os
from transformers import PreTrainedTokenizerFast
import logging

from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.components.addons.relation_extraction.tokenizer import (
    BaseTokenizerWrapper)

logger = logging.getLogger(__name__)


class TokenizerWrapperModernBERT(BaseTokenizerWrapper):
    """Wrapper around a huggingface ModernBERT tokenizer so that it works
    with the RelCAT models.

    Args:
        hf_tokenizers (`transformers.PreTrainedTokenizerFast`):
            A huggingface Fast tokenizer.
    """
    name = "tokenizer_wrapper_modern_bert_rel"
    pretrained_model_name_or_path = "answerdotai/ModernBERT-base"

    @classmethod
    def load(cls, tokenizer_path: str, relcat_config: ConfigRelCAT, **kwargs
             ) -> "TokenizerWrapperModernBERT":
        tokenizer = cls()
        path = os.path.join(tokenizer_path, cls.name)

        if tokenizer_path:
            tokenizer.hf_tokenizers = PreTrainedTokenizerFast.from_pretrained(
                path, **kwargs)
        else:
            relcat_config.general.model_name = (
                cls.pretrained_model_name_or_path)
            tokenizer.hf_tokenizers = PreTrainedTokenizerFast.from_pretrained(
                path=relcat_config.general.model_name)
        return tokenizer
