from typing import Optional
import os
import json
import logging

import torch

from medcat2.components.addons.meta_cat.meta_cat import MetaCAT, MetaCATAddon
from medcat2.components.addons.meta_cat.mctokenizers.tokenizers import (
    TokenizerWrapperBase, load_tokenizer)
from medcat2.config.config_meta_cat import ConfigMetaCAT
from medcat2.tokenizing.tokenizers import BaseTokenizer


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


def _fix_old_style_cnf(data: dict,
                       remove: set[str] = {"py/object", "__fields_set__",
                                           "__private_attribute_values__"},
                       take_from: str = "py/state.__dict__"):
    all_keys = set(sub_key for key in data for sub_key in
                   (data[key] if isinstance(data[key], dict) else [key]))
    # add 1st level keys
    all_keys.update(data.keys())
    # is old if py/object and py/state somewhere in keys
    if not set(('py/object', 'py/state')) <= all_keys:
        return data
    for to_rm in remove:
        if to_rm in data:
            del data[to_rm]
    # get the data from internal data structure
    cdata = data
    cpath = take_from
    while "." in cpath:
        cur_key, cpath = cpath.split(".", 1)
        if cur_key not in cdata:
            break
        cdata = cdata.pop(cur_key)
    if cpath in cdata:
        cdata = cdata.pop(cpath)
    # do recursive fix and get from internal structure where applicable
    for k, v in cdata.items():
        if isinstance(v, dict):
            v = _fix_old_style_cnf(v)
        data[k] = v
    return data


def load_cnf(cnf_path: str) -> ConfigMetaCAT:
    with open(cnf_path) as f1:
        data = json.load(f1)
    data = _fix_old_style_cnf(data)
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
