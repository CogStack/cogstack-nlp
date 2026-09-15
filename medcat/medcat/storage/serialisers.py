from enum import Enum, auto
from typing import Union, Type, Any, Optional
import os
from abc import ABC, abstractmethod
from importlib import import_module
import logging
import re
import importlib

import dill as _dill

from medcat.storage.serialisables import Serialisable, ManualSerialisable
from medcat.storage.serialisables import get_all_serialisable_members
from medcat.storage.schema import load_schema, save_schema
from medcat.storage.schema import DEFAULT_SCHEMA_FILE, IllegalSchemaException
from medcat.utils.legacy.v2_beta import (
    fix_module_and_cls_name, RemappingUnpickler)


logger = logging.getLogger(__name__)


SER_TYPE_FILE = '.serialised_by'
MANUAL_SERIALISED_TAG = 'MANUALLY_SERIALISED:'
MANUAL_SERIALISED_RE = re.compile(re.escape(MANUAL_SERIALISED_TAG) + "(.*)")


class Serialiser(ABC):
    """The abstract serialiser base class.

    This class is responsible for both serialising and deserialising.
    """
    RAW_FILE = 'raw_dict.dat'

    @property
    @abstractmethod
    def ser_type(self) -> 'AvailableSerialisers':
        """The serialiser type."""
        pass

    @abstractmethod
    def serialise(self, raw_parts: dict[str, Any], target_file: str) -> None:
        """Serialise the raw attributes / objects.

        Args:
            raw_parts (dict[str, Any]): The raw objects to serialise.
            target_file (str): The file name to write to.
        """
        pass

    @abstractmethod
    def deserialise(self, target_file: str) -> dict[str, Any]:
        """Deserialise data written to the specified file.

        Args:
            target_file (str): The file to read from.

        Returns:
            dict[str, Any]: The deserialised raw attributes / objects.
        """
        pass

    @classmethod
    def get_ser_type_file(cls, folder: str) -> str:
        return os.path.join(folder, SER_TYPE_FILE)

    def save_ser_type_file(self, folder: str) -> None:
        """Save the serialiser type into the specified folder.

        Args:
            folder (str): The folder to use.
        """
        file_path = self.get_ser_type_file(folder)
        self.ser_type.write_to(file_path)

    @classmethod
    def get_manually_serialised_path(cls, folder: str) -> Optional[str]:
        file_path = cls.get_ser_type_file(folder)
        with open(file_path) as f:
            contents = f.read()
        matched = MANUAL_SERIALISED_RE.match(contents)
        if matched is not None:
            return matched.group(1)
        return None

    def check_ser_type(self, folder: str) -> None:
        """Check that the folder contains data serialised by this serialiser.

        Args:
            folder (str): Target folder.

        Raises:
            TypeError: If the folder was not serialised by this serialiser.
        """
        file_path = os.path.join(folder, SER_TYPE_FILE)
        in_folder = AvailableSerialisers.from_file(file_path)
        if in_folder != self.ser_type:
            raise TypeError(
                "Expected nested bits to be serialised by the same serialiser")

    def serialise_all(self, obj: Serialisable, target_folder: str,
                      overwrite: bool = False) -> None:
        """Serialise the entire object into the target folder.

        This finds the serialisable parts (attributes) of the object and calls
        the same method on them recursively.
        It also finds the raw attributes (if any) and serialises them.

        Args:
            obj (Serialisable): The object to serialise.
            target_folder (str): The target folder.
            overwrite (bool): Whether to allow overwriting. Defaults to False.

        Raises:
            IllegalSchemaException:
                If there's multiple parts with the same name or
                a file already exists.
        """
        if isinstance(obj, ManualSerialisable):
            obj_cls = type(obj)
            logger.info("Serialising obj '%s' manually", obj_cls.__name__)
            obj.serialise_to(target_folder)
            # write the serialised_by meta file
            cls_path = obj_cls.__module__ + "." + obj_cls.__name__
            with open(self.get_ser_type_file(target_folder), 'w') as f:
                f.write(MANUAL_SERIALISED_TAG + cls_path)
            return
        ser_parts, raw_parts = get_all_serialisable_members(obj)
        for part, name in ser_parts:
            basename = name
            part_folder = os.path.join(target_folder, basename)
            if os.path.exists(part_folder) and not overwrite:
                raise IllegalSchemaException(
                    f"File already exists: {part_folder}. Unable to overwrite")
            elif not os.path.exists(part_folder):
                os.mkdir(part_folder)
            # recursive
            self.serialise_all(part, part_folder, overwrite=overwrite)
        if raw_parts:
            raw_file = os.path.join(target_folder, self.RAW_FILE)
            self.serialise(raw_parts, raw_file)
        schema_path = os.path.join(target_folder, DEFAULT_SCHEMA_FILE)
        save_schema(schema_path, obj.__class__, obj.get_init_attrs())
        self.save_ser_type_file(target_folder)

    @classmethod
    def deserialise_manually(cls, folder_path: str, man_cls_path: str,
                             **init_kwargs) -> Serialisable:
        logger.info("Deserialising manually based on %s", man_cls_path)
        module_name, cls_name = man_cls_path.rsplit(".", 1)
        module_name, cls_name = fix_module_and_cls_name(module_name, cls_name)
        rel_module = importlib.import_module(module_name)
        man_cls = getattr(rel_module, cls_name)
        if not issubclass(man_cls, ManualSerialisable):
            raise ValueError(
                f"Cannot manually serialise {folder_path} "
                "because the class used for manual serialisation "
                f"({man_cls_path}) does not implement ManualSerialisable")
        return man_cls.deserialise_from(folder_path, **init_kwargs)

    def deserialise_all(self, folder_path: str,
                        ignore_folders_prefix: set[str] = set(),
                        ignore_folders_suffix: set[str] = set(),
                        **kwargs) -> Serialisable:
        """Deserialise contents of folder.

        Additional initialisation keyword arguments can be provided if needed.

        This loads both the raw attributes for this object as well as the
        serialisable parts / attributes recursively.

        Args:
            folder_path (str): The folder path.
            ignore_folders_prefix (set[str]): The prefixes of folders
                to ignore.
            ignore_folders_suffix (set[str]): The suffixes of folders
                to ignore.

        Returns:
            Serialisable: The resulting object.
        """
        man_cls_path = self.get_manually_serialised_path(folder_path)
        if man_cls_path:
            return self.deserialise_manually(folder_path, man_cls_path)
        self.check_ser_type(folder_path)
        schema_path = os.path.join(folder_path, DEFAULT_SCHEMA_FILE)
        cls_path, init_attrs = load_schema(schema_path)
        module_path, cls_name = cls_path.rsplit('.', 1)
        module = import_module(module_path)
        cls: Type = getattr(module, cls_name)
        init_kwargs: dict[str, Serialisable] = kwargs
        non_init_sers: dict[str, Serialisable] = {}
        for part_name in os.listdir(folder_path):
            if part_name == DEFAULT_SCHEMA_FILE or part_name == self.RAW_FILE:
                continue
            suitable_folder = True
            for ignore_prefix in ignore_folders_prefix:
                if part_name.startswith(ignore_prefix):
                    suitable_folder = False
                    break
            for ignore_suffix in ignore_folders_suffix:
                if part_name.endswith(ignore_suffix):
                    suitable_folder = False
                    break
            if not suitable_folder:
                continue
            part_path = os.path.join(folder_path, part_name)
            if not os.path.isdir(part_path):
                continue
            part = self.deserialise_all(
                part_path, ignore_folders_prefix=ignore_folders_prefix,
                ignore_folders_suffix=ignore_folders_suffix)
            if part_name in init_attrs:
                init_kwargs[part_name] = part
            else:
                non_init_sers[part_name] = part
        raw_file = os.path.join(folder_path, self.RAW_FILE)
        raw_parts: dict[str, Any]
        if os.path.exists(raw_file):
            raw_parts = self.deserialise(raw_file)
        else:
            raw_parts = {}
        missing = set(set(init_attrs) - set(init_kwargs))
        if init_attrs and missing:
            for missed in missing:
                init_kwargs[missed] = raw_parts.pop(missed)
        obj = cls(**init_kwargs)
        all_items = list(raw_parts.items()) + list(non_init_sers.items())
        for attr_name, attr in all_items:
            setattr(obj, attr_name, attr)
        return obj


class AvailableSerialisers(Enum):
    """Describes the available serialisers."""
    dill = auto()
    json = auto()

    def write_to(self, file_path: str) -> None:
        with open(file_path, 'w') as f:
            f.write(self.name)

    @classmethod
    def from_file(cls, file_path: str) -> 'AvailableSerialisers':
        with open(file_path, 'r') as f:
            return cls[f.read().strip()]


class DillSerialiser(Serialiser):
    """The dill based serialiser."""
    ser_type = AvailableSerialisers.dill

    def serialise(self, raw_parts: dict[str, Any], target_file: str) -> None:
        with open(target_file, 'wb') as f:
            _dill.dump(raw_parts, f)

    def deserialise(self, target_file: str) -> dict[str, Any]:
        with open(target_file, 'rb') as f:
            return RemappingUnpickler(f).load()


_DEF_SER = AvailableSerialisers.dill


def get_serialiser(
        serialiser_type: Union[str, AvailableSerialisers] = _DEF_SER
                   ) -> Serialiser:
    """Get the serialiser based on the type specified.

    Args:
        serialiser_type (Union[str, AvailableSerialisers], optional):
            The required type. Defaults to 'dill'.

    Raises:
        ValueError: If no serialiser is found.

    Returns:
        Serialiser: The appropriate serialiser.
    """
    if isinstance(serialiser_type, str):
        serialiser_type = AvailableSerialisers[serialiser_type.lower()]
    if serialiser_type is AvailableSerialisers.dill:
        return DillSerialiser()
    elif serialiser_type is AvailableSerialisers.json:
        from medcat.storage.jsonserialiser import JsonSerialiser
        return JsonSerialiser()
    raise ValueError("Unknown or unimplemented serialsier type: "
                     f"{serialiser_type}")


def get_serialiser_type_from_folder(folder_path: str) -> AvailableSerialisers:
    """Get the serialiser type that was used to serialise data in the folder.

    Args:
        folder_path (str): The folder in question.

    Returns:
        AvailableSerialisers: The serialiser type.
    """
    file_path = os.path.join(folder_path, SER_TYPE_FILE)
    return AvailableSerialisers.from_file(file_path)


def get_serialiser_from_folder(folder_path: str) -> Serialiser:
    """Get the serialiser that was used to serialise the data in the folder.

    Args:
        folder_path (str): The folder in question.

    Returns:
        Serialiser: The appropriate serialiser.
    """
    ser_type = get_serialiser_type_from_folder(folder_path)
    logger.info("Determined serialised of type %s off disk",
                ser_type.name)
    return get_serialiser(ser_type)


def serialise(serialiser_type: Union[str, AvailableSerialisers],
              obj: Serialisable, target_folder: str,
              overwrite: bool = False) -> None:
    """Serialise an object based on the specified serialiser type.

    Args:
        serialiser_type (Union[str, AvailableSerialisers]):
            The serialiser type.
        obj (Serialisable):
            The object to serialise.
        target_folder (str):
            The folder to serialise into.
        overwrite (bool):
            Whether to allow overwriting. Defaults to False.
    """
    ser = get_serialiser(serialiser_type)
    ser.serialise_all(obj, target_folder, overwrite=overwrite)


def deserialise(folder_path: str,
                ignore_folders_prefix: set[str] = set(),
                ignore_folders_suffix: set[str] = set(),
                **init_kwargs) -> Serialisable:
    """Deserialise contents of a folder.

    Extra init keyword arguments can be provided if needed.
    These are generally:
    - cnf: The config relevant to the components
    - tokenizer (BaseTokenizer): The base tokenizer for the model
    - cdb (CDB): The CDB for the model
    - vocab (Vocab): The Vocab for the model
    - model_load_path (Optional[str]): The model load path,
        but not the component load path

    This method finds the serialiser to be used based on the files on disk.

    Args:
        folder_path (str): The folder to serialise.
        ignore_folders_prefix (set[str]): The prefixes of folders to ignore.
        ignore_folders_suffix (set[str]): The suffixes of folders to ignore.

    Returns:
        Serialisable: The deserialised object.
    """
    # if manually serialised, do manually deserialisation
    man_cls_path = Serialiser.get_manually_serialised_path(folder_path)
    if man_cls_path:
        return Serialiser.deserialise_manually(folder_path, man_cls_path,
                                               **init_kwargs)
    ser = get_serialiser_from_folder(folder_path)
    return ser.deserialise_all(
        folder_path, ignore_folders_prefix=ignore_folders_prefix,
        ignore_folders_suffix=ignore_folders_suffix, **init_kwargs)
