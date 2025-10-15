from typing import Union
from pathlib import Path

from pydantic import BaseModel

from medcat_den.backend import DenType


class DenConfig(BaseModel):
    type: DenType


class LocalDenConfig(DenConfig):
    location: Union[str, Path]


class RemoteDenConfig(DenConfig):
    host: str
    credentials: dict
    allow_local_fine_tune: bool
    allow_push_fine_tuned: bool


class LocalCacheConfig(BaseModel):
    path: Union[str, Path]
    expiration_time: int
    max_size: int
    eviction_policy: str
