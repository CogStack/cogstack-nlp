import os


def ensure_folder_if_parent(folder_name: str) -> None:
    """Ensure the folder exists if its parent folder exists.

    Create a folder if the parent folder exists.
    If the parent folder does not exist, raise an error.

    Args:
        folder_name (str): The target folder.

    Raises:
        ValueError: If the parent folder does not exist.
    """
    target_folder = os.path.dirname(folder_name)
    if (os.path.exists(target_folder) and
            not os.path.exists(folder_name)):
        os.makedirs(folder_name)
    elif not os.path.exists(target_folder):
        raise ValueError("The target folder does not exist: "
                         f"{target_folder}")
