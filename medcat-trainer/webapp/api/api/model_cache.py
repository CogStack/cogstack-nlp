import logging
import os
from typing import Dict, Optional, Any

from pydantic import ValidationError

from medcat import __version__ as mct_version
from medcat.cat import CAT
from medcat.config.config import Config, SerialisableBaseModel
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.utils.legacy.convert_cdb import get_cdb_from_old

from api.models import ConceptDB

"""
Module level caches for CDBs, Vocabs and CAT instances.
"""
# Maps between IDs and objects
CDB_MAP = {}
VOCAB_MAP = {}
CAT_MAP = {}

logger = logging.getLogger(__name__)

try:
    _MAX_MODELS_LOADED = int(os.getenv("MAX_MEDCAT_MODELS", 1))
except ValueError:
    _MAX_MODELS_LOADED = 1
    logger.warning("MAX_MEDCAT_MODELS is not an integer, using default value of 1")


def _clear_models(cdb_map: Dict[str, CDB]=CDB_MAP,
                  vocab_map: Dict[str, Vocab]=VOCAB_MAP,
                  cat_map: Dict[str, CAT]=CAT_MAP):
    if len(cat_map) > _MAX_MODELS_LOADED:
        (k := next(iter(cat_map)), cat_map.pop(k))
    if len(cdb_map) > _MAX_MODELS_LOADED:
        (k := next(iter(cdb_map)), cdb_map.pop(k))
    if len(vocab_map) > _MAX_MODELS_LOADED:
        (k := next(iter(vocab_map)), vocab_map.pop(k))


def get_medcat_from_cdb_vocab(project,
                              cdb_map: Dict[str, CDB]=CDB_MAP,
                              vocab_map: Dict[str, Vocab]=VOCAB_MAP,
                              cat_map: Dict[str, CAT]=CAT_MAP) -> CAT:
    cdb_id = project.concept_db.id
    vocab_id = project.vocab.id
    cat_id = str(cdb_id) + "-" + str(vocab_id)
    if cat_id in cat_map:
        cat = cat_map[cat_id]
    else:
        if cdb_id in cdb_map:
            cdb = cdb_map[cdb_id]
        else:
            cdb_path = project.concept_db.cdb_file.path
            try:
                cdb = CDB.load(cdb_path)
            except NotADirectoryError as e:
                logger.warning("Legacy CDB found, converting to new format")
                # TODO: deserialise and write back to the model path?
                cdb = get_cdb_from_old(cdb_path)
                cdb.save(cdb_path)
                cdb_map[cdb_id] = cdb
                cdb_path = project.concept_db.cdb_file.path
                cdb_map[cdb_id] = cdb

            except KeyError as ke:
                mc_v = mct_version
                if int(mc_v.split('.')[0]) > 0:
                    logger.error('Attempted to load MedCAT v0.x model with MCTrainer v1.x')
                    raise Exception('Attempted to load MedCAT v0.x model with MCTrainer v1.x',
                                    'Please re-configure this project to use a MedCAT v1.x CDB or consult the '
                                    'MedCATTrainer Dev team if you believe this should work') from ke
                raise

            custom_config = os.getenv("MEDCAT_CONFIG_FILE")
            if custom_config is not None and os.path.exists(custom_config):
                _parse_config_file(cdb.config, custom_config)
            else:
                logger.info("No MEDCAT_CONFIG_FILE env var set to valid path, using default config available on CDB")
            cdb_map[cdb_id] = cdb

        if vocab_id in vocab_map:
            vocab = vocab_map[vocab_id]
        else:
            vocab_path = project.vocab.vocab_file.path
            vocab = Vocab.load(vocab_path)
            vocab_map[vocab_id] = vocab
        cat = CAT(cdb=cdb, config=cdb.config, vocab=vocab)
        cat_map[cat_id] = cat
        _clear_models(cat_map=cat_map, cdb_map=cdb_map, vocab_map=vocab_map)
    return cat


def _parse_config_file(config: Config,
                       custom_config_path: str):
    # NOTE: the v2 mappings are a little different
    mappings = {
        "linking": "components.linking",
        "ner": "components.ner",
    }
    mappings_key = {
        "spacy_model": "nlp.modelname"
    }
    with open(custom_config_path) as f:
        for line in f:
            if not line.strip().startswith("cat"):
                continue
            line = line[4:]
            left, right = line.split("=")
            variable, key = left.split(".")
            variable = variable.strip()
            # map to v2
            variable = mappings.get(variable, variable)
            key = key.strip()
            # key can also differ
            key = mappings_key.get(key, key)
            value = eval(right)
            alt_value = set() if right.strip() in ({}, "{}") else None

            # get (potentially nested in case of v2 mapping) attribute
            cnf = config
            while "." in variable:
                current, variable = variable.split(".", 1)
                cnf = getattr(cnf, current)
            attr = getattr(cnf, variable)
            while "." in key:
                cur_key, key = key.split(".", 1)
                attr = getattr(attr, cur_key)
            if isinstance(attr, SerialisableBaseModel):
                _set_value_or_alt(attr, key, value, alt_value)
            elif isinstance(attr, dict):
                attr[key] = value
            else:
                raise ValueError(f'Unknown attribute {attr} for "{line}"')


def _set_value_or_alt(conf: SerialisableBaseModel, key: str, value: Any,
                      alt_value: Any, err: Optional[ValidationError] = None) -> None:
    try:
        setattr(conf, key, value) # hoping for correct type
    except ValidationError as ve:
        if alt_value is not None:
            _set_value_or_alt(conf, key, alt_value, None, err=ve)
        elif err is not None:
            raise err
        else:
            raise ve


def get_medcat_from_model_pack(project, cat_map: Dict[str, CAT]=CAT_MAP) -> CAT:
    model_pack_obj = project.model_pack
    cat_id = 'mp' + str(model_pack_obj.id)
    logger.info('Loading model pack from:%s', model_pack_obj.model_pack.path)
    cat = CAT.load_model_pack(model_pack_obj.model_pack.path)
    cat_map[cat_id] = cat
    _clear_models(cat_map=cat_map)
    return cat


def get_medcat(project,
               cdb_map: Dict[str, CDB]=CDB_MAP,
               vocab_map: Dict[str, Vocab]=VOCAB_MAP,
               cat_map: Dict[str, CAT]=CAT_MAP):
    try:
        if project.model_pack is None:
            cat = get_medcat_from_cdb_vocab(project, cdb_map, vocab_map, cat_map)
        else:
            cat = get_medcat_from_model_pack(project, cat_map)
        return cat
    except AttributeError as err:
        raise Exception('Failure loading Project ConceptDB, Vocab or Model Pack. Are these set correctly?') from err


def get_cached_medcat(project, cat_map: Dict[str, CAT]=CAT_MAP):
    if project.model_pack is not None:
        cat_id = 'mp' + str(project.model_pack.id)
    else:
        cdb_id = project.concept_db.id
        vocab_id = project.vocab.id
        cat_id = str(cdb_id) + "-" + str(vocab_id)
    return cat_map.get(cat_id)


def clear_cached_medcat(project, cat_map: Dict[str, CAT]=CAT_MAP):
    if project.model_pack is not None:
        model_pack_obj = project.model_pack
        cat_id = 'mp' + str(model_pack_obj.id)
    else:
        cdb_id = project.concept_db.id
        vocab_id = project.vocab.id
        clear_cached_cdb(cdb_id)
        clear_cached_vocab(vocab_id)
        cat_id = str(cdb_id) + "-" + str(vocab_id)
    if cat_id in cat_map:
        del cat_map[cat_id]


def get_cached_cdb(cdb_id: str, cdb_map: Dict[str, CDB]=CDB_MAP) -> CDB:
    if cdb_id not in cdb_map:
        cdb_obj = ConceptDB.objects.get(id=cdb_id)
        cdb = CDB.load(cdb_obj.cdb_file.path)
        cdb_map[cdb_id] = cdb
    return cdb_map[cdb_id]


def clear_cached_cdb(cdb_id, cdb_map: Dict[str, CDB]=CDB_MAP):
    if cdb_id in cdb_map:
        del cdb_map[cdb_id]


def clear_cached_vocab(vocab_id, vocab_map: Dict[str, Vocab]=VOCAB_MAP):
    if vocab_id in vocab_map:
        del vocab_map[vocab_id]


def is_model_loaded(project,
                    cdb_map: Dict[str, CDB]=CDB_MAP,
                    cat_map: Dict[str, CAT]=CAT_MAP):
    if project.concept_db is None:
        # model pack is used.
        return False if not project.model_pack else f'mp{project.model_pack.id}' in cat_map
    else:
        return False if not project.concept_db else project.concept_db.id in cdb_map
