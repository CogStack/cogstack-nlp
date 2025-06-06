from typing import Any
from contextlib import contextmanager
from pydantic import BaseModel


@contextmanager
def temp_changed_config(config: BaseModel, target: str, value: Any):
    """Context manager to change the config temporarily (within).

    Args:
        config (BaseModel): The config in question.
        target (str): The attribute name to change.
        value (Any): The temporary value to use.

    Raises:
        IllegalConfigPathException: If no previous value is available.
    """
    try:
        prev_value = getattr(config, target)
    except AttributeError as e:
        raise IllegalConfigPathException(target) from e
    setattr(config, target, value)
    try:
        yield
    finally:
        setattr(config, target, prev_value)


class IllegalConfigPathException(ValueError):

    def __init__(self, target_path: str):
        super().__init__(
            f"Config has no target path: {target_path}")
