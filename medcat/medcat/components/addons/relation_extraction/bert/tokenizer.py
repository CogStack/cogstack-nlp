import os
import logging

from transformers.models.bert.tokenization_bert_fast import BertTokenizerFast

from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.components.addons.relation_extraction.tokenizer import (
    BaseTokenizerWrapper)

logger = logging.getLogger(__name__)


class TokenizerWrapperBERT(BaseTokenizerWrapper):

    name = "tokenizer_wrapper_bert_rel"

    ''' Wrapper around a huggingface BERT tokenizer so that it works with the
    RelCAT models.

    Args:
        hf_tokenizers (
        `transformers.models.bert.tokenization_bert_fast.PreTrainedTokenizerFast`):
            A huggingface Fast BERT.
    '''
    name = 'bert-tokenizer'
    pretrained_model_name_or_path = "bert-base-uncased"

    @classmethod
    def load(cls, tokenizer_path: str, relcat_config: ConfigRelCAT, **kwargs
             ) -> "TokenizerWrapperBERT":
        tokenizer = cls()
        path = os.path.join(tokenizer_path, cls.name)

        if tokenizer_path:
            tokenizer.hf_tokenizers = BertTokenizerFast.from_pretrained(
                pretrained_model_name_or_path=path, **kwargs)
        else:
            relcat_config.general.model_name = (
                cls.pretrained_model_name_or_path)
            tokenizer.hf_tokenizers = BertTokenizerFast.from_pretrained(
                pretrained_model_name_or_path=relcat_config.general.model_name)
        return tokenizer
