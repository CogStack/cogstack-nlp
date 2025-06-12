from typing import Optional
import os
import json
import logging

import torch

from medcat.components.addons.meta_cat import MetaCAT, MetaCATAddon
from medcat.components.addons.meta_cat.mctokenizers.tokenizers import (
    TokenizerWrapperBase, load_tokenizer)
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.tokenizing.tokenizers import BaseTokenizer

from medcat.utils.legacy.helpers import fix_old_style_cnf


logger = logging.getLogger(__name__)


def _load_legacy(config: ConfigMetaCAT, save_dir_path: str) -> MetaCAT:
    tokenizer: Optional[TokenizerWrapperBase] = None
    # Load tokenizer
    tokenizer = load_tokenizer(config, save_dir_path)

    # Create meta_cat
    meta_cat = MetaCAT(tokenizer=tokenizer, embeddings=None, config=config)

    # Load the model
    model_save_path = os.path.join(save_dir_path, 'model.dat')
    device = torch.device(config.general.device)
    if not torch.cuda.is_available() and device.type == 'cuda':
        logger.warning(
            'Loading a MetaCAT model without GPU availability, '
            'stored config used GPU')
        config.general.device = 'cpu'
        device = torch.device('cpu')
    meta_cat.model.load_state_dict(
        torch.load(model_save_path, map_location=device))
    return meta_cat


def load_cnf(cnf_path: str) -> ConfigMetaCAT:
    with open(cnf_path) as f1:
        data = json.load(f1)
    data = fix_old_style_cnf(data)
    cnf = ConfigMetaCAT.model_validate(data)
    cnf.comp_name = MetaCATAddon.addon_type
    return cnf


def get_meta_cat_from_old(old_path: str, tokenizer: BaseTokenizer
                          ) -> MetaCATAddon:
    """Convert a v1 MetaCAT folder to a v2 MetaCAT.

    Args:
        old_path (str): The v1 MetaCAT file path.
        tokenizer (BaseTokenizer): The tokenizer.

    Returns:
        MetaCATAddon: The v2 MetaCAT.
    """
    cnf = load_cnf(os.path.join(old_path, "config.json"))
    mc = _load_legacy(cnf, old_path)
    addon = MetaCATAddon.create_new(cnf, tokenizer)
    addon._mc = mc
    return addon
