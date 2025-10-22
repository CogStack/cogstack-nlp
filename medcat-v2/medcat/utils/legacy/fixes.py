import logging

from medcat.cdb import CDB


logger = logging.getLogger(__name__)


def _fix_cui2original_names(cdb: CDB) -> None:
    cui2on = cdb.addl_info["cui2original_names"]
    num_cuis = len(cui2on)
    used_cuis = 0
    for ci in cdb.cui2info.values():
        orig_names: set[str] = cui2on.get(ci["cui"], None)
        if orig_names is not None:
            if ci["original_names"] is None:
                ci["original_names"] = orig_names
            else:
                ci["original_names"].update(orig_names)
            used_cuis += 1
    logger.info(
        "Used %d out of %d CUIs in the 'cui2original_names' map",
        used_cuis, num_cuis)
    # delete existing data in cui2original_names
    del cdb.addl_info["cui2original_names"]


def fix_cui2original_names_if_needed(cdb: CDB) -> bool:
    """Fix the cui2original names in CDB if needed.

    This was an issue caused by faulty legacy conversion
    where the data wasn't moved correctly from addl_info.

    Args:
        cdb (CDB): The CDB in question.

    Returns:
        bool: Whether the fix / change was made.
    """
    if "cui2original_names" in cdb.addl_info:
        logger.info(
            "CDB addl_info contains legacy data: "
            "'cui2original_names' . Moving it to cui2info")
        _fix_cui2original_names(cdb)
        return True
    else:
        logger.debug("CDB does not contain legacy 'cui2original_names")
        return False
