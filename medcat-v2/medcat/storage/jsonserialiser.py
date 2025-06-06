from typing import Protocol, Any, TypeVar, Generic, cast
from datetime import datetime
from dataclasses import is_dataclass, asdict, dataclass
import importlib
import json

import numpy as np

from medcat.storage.serialisers import Serialiser, AvailableSerialisers


T = TypeVar("T")


# Protocol for type handlers
class TypeHandler(Protocol, Generic[T]):
    type_name: str
    type_cls: type

    def should_encode(self, obj: Any) -> bool:
        pass

    def encode(self, obj: T) -> Any:
        """Encode an object of the registered type."""
        pass

    def decode(self, obj: Any) -> T:
        """Decode an object of the registered type."""
        pass


# Registry for type handlers
class TypeRegistry:
    _type_key = "__type__"
    _data_key = "data"

    def __init__(self) -> None:
        self.handlers: dict[str, TypeHandler] = {}

    def register(self, handler: TypeHandler) -> None:
        """Register a new type handler."""
        self.handlers[handler.type_name] = handler

    def encode(self, obj: Any) -> Any:
        """Encode an object using the registered handler."""
        for handler in self.handlers.values():
            if handler.should_encode(obj):
                return {self._type_key: handler.type_name,
                        self._data_key: handler.encode(obj)}
        return obj  # Default handling

    def decode(self, obj: Any) -> Any:
        """Decode an object using the registered handler."""
        if isinstance(obj, dict) and self._type_key in obj:
            type_name = obj[self._type_key]
            if type_name in self.handlers:
                return self.handlers[type_name].decode(obj[self._data_key])
        return obj  # Default handling


class TypeBasedHandler(TypeHandler[T]):

    def should_encode(self, obj: Any) -> bool:
        return isinstance(obj, self.type_cls)


class NumpyArrayHandler(TypeBasedHandler[np.ndarray]):
    type_name = "ndarray"
    type_cls = np.ndarray
    _dtype_key = "dtype"
    _data_key = "data"
    _shape_key = "shape"

    def encode(self, obj: np.ndarray) -> Any:
        """Encode numpy ndarray."""
        return {
            self._data_key: obj.tolist(),
            self._dtype_key: str(obj.dtype),
            self._shape_key: obj.shape}

    def decode(self, obj: Any) -> np.ndarray:
        """Decode to numpy ndarray."""
        return np.array(
            obj[self._data_key],
            dtype=obj[self._dtype_key]).reshape(
                obj[self._shape_key])


class SetHandler(TypeBasedHandler[set]):
    type_name = "set"
    type_cls = set

    def encode(self, obj: set) -> Any:
        """Encode set."""
        return list(obj)

    def decode(self, obj: Any) -> set:
        """Decode to set."""
        return set(obj)


class DateTimeHandler(TypeBasedHandler[datetime]):
    type_name = "datetime"
    type_cls = datetime

    def encode(self, obj: datetime) -> Any:
        return obj.isoformat()

    def decode(self, obj: Any):
        return datetime.fromisoformat(obj)


class DataClassHandler(TypeHandler[T]):
    type_name = "dataclass"
    type_cls = type(dataclass)  # NOTE: shouldn't be used
    _cls_key = "class-path"
    _data_key = "data"

    def should_encode(self, obj: Any) -> bool:
        return is_dataclass(obj)

    def encode(self, obj: T) -> Any:
        cls_path = f"{obj.__class__.__module__}.{obj.__class__.__name__}"
        return {
            self._cls_key: cls_path,
            # NOTE: mypy doesn't know that this is a dataclass
            self._data_key: asdict(obj),  # type: ignore
        }

    def decode(self, obj: Any) -> T:
        cls_path: str = obj[self._cls_key]
        module_name, cls_name = cls_path.rsplit('.', 1)
        module = importlib.import_module(module_name)
        cls = getattr(module, cls_name)
        if not is_dataclass(cls):
            raise TypeError(f"Unsupported type: {cls}")
        # NOTE: mypy doesn't know that the dataclass init can be called here
        return cast(T, cls(**obj[self._data_key]))  # type: ignore


_def_registry = TypeRegistry()


_def_registry.register(NumpyArrayHandler())
_def_registry.register(SetHandler())
_def_registry.register(DateTimeHandler())
_def_registry.register(DataClassHandler())


class JsonSerialiser(Serialiser):
    ser_type = AvailableSerialisers.json

    def serialise(self, raw_parts: dict[str, Any], target_file: str) -> None:
        with open(target_file, 'w') as f:
            json.dump(raw_parts, f, default=_def_registry.encode)

    def deserialise(self, target_file: str) -> dict[str, Any]:
        with open(target_file, 'r') as f:
            return json.load(f, object_hook=_def_registry.decode)
