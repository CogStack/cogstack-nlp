from medcat2.cat import CAT
from medcat2.cdb.cdb import CDB
from medcat2.preprocessors.cleaners import prepare_name, NameDescriptor

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


def fix_subnames(cat: CAT) -> None:
    # NOTE: old v1 models may have not stored subnames (snames)
    #       on a per concept basis so we may need to rebuild that
    if has_per_concept_subnames(cat.cdb):
        return
    logger.info(
        "The previous CAT had no per-concept subnames. Adding them now.")
    _fix_subnames(cat)
