import os
import shutil
import tempfile
from typing import Union, Literal

from medcat.storage.serialisables import Serialisable
from medcat.storage.serialisers import (
    serialise, deserialise, AvailableSerialisers)


def should_serialise_as_zip(path: str,
                            as_zip: Union[bool, Literal['auto']]
                            ) -> bool:
    if as_zip == 'auto':
        return path.endswith(".zip")
    return as_zip


def serialise_as_zip(
        obj: Serialisable, path: str,
        ser_type: Union[AvailableSerialisers, str] = AvailableSerialisers.dill,
        overwrite: bool = False,
        ) -> None:
    """Serialse the file to a .zip at the specified path.

    The process uses the regular `serialise` method to serialise the object
    as a folder into a temporary directory and subsequently zips it up to
    the path requested.

    Args:
        obj (Serialisable): The object to serialise.
        path (str): The path to serialse the file to. Should end with .zip.
        ser_type (Union[AvailableSerialisers, str], optional): The serialiser
            to use. Defaults to AvailableSerialisers.dill.
        overwrite (bool, optional):
            Whether to allow overwriting existing files. Defaults to False.
    """
    if not path.endswith('.zip'):
        raise ValueError(f"Path must end with .zip, got {path}")
    with tempfile.TemporaryDirectory() as tmpdir:
        serialise(ser_type, obj, tmpdir)
        if not overwrite and os.path.exists(path):
            raise ValueError(f"Cannot overwrite existing file: {path}")
        base_name = path[:-4]  # remove '.zip'
        shutil.make_archive(
            base_name=base_name,
            format='zip',
            root_dir=tmpdir,
        )


def deserialise_from_zip(path: str) -> Serialisable:
    """Deserialise from a zip file.

    The process involves unzipping the contents to a temporary directory,
    and subsequently using the ruglar `deserialise` method to deserialise
    from that.

    Args:
        path (str): The path to deserialise from. Should end with .zip.

    Returns:
        Serialisable: The deserialised object
    """
    if not path.endswith('.zip'):
        raise ValueError(f"Path must end with .zip, got {path}")
    with tempfile.TemporaryDirectory() as tmpdir:
        shutil.unpack_archive(path, tmpdir, format='zip')
        return deserialise(tmpdir)
