from enum import Enum, auto
from typing import Union, Type, Any
import os
from abc import ABC, abstractmethod
from importlib import import_module
import logging

import dill as _dill

from medcat2.storage.serialisables import Serialisable
from medcat2.storage.serialisables import get_all_serialisable_members
from medcat2.storage.schema import load_schema, save_schema
from medcat2.storage.schema import DEFAULT_SCHEMA_FILE, IllegalSchemaException


logger = logging.getLogger(__name__)


SER_TYPE_FILE = '.serialised_by'


class Serialiser(ABC):
    RAW_FILE = 'raw_dict.dat'

    @property
    @abstractmethod
    def ser_type(self) -> 'AvailableSerialisers':
        pass

    @abstractmethod
    def serialise(self, raw_parts: dict[str, Any], target_file: str) -> None:
        pass

    @abstractmethod
    def deserialise(self, target_file: str) -> dict[str, Any]:
        pass

    def save_ser_type_file(self, folder: str) -> None:
        file_path = os.path.join(folder, SER_TYPE_FILE)
        self.ser_type.write_to(file_path)

    def check_ser_type(self, folder: str) -> None:
        file_path = os.path.join(folder, SER_TYPE_FILE)
        in_folder = AvailableSerialisers.from_file(file_path)
        if in_folder != self.ser_type:
            raise TypeError(
                "Expected nested bits to be serialised by the same serialiser")

    def serialise_all(self, obj: Serialisable, target_folder: str) -> None:
        ser_parts, raw_parts = get_all_serialisable_members(obj)
        for part, name in ser_parts:
            basename = name
            part_folder = os.path.join(target_folder, basename)
            if os.path.exists(part_folder):
                raise IllegalSchemaException(
                    f"File already exists: {part_folder}. Unable to overwrite")
            os.mkdir(part_folder)
            # recursive
            self.serialise_all(part, part_folder)
        if raw_parts:
            raw_file = os.path.join(target_folder, self.RAW_FILE)
            self.serialise(raw_parts, raw_file)
        schema_path = os.path.join(target_folder, DEFAULT_SCHEMA_FILE)
        save_schema(schema_path, obj.__class__, obj.get_init_attrs())
        self.save_ser_type_file(target_folder)

    def deserialise_all(self, folder_path: str) -> Serialisable:
        self.check_ser_type(folder_path)
        schema_path = os.path.join(folder_path, DEFAULT_SCHEMA_FILE)
        cls_path, init_attrs = load_schema(schema_path)
        module_path, cls_name = cls_path.rsplit('.', 1)
        module = import_module(module_path)
        cls: Type = getattr(module, cls_name)
        init_kwargs: dict[str, Serialisable] = {}
        non_init_sers: dict[str, Serialisable] = {}
        for part_name in os.listdir(folder_path):
            if part_name == DEFAULT_SCHEMA_FILE or part_name == self.RAW_FILE:
                continue
            part_path = os.path.join(folder_path, part_name)
            if not os.path.isdir(part_path):
                continue
            part = self.deserialise_all(part_path)
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
    ser_type = AvailableSerialisers.dill

    def serialise(self, raw_parts: dict[str, Any], target_file: str) -> None:
        with open(target_file, 'wb') as f:
            _dill.dump(raw_parts, f)

    def deserialise(self, target_file: str) -> dict[str, Any]:
        with open(target_file, 'rb') as f:
            return _dill.load(f)


_DEF_SER = AvailableSerialisers.dill


def get_serialiser(
        serialiser_type: Union[str, AvailableSerialisers] = _DEF_SER
                   ) -> Serialiser:
    if isinstance(serialiser_type, str):
        serialiser_type = AvailableSerialisers[serialiser_type.lower()]
    if serialiser_type is AvailableSerialisers.dill:
        return DillSerialiser()
    elif serialiser_type is AvailableSerialisers.json:
        from medcat2.storage.jsonserialiser import JsonSerialiser
        return JsonSerialiser()
    raise ValueError("Unknown or unimplemented serialsier type: "
                     f"{serialiser_type}")


def get_serialiser_type_from_folder(folder_path: str) -> AvailableSerialisers:
    file_path = os.path.join(folder_path, SER_TYPE_FILE)
    return AvailableSerialisers.from_file(file_path)


def get_serialiser_from_folder(folder_path: str) -> Serialiser:
    ser_type = get_serialiser_type_from_folder(folder_path)
    logger.info("Determined serialised of type %s off disk",
                ser_type.name)
    return get_serialiser(ser_type)


def serialise(serialiser_type: Union[str, AvailableSerialisers],
              obj: Serialisable, target_folder: str) -> None:
    ser = get_serialiser(serialiser_type)
    ser.serialise_all(obj, target_folder)


def deserialise(folder_path: str) -> Serialisable:
    ser = get_serialiser_from_folder(folder_path)
    return ser.deserialise_all(folder_path)
