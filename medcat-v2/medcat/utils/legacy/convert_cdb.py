import dill
import logging

from medcat.cdb import CDB
from medcat.config import Config
from medcat.cdb.concepts import get_new_cui_info, get_new_name_info, TypeInfo
from medcat.utils.legacy.convert_config import get_config_from_nested_dict


logger = logging.getLogger(__name__)


class LegacyClassNotFound:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        return f"<LegacyClassNotFound args={self.args} kwargs={self.kwargs}>"


class CustomUnpickler(dill.Unpickler):
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except (AttributeError, ModuleNotFoundError):
            logger.warning(
                "Missing class %s.%s, replacing with LegacyClassNotFound.",
                module, name)
            return LegacyClassNotFound


def load_old_raw_data(old_path: str) -> dict:
    """Looads the raw data from old file.

    This uses a wrapper that allows loading the data even if the classes
    do not exist.

    Args:
        old_path (str): The path of the file to read.

    Returns:
        dict: The resulting raw data.
    """
    with open(old_path, 'rb') as f:
        # NOTE: custom unpickler needed because we
        #       do not have access to original modules within medcat(v1)
        data = CustomUnpickler(f).load()
    return data


EXPECTED_USEFUL_KEYS = [
    'name2cuis', 'name2cuis2status', 'name2count_train', 'name_isupper',

    'snames',

    'cui2names', 'cui2snames', 'cui2context_vectors', 'cui2count_train',
    'cui2tags', 'cui2type_ids', 'cui2preferred_name', 'cui2average_confidence',

    'addl_info',
    'vocab',
]
NAME2KEYS = {'name2cuis', 'name2cuis2status', 'name2count_train',
             'name_isupper'}
OPTIONAL_NAME2_KEYS = {"name_isupper", }
CUI2KEYS = {'cui2names', 'cui2snames', 'cui2context_vectors',
            'cui2count_train', 'cui2info', 'cui2tags', 'cui2type_ids',
            'cui2preferred_name', 'cui2average_confidence', }
CUI2KEYS_OPTIONAL = {"cui2info", }
TO_RENAME = {'vocab': 'token_counts'}


_DEFAULT_SNOMED_TYPE_ID2NAME = {
    '32816260': 'physical object', '2680757': 'observable entity',
    '37552161': 'body structure', '91776366': 'product',
    '81102976': 'organism', '28321150': 'procedure',
    '67667581': 'finding', '7882689': 'qualifier value',
    '91187746': 'substance', '29422548': 'core metadata concept',
    '40357424': 'foundation metadata concept',
    '33782986': 'morphologic abnormality', '9090192': 'disorder',
    '90170645': 'record artifact', '66527446': 'cell structure',
    '3061879': 'situation', '16939031': 'occupation',
    '31601201': 'person', '37785117': 'medicinal product',
    '17030977': 'assessment scale', '47503797': 'regime/therapy',
    '33797723': 'event', '82417248': 'navigational concept',
    '75168589': 'environment', '9593000': 'medicinal product form',
    '99220404': 'cell', '13371933': 'social concept',
    '46922199': 'religion/philosophy', '27603525': 'clinical drug',
    '43039974': 'attribute', '43857361': 'physical force',
    '40584095': 'metadata', '337250': 'specimen',
    '46506674': 'disposition', '87776218': 'role',
    '30703196': 'tumor staging', '31685163': 'staging scale',
    '21114934': 'dose form', '70426313': 'namespace concept',
    '51120815': 'intended site', '45958968': 'administration method',
    '51885115': 'OWL metadata concept', '8067332': 'basic dose form',
    '95475658': 'product name', '43744943': 'supplier',
    '66203715': 'transformation', '64755083': 'release characteristic',
    '49144999': 'state of matter', '39041339': 'unit of presentation',
    '18854038': 'geographic location', '28695783': 'link assertion',
    '14654508': 'racial group', '20410104': 'ethnic group',
    '92873870': 'special concept', '72706784': 'product',
    '78096516': 'environment / location', '25624495': 'SNOMED RT+CTV3',
    '55540447': 'linkage concept', '3242456': 'social context'
}


def _add_cui_info(cdb: CDB, data: dict) -> CDB:
    all_cuis = set()
    for key in CUI2KEYS:
        if key in CUI2KEYS_OPTIONAL and key not in data:
            logger.info(
                "Optional key to be converted was not found in target "
                "data: %s. Ignoring", key)
            continue
        ccuis = data[key].keys()
        logger.debug("Adding %d cuis based on '%s", len(ccuis), key)
        all_cuis.update(ccuis)
    logger.info("A total of %d CUIs identified", len(all_cuis))
    cui2names, cui2snames = data['cui2names'], data['cui2snames']
    cui2cv, cui2ct = data['cui2context_vectors'], data['cui2count_train']
    cui2tags, cui2type_ids = data['cui2tags'], data['cui2type_ids']
    cui2prefname = data['cui2preferred_name']
    cui2av_conf = data['cui2average_confidence']
    for cui in all_cuis:
        names = cui2names.get(cui, set())
        snames = cui2snames.get(cui, set())
        vecs = cui2cv.get(cui, None)
        count_train = cui2ct.get(cui, 0)
        tags = cui2tags.get(cui, None)
        type_ids = cui2type_ids.get(cui, set())
        prefname = cui2prefname.get(cui, None)
        av_conf = cui2av_conf.get(cui, 0.0)
        info = get_new_cui_info(
            cui=cui, preferred_name=prefname, names=names, subnames=snames,
            type_ids=type_ids, tags=tags, count_train=count_train,
            context_vectors=vecs, average_confidence=av_conf,
        )
        cdb.cui2info[cui] = info
    all_cui_tuis = set((ci['cui'], tui) for ci in cdb.cui2info.values()
                       for tui in ci['type_ids'])
    all_tuis = set(tui for _, tui in all_cui_tuis)
    if (not (tid2name := data['addl_info'].get('type_id2name', None)) and
            # UMLS has TypeIds that start with T
            # so in this case we can be _pretty sure_ it's Snomed
            not any("T" in tui for tui in all_tuis)):
        tid2name = {
            tid: name for tid, name in _DEFAULT_SNOMED_TYPE_ID2NAME.items()
            if tid in all_tuis
        }
        print("Set TypeID2name for", len(tid2name),
              'TypeIDs out of', len(all_tuis))
    print("Conditions", bool(not tid2name),
          not any("T" in tui for tui in all_tuis),
          "IN", all_tuis)
    print("Got TypeID2name for", len(tid2name),
          'TypeIDs out of', len(all_tuis))
    for cui, tui in all_cui_tuis:
        if tui not in cdb.type_id2info:
            cdb.type_id2info[tui] = TypeInfo(
                type_id=tui, name=tid2name.get(tui), cuis=set())
        cdb.type_id2info[tui].cuis.add(cui)
    cdb.addl_info.update(data['addl_info'])
    # for cui, ontos in data['addl_info']['cui2ontologies'].items():
    #     cdb.cui2info[cui]['in_other_ontology'] = ontos
    return cdb


def _add_name_info(cdb: CDB, data: dict) -> CDB:
    all_names = set()
    for key in NAME2KEYS:
        if key in OPTIONAL_NAME2_KEYS and key not in data:
            continue
        cnames = data[key].keys()
        logger.debug("Adding %d names based on '%s", len(cnames), key)
        all_names.update(cnames)
    logger.info("A total of %d names found", len(all_names))
    logger.info("Adding names from cui2names")
    # add from cui2names
    for cui_infos in cdb.cui2info.values():
        all_names.update(cui_infos['names'])
    logger.info("A total of %d names found after adding from cui2names",
                len(all_names))
    # NOTE: name2cuis has the same cuis as name2cuis2status
    #       so v2 only uses the latter since it provides extra information
    name2cuis2status = data['name2cuis2status']
    name2cnt_train = data['name2count_train']
    name2is_upper = data.get('name_isupper', {})
    for name in all_names:
        cuis2status: dict[str, str] = {}
        _cuis2status = name2cuis2status.get(name, {})
        cuis2status.update(_cuis2status)
        cnt_train = name2cnt_train.get(name, 0)
        is_upper = name2is_upper.get(name, False)
        info = get_new_name_info(name, per_cui_status=cuis2status,
                                 is_upper=is_upper, count_train=cnt_train)
        cdb.name2info[name] = info
    return cdb


def update_names(cdb: CDB, data: dict):
    for name_from, name_to in TO_RENAME.items():
        setattr(cdb, name_to, data[name_from])


def convert_data(all_data: dict) -> CDB:
    """Convert the raw v1 data into a CDB.

    Args:
        all_data (dict): The raw v1 data off disk.

    Returns:
        CDB: The v2 CDB.
    """
    data = all_data['cdb']
    cdb = CDB(Config())
    cdb = _add_cui_info(cdb, data)
    cdb = _add_name_info(cdb, data)
    update_names(cdb, data)
    if 'config' in all_data:
        logger.info("Loading old style CDB with config included.")
        cdb.config = get_config_from_nested_dict(all_data['config'])
    return cdb


def get_cdb_from_old(old_path: str) -> CDB:
    """Get the v2 CDB from a v1 CDB path.

    Args:
        old_path (str): The v1 CDB path.

    Returns:
        CDB: The v2 CDB.
    """
    data = load_old_raw_data(old_path)
    return convert_data(data)
