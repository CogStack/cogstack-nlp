from medcat.cat import CAT
from medcat.cdb.cdb import CDB
from medcat.preprocessors.cleaners import prepare_name, NameDescriptor

import logging


logger = logging.getLogger(__name__)


def has_per_concept_subnames(cdb: CDB) -> bool:
    for ci in cdb.cui2info.values():
        if ci['subnames']:
            return True
    return False


def _fix_subnames(cat: CAT) -> None:
    tknzer = cat._pipeline.tokenizer_with_tag
    for ci in cat.cdb.cui2info.values():
        names: dict[str, NameDescriptor] = {}
        for name in ci['names']:
            prepare_name(
                name, tknzer, names, (cat.config.general,
                                      cat.config.preprocessing,
                                      cat.config.cdb_maker))
        for name, descr in names.items():
            ci['subnames'].update(descr.snames)
            cat.cdb._subnames.update(descr.snames)


def fix_old_style_cnf(data: dict,
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
            v = fix_old_style_cnf(v)
        data[k] = v
    return data


def fix_subnames(cat: CAT) -> None:
    # NOTE: old v1 models may have not stored subnames (snames)
    #       on a per concept basis so we may need to rebuild that
    if has_per_concept_subnames(cat.cdb):
        return
    logger.info(
        "The previous CAT had no per-concept subnames. Adding them now.")
    _fix_subnames(cat)
