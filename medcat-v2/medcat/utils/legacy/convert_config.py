import json
from typing import Any, cast, Optional, Type
import logging

from pydantic import BaseModel

from medcat.config import Config

from medcat.utils.legacy.helpers import fix_old_style_cnf
from medcat.config.config import SerialisableBaseModel


logger = logging.getLogger(__name__)


SET_IDENTIFIER = "==SET=="
CONFIG_KEEP_IDENTICAL = {
    'cdb_maker', 'preprocessing'
}
CONFIG_MOVE = {
    'linking': 'components.linking',
    'ner': 'components.ner',
    'version.description': 'meta.description',
    'version.id': 'meta.hash',
    'version.ontology': 'meta.ontology',
    'general.spacy_model': 'general.nlp.modelname',
    'general.spacy_disabled_components': 'general.nlp.disabled_components',
}
CONFIG_MOVE_OPTIONAL = {
    "version.description", "version.id", "version.ontology"}
MOVE_WITH_REMOVES = {
    'general': {'checkpoint',  # TODO: Start supporitn checkpoints again
                'spacy_model', 'spacy_disabled_components', 'usage_monitor'},
    'annotation_output': {'doc_extended_info'},
}


def get_val_and_parent_model(old_data: Optional[dict],
                             cnf: Optional[Config],
                             path: str
                             ) -> tuple[Optional[Any], Optional[BaseModel]]:
    """Get the value and the model to set it for from the path specified.

    The paths may be specified in a `.`-separated manner. This unwraps that
    and figures out the value in the old model and the class that should
    be used in the new model.

    Args:
        old_data (Optional[dict]): The raw v1 config data.
        cnf (Optional[Config]): The v2 config.
        path (str): The path to look for.

    Returns:
        tuple[Optional[Any], Optional[BaseModel]]: The value to set, and the
            model to set it for.
    """
    val = old_data
    target_model: Optional[BaseModel] = cnf
    name = path
    while name:
        parts = name.split(".", 1)
        cname = parts[0]
        if len(parts) == 2:
            name = parts[1]
            if target_model is not None:
                target_model = cast(BaseModel, getattr(target_model, cname))
        else:
            name = ''
        if val is not None:
            if path in CONFIG_MOVE_OPTIONAL and cname not in val:
                logger.warning(
                    "Optional path '%s' not found in old config. Ignoring",
                    path)
                val = None
                break
            val = val[cname]
    return val, target_model


def _safe_setattr(target_model: BaseModel, fname: str, val: Any) -> None:
    mval = getattr(target_model, fname)
    if isinstance(mval, BaseModel) and isinstance(val, dict):
        for sname, sval in val.items():
            if not hasattr(mval, sname):
                logger.warning("Trying to set '%s' for '%s' but no such "
                               "attribute", sname, type(mval).__name__)
                continue
            _safe_setattr(mval, sname, sval)
    else:
        setattr(target_model, fname, val)


def _move_identicals(cnf: Config, old_data: dict) -> Config:
    for name in CONFIG_KEEP_IDENTICAL:
        val, target_model = get_val_and_parent_model(old_data, cnf, name)
        val = cast(Any, val)
        target_model = cast(BaseModel, target_model)
        fname = name.split(".")[-1]
        logger.info("Setting %s.%s to %s", type(target_model).__name__, fname,
                    type(val).__name__)
        _safe_setattr(target_model, fname, val)
    return cnf


def _move_partials(cnf: Config, old_data: dict) -> Config:
    for path, to_remove in MOVE_WITH_REMOVES.items():
        val, target_model = get_val_and_parent_model(old_data, cnf, path)
        val = cast(Any, val)
        target_model = cast(BaseModel, target_model)
        val = cast(dict, val).copy()
        for remove in to_remove:
            if remove in val:
                del val[remove]
        fname = path.split(".")[-1]
        logger.info("Setting %s while removing %d", path, len(to_remove))
        _safe_setattr(target_model, fname, val)
    return cnf


def _relocate(cnf: Config, old_data: dict) -> Config:
    for orig_path, new_path in CONFIG_MOVE.items():
        orig_val, _ = get_val_and_parent_model(old_data, cnf=None,
                                               path=orig_path)
        _, target_model = get_val_and_parent_model(None, cnf=cnf,
                                                   path=new_path)
        orig_val = cast(Any, orig_val)
        target_model = cast(BaseModel, target_model)
        fname = new_path.split(".")[-1]
        logger.info("Relocating from %s to %s (%s)", orig_path, new_path,
                    type(orig_val).__name__)
        _safe_setattr(target_model, fname, orig_val)
    return cnf


def _sanitise_sets(old_data: dict) -> dict:
    for k in list(old_data):
        v = old_data[k]
        if isinstance(v, dict) and len(v) == 1 and SET_IDENTIFIER in v:
            logger.info("Moving ")
            old_data[k] = set(v[SET_IDENTIFIER])
        elif isinstance(v, dict):
            # in place anyway
            _sanitise_sets(v)
    return old_data


def _make_changes(cnf: Config, old_data: dict) -> Config:
    old_data = _sanitise_sets(old_data)
    cnf = _move_identicals(cnf, old_data)
    cnf = _move_partials(cnf, old_data)
    cnf = _relocate(cnf, old_data)
    return cnf


def get_config_from_nested_dict(old_data: dict) -> Config:
    """Get the v2 config from v1 json data.

    Args:
        old_data (dict): The json (nested dict) data.

    Returns:
        Config: The v 2 config.
    """
    old_data = fix_old_style_cnf(old_data)
    cnf = Config()
    # v1 models always used spacy
    # but we now default to regex
    cnf.general.nlp.provider = 'spacy'
    cnf = _make_changes(cnf, old_data)
    if cnf.general.nlp.modelname in ('spacy_model', 'en_core_sci_md',
                                     'en_core_sci_lg'):
        logger.info("Fixing spacy model. "
                    "Moving from '%s' to 'en_core_web_md'!",
                    cnf.general.nlp.modelname)
        cnf.general.nlp.modelname = 'en_core_web_md'
    return cnf


def get_config_from_old(path: str) -> Config:
    """Convert the saved v1 config into a v2 Config.

    Args:
        path (str): The v1 config path.

    Returns:
        Config: The v2 config.
    """
    with open(path) as f:
        old_cnf_data = json.load(f)
    return get_config_from_nested_dict(old_cnf_data)


def get_config_from_old_per_cls(
        path: str, cls: Type[SerialisableBaseModel]) -> SerialisableBaseModel:
    """Convert the saved v1 config into a v2 Config for a specific class.

    Args:
        path (str): The v1 config path.
        cls (Type[SerialisableBaseModel]): The class to convert to.

    Returns:
        SerialisableBaseModel: The converted config.
    """
    from medcat.config.config_meta_cat import ConfigMetaCAT
    from medcat.config.config_transformers_ner import ConfigTransformersNER
    from medcat.config.config_rel_cat import ConfigRelCAT
    if cls is Config:
        return get_config_from_old(path)
    elif cls is ConfigMetaCAT:
        from medcat.utils.legacy.convert_meta_cat import (
            load_cnf as load_meta_cat_cnf)
        return load_meta_cat_cnf(path)
    elif cls is ConfigTransformersNER:
        from medcat.utils.legacy.convert_deid import (
            get_cnf as load_deid_cnf)
        return load_deid_cnf(path)
    elif cls is ConfigRelCAT:
        from medcat.utils.legacy.convert_rel_cat import (
            load_cnf as load_rel_cat_cnf)
        return load_rel_cat_cnf(path)
    raise ValueError(f"The config at '{path}' is not a {cls.__name__}!")
