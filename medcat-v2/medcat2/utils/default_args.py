"""This module exists purely to set the default arguments
in the config for the default tokenizer and the default
components creation.
"""
from typing import Optional

from medcat2.components.types import get_component_creator, CoreComponentType
from medcat2.components.addons.addons import get_addon_creator
from medcat2.tokenizing.tokenizers import BaseTokenizer, get_tokenizer_creator
from medcat2.config.config import ComponentConfig
from medcat2.config import Config
from medcat2.cdb import CDB
from medcat2.vocab import Vocab

import logging


logger = logging.getLogger(__name__)


def set_tokenizer_defaults(config: Config) -> None:
    """Set the default init arguments for the tokenizer.

    This generally uses the `get_init_args` and `get_init_kwargs`
    method bound to the tokenizer class.

    Args:
        config (Config): The same (modified) config.
    """
    nlp_cnf = config.general.nlp
    tok_cls = get_tokenizer_creator(nlp_cnf.provider)
    if hasattr(tok_cls, 'get_init_args'):
        nlp_cnf.init_args = tok_cls.get_init_args(config)
    else:
        logger.warning(
            "Could not set init arguments for tokenizer (%s). "
            "You generally need to specify these with the class method "
            "get_init_args(Config) -> list[Any].", nlp_cnf.provider)
    if hasattr(tok_cls, 'get_init_kwargs'):
        nlp_cnf.init_kwargs = tok_cls.get_init_kwargs(config)
    else:
        logger.warning(
            "Could not set init keyword arguments for tokenizer (%s). "
            "You generally need to specify these with the class method "
            "get_init_kwargs(Config) -> dict[str, Any].", nlp_cnf.provider)


def set_components_defaults(cdb: CDB, vocab: Optional[Vocab],
                            tokenizer: BaseTokenizer,
                            model_load_path: Optional[str]):
    """Set the default init arguments for the componts.

    This generally uses the `get_init_args` and `get_init_kwargs`
    method bound to the tokenizer class.

    Args:
        cdb (CDB): The CDB.
        vocab (Optional[Vocab]): The Vocab.
        tokenizer (BaseTokenizer): The tokenizer.
        model_load_path (Optional[str]): The model load path.
    """
    for comp_name, comp_cnf in cdb.config.components:
        if not isinstance(comp_cnf, ComponentConfig):
            # e.g ignore order
            continue
        comp_cls = get_component_creator(CoreComponentType[comp_name],
                                         comp_cnf.comp_name)
        if not isinstance(comp_cls, type):
            # i.e get CompCls from CompCls.create_new
            comp_cls = comp_cls.__self__  # type: ignore
        if hasattr(comp_cls, 'get_init_args'):
            comp_cnf.init_args = comp_cls.get_init_args(tokenizer, cdb, vocab,
                                                        model_load_path)
        else:
            logger.warning(
                "The component %s (%s) does not define init arguments. "
                "You generally need to specify these with the class method "
                "get_init_args(BaseTokenizer, CDB, Vocab) -> list[Any]",
                comp_name, comp_cnf.comp_name)
        if hasattr(comp_cls, 'get_init_kwargs'):
            comp_cnf.init_kwargs = comp_cls.get_init_kwargs(
                tokenizer, cdb, vocab, model_load_path)
        else:
            logger.warning(
                "The component %s (%s) does not define init keyword arguments."
                " You generally need to specify these with the class method "
                "get_init_kwargs(BaseTokenizer, CDB, Vocab) -> dict[str, Any]",
                comp_name, comp_cnf.comp_name)


def set_addon_defaults(cdb: CDB, vocab: Optional[Vocab],
                       tokenizer: BaseTokenizer,
                       model_load_path: Optional[str]):
    """Set default init arguments for addons.

    Args:
        cdb (CDB): The CDB.
        vocab (Optional[Vocab]): The Vocab.
        tokenizer (BaseTokenizer): The tokenizer.
        model_load_path (Optional[str]): The model load path.
    """
    for addon_cnf in cdb.config.components.addons:
        addon_cls = get_addon_creator(addon_cnf.comp_name)
        if not isinstance(addon_cls, type):
            # i.e get MetaCAT from MetaCAT.create_new
            addon_cls = addon_cls.__self__  # type: ignore
        if hasattr(addon_cls, 'get_init_args'):
            addon_cnf.init_args = addon_cls.get_init_args(
                tokenizer, cdb, vocab, model_load_path)
        else:
            logger.warning(
                "The addon  '%s' does not define init arguments. "
                "You generally need to specify these with the class method "
                "get_init_args(BaseTokenizer, CDB, Vocab) -> list[Any]",
                addon_cnf.comp_name)
        if hasattr(addon_cls, 'get_init_kwargs'):
            addon_cnf.init_kwargs = addon_cls.get_init_kwargs(
                tokenizer, cdb, vocab, model_load_path)
        else:
            logger.warning(
                "The component '%s' does not define init keyword arguments."
                " You generally need to specify these with the class method "
                "get_init_kwargs(BaseTokenizer, CDB, Vocab) -> dict[str, Any]",
                addon_cnf.comp_name)


class OptionalPartNotInstalledException(ValueError):

    def __init__(self, *args):
        super().__init__(*args)
