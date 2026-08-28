import logging
import os
from typing import cast

from transformers import BertConfig

from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.components.addons.relation_extraction.config import (
    RelExtrBaseConfig)

logger = logging.getLogger(__name__)


class RelExtrBertConfig(RelExtrBaseConfig):
    """ Class for BertConfig
    """

    name = 'bert-config'
    pretrained_model_name_or_path = "bert-base-uncased"
    hf_model_config: BertConfig

    @classmethod
    def load(cls, pretrained_model_name_or_path: str,
             relcat_config: ConfigRelCAT, **kwargs
             ) -> "RelExtrBertConfig":
        model_config = cls(pretrained_model_name_or_path, **kwargs)

        if pretrained_model_name_or_path and os.path.exists(
                pretrained_model_name_or_path):
            model_config.hf_model_config = cast(
                BertConfig, BertConfig.from_json_file(
                    pretrained_model_name_or_path))
            logger.info("Loaded config from file: %s",
                        pretrained_model_name_or_path)
        else:
            pretrained_name = relcat_config.general.model_name = (
                cls.pretrained_model_name_or_path)
            model_config.hf_model_config = cast(
                BertConfig, BertConfig.from_pretrained(
                    pretrained_model_name_or_path=pretrained_name, **kwargs))
            logger.info("Loaded config from pretrained: %s", pretrained_name)

        return model_config
