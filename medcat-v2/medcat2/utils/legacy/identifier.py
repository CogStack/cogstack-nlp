import os

EXPECTED_V1_CDB_FILE_NAME = "cdb.dat"
EXPECTED_V2_CDB_FOLDER_NAME = "cdb"


def is_legacy_model_pack(model_pack_path: str) -> bool:
    """Check if the model pack is a legacy model pack.

    Args:
        model_pack_path (str): The path to the model pack (unzipped).

    Returns:
        bool: True if the model pack is a legacy model pack, False otherwise.
    """
    if not os.path.isdir(model_pack_path):
        raise ValueError(
            f"Provided model pack path is not a directory: {model_pack_path}")
    cdb_path_v1 = os.path.join(model_pack_path, EXPECTED_V1_CDB_FILE_NAME)
    cdb_path_v2 = os.path.join(model_pack_path, EXPECTED_V2_CDB_FOLDER_NAME)
    return (
        # has cdb.dat and it is a file
        os.path.exists(cdb_path_v1) and os.path.isfile(cdb_path_v1) and
        # does not have cdb folder
        not os.path.exists(cdb_path_v2))
