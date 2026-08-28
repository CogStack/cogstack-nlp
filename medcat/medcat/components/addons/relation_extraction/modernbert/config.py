import logging
import os
from typing import cast

from transformers.models.modernbert import ModernBertConfig

from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.components.addons.relation_extraction.config import (
    RelExtrBaseConfig)

logger = logging.getLogger(__name__)


class RelExtrModernBertConfig(RelExtrBaseConfig):
    """ Class for ModernBertConfig
    """

    name = 'modern-bert-config'
    pretrained_model_name_or_path = "answerdotai/ModernBERT-base"
    hf_model_config: ModernBertConfig

    @classmethod
    def load(cls, pretrained_model_name_or_path: str,
             relcat_config: ConfigRelCAT, **kwargs
             ) -> "RelExtrModernBertConfig":
        model_config = cls(
            pretrained_model_name_or_path=pretrained_model_name_or_path,
            **kwargs)

        if pretrained_model_name_or_path and os.path.exists(
                pretrained_model_name_or_path):
            model_config.hf_model_config = cast(
                ModernBertConfig, ModernBertConfig.from_json_file(
                    pretrained_model_name_or_path))
            logger.info("Loaded config from file: %s",
                        pretrained_model_name_or_path)
        else:
            pretrained_model = relcat_config.general.model_name = (
                cls.pretrained_model_name_or_path)
            model_config.hf_model_config = cast(
                ModernBertConfig, ModernBertConfig.from_pretrained(
                    pretrained_model_name_or_path=pretrained_model, **kwargs))
            logger.info("Loaded config from pretrained: %s", pretrained_model)

        return model_config
