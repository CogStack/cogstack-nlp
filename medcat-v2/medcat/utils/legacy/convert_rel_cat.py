import os
import json
import logging

import torch

from medcat.cdb import CDB
from medcat.components.addons.relation_extraction.rel_cat import (
    RelCAT, RelCATAddon)
from medcat.components.addons.relation_extraction.base_component import (
    RelExtrBaseComponent)
from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.tokenizing.tokenizers import BaseTokenizer, create_tokenizer
from medcat.utils.legacy.helpers import fix_old_style_cnf


logger = logging.getLogger(__name__)


def _load_legacy(cdb: CDB, base_tokenizer: BaseTokenizer,
                 config: ConfigRelCAT, save_dir_path: str) -> RelCAT:
    # tokenizer: Optional[TokenizerWrapperBase] = None
    # Load tokenizer
    # tokenizer = load_tokenizer(config, save_dir_path)

    # Create rel_cat
    # rel_cat = RelCAT(tokenizer=tokenizer, embeddings=None, config=config)
    component = RelExtrBaseComponent.from_relcat_config(config, save_dir_path)
    device = torch.device(
        "cuda" if torch.cuda.is_available() and
        component.relcat_config.general.device != "cpu" else "cpu")

    rel_cat = RelCAT(
        base_tokenizer, cdb=cdb,
        config=component.relcat_config, task=component.task)
    rel_cat.device = device
    rel_cat.component = component
    return rel_cat


def load_cnf(cnf_path: str) -> ConfigRelCAT:
    with open(cnf_path) as f1:
        data = json.load(f1)
    data = fix_old_style_cnf(data)
    cnf = ConfigRelCAT.model_validate(data)
    cnf.comp_name = RelCATAddon.addon_type
    return cnf


def get_rel_cat_from_old(cdb: CDB, old_path: str, tokenizer: BaseTokenizer
                         ) -> RelCATAddon:
    """Convert a v1 RelCAT folder to a v2 RelCAT.

    Args:
        cdb (CDB): The base CDB.
        old_path (str): The v1 RelCAT file path.
        tokenizer (BaseTokenizer): The tokenizer.

    Returns:
        RelCATAddon: The v2 RelCAT.
    """
    cnf = load_cnf(os.path.join(old_path, "config.json"))
    rel_cat = _load_legacy(cdb, tokenizer, cnf, old_path)
    addon = RelCATAddon.create_new(cnf, tokenizer, rel_cat.cdb)
    addon._rel_cat = rel_cat
    return addon


if __name__ == "__main__":
    import sys
    from medcat.config import Config
    cdb = CDB(Config())
    cdb.config.general.nlp.provider = 'spacy'
    rc = get_rel_cat_from_old(
        cdb, sys.argv[1], create_tokenizer("spacy", cdb.config))
