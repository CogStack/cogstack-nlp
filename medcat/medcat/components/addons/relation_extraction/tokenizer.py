import os
from typing import Optional
from transformers.models.bert.tokenization_bert_fast import BertTokenizerFast
from transformers import PreTrainedTokenizerFast
import logging

from medcat.config.config_rel_cat import ConfigRelCAT


logger = logging.getLogger(__name__)


class BaseTokenizerWrapper(PreTrainedTokenizerFast):

    name = "base_tokenizer_wrapper_rel"

    def __init__(self, hf_tokenizers=None,
                 max_seq_length: Optional[int] = None,
                 add_special_tokens: Optional[bool] = False):
        self.hf_tokenizers = hf_tokenizers
        self.max_seq_length = max_seq_length
        self._add_special_tokens = add_special_tokens

    def get_size(self):
        return len(self.hf_tokenizers.vocab)

    def token_to_id(self, token):
        return self.hf_tokenizers.convert_tokens_to_ids(token)

    def get_pad_id(self):
        return self.hf_tokenizers.pad_token_id

    def __call__(self, text, truncation: Optional[bool] = True):
        if isinstance(text, str):
            result = self.hf_tokenizers.encode_plus(
                text, return_offsets_mapping=True, return_length=True,
                return_token_type_ids=True, return_attention_mask=True,
                add_special_tokens=self._add_special_tokens,
                max_length=self.max_seq_length, padding="longest",
                truncation=truncation)

            return {'offset_mapping': result['offset_mapping'],
                    'input_ids': result['input_ids'],
                    'tokens':  self.hf_tokenizers.convert_ids_to_tokens(
                        result['input_ids']),
                    'token_type_ids': result['token_type_ids'],
                    'attention_mask': result['attention_mask'],
                    'length': result['length']
                    }
        elif isinstance(text, list):
            results = self.hf_tokenizers._batch_encode_plus(
                text, return_offsets_mapping=True, return_length=True,
                return_token_type_ids=True,
                add_special_tokens=self._add_special_tokens,
                max_length=self.max_seq_length, truncation=truncation)
            output = []
            for ind in range(len(results['input_ids'])):
                output.append({
                    'offset_mapping': results['offset_mapping'][ind],
                    'input_ids': results['input_ids'][ind],
                    'tokens':  self.hf_tokenizers.convert_ids_to_tokens(
                        results['input_ids'][ind]),
                    'token_type_ids': results['token_type_ids'][ind],
                    'attention_mask': results['attention_mask'][ind],
                    'length': result['length']
                })
            return output
        else:
            raise Exception(
                "Unsupported input type, supported: text/list, but got: "
                f"{type(text)}")

    def save(self, dir_path: str):
        path = os.path.join(dir_path, self.name)
        self.hf_tokenizers.save_pretrained(path)

    @classmethod
    def load(cls, tokenizer_path: str, relcat_config: ConfigRelCAT, **kwargs
             ) -> "BaseTokenizerWrapper":

        tokenizer = BaseTokenizerWrapper()

        cnf_gen = relcat_config.general

        if os.path.exists(tokenizer_path):
            if "modern-bert" in cnf_gen.tokenizer_name:
                from medcat.components.addons.relation_extraction.modernbert.tokenizer import TokenizerWrapperModernBERT  # noqa
                tokenizer = TokenizerWrapperModernBERT.load(
                    tokenizer_path, relcat_config=relcat_config, **kwargs)
            elif "bert" in cnf_gen.tokenizer_name:
                from medcat.components.addons.relation_extraction.bert.tokenizer import TokenizerWrapperBERT  # noqa
                tokenizer = TokenizerWrapperBERT.load(
                    tokenizer_path, relcat_config=relcat_config, **kwargs)
            elif "llama" in cnf_gen.tokenizer_name:
                from medcat.components.addons.relation_extraction.llama.tokenizer import TokenizerWrapperLlama  # noqa
                tokenizer = TokenizerWrapperLlama.load(
                    tokenizer_path, relcat_config=relcat_config, **kwargs)
            logger.info("Tokenizer loaded %s from: %s",
                        str(tokenizer.__class__.__name__), tokenizer_path)
        elif cnf_gen.model_name:
            logger.info("Attempted to load Tokenizer from path: %s,"
                        " but it doesn't exist, loading default toknizer from "
                        "model_name relcat_config.general.model_name: %s",
                        tokenizer_path, cnf_gen.model_name)
            from medcat.components.addons.relation_extraction.bert.tokenizer import TokenizerWrapperBERT  # noqa
            from medcat.components.addons.relation_extraction.ml_utils import create_tokenizer_pretrain  # noqa
            logger.info(
                "Addeding special tokens to tokenizer: %s %s",
                str(cnf_gen.tokenizer_relation_annotation_special_tokens_tags),
                str(cnf_gen.tokenizer_other_special_tokens))
            tokenizer = TokenizerWrapperBERT(
                BertTokenizerFast.from_pretrained(cnf_gen.model_name),
                add_special_tokens=True)
            tokenizer = create_tokenizer_pretrain(
                tokenizer, relcat_config=relcat_config)
        else:
            logger.info(
                "Attempted to load Tokenizer from path: %s, "
                "but it doesn't exist, loading default toknizer from "
                "model_name config.general.model_name:bert-base-uncased",
                tokenizer_path)
            from medcat.components.addons.relation_extraction.bert.tokenizer import TokenizerWrapperBERT  # noqa
            tokenizer = TokenizerWrapperBERT(
                BertTokenizerFast.from_pretrained(cnf_gen.model_name),
                max_seq_length=cnf_gen.max_seq_length,
                add_special_tokens=cnf_gen.tokenizer_special_tokens)
        return tokenizer
