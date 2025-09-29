from typing import Type
from enum import Enum


class DenType(str, Enum):
    LOCAL_USER = "local_user"
    LOCAL_MACHINE = "local_machine"
    MEDCATTERY = "medcattery"
    # S3 = "s3"
    # and so on

    def is_local(self) -> bool:
        return self in (DenType.LOCAL_USER, DenType.LOCAL_MACHINE)


_remote_den_map: dict[DenType, Type] = {}


def register_remote_den(den_type: DenType, den_cls: Type) -> None:
    """Register a remote den class for a given den type.

    Args:
        den_type (DenType): The den type.
        den_cls (Type): The den class.

    Raises:
        ValueError: If the den type is not remote.
        ValueError: If the den type is already registered.
    """
    if den_type.is_local():
        raise ValueError("Can only register remote dens")
    if den_type in _remote_den_map:
        raise ValueError(f"Den type {den_type} already registered")
    _remote_den_map[den_type] = den_cls


def has_registered_remote_den(den_type: DenType) -> bool:
    """Check if a remote den class is registered for a given den type.

    Args:
        den_type (DenType): The den type.

    Raises:
        ValueError: If the den type is not remote.

    Returns:
        bool: True if the den type is registered, False otherwise.
    """
    if den_type.is_local():
        raise ValueError("Can only check remote dens")
    return den_type in _remote_den_map


def get_registered_remote_den(den_type: DenType) -> Type:
    """Get the registered den class for a given den type.

    Args:
        den_type (DenType): The den type.

    Raises:
        ValueError: If the den type is not remote.
        ValueError: If the den type is not registered.

    Returns:
        Type: The den class.
    """
    if den_type.is_local():
        raise ValueError("Can only get remote dens")
    if den_type not in _remote_den_map:
        raise ValueError(f"Den type {den_type} not registered")
    return _remote_den_map[den_type]
