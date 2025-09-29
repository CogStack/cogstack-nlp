from typing import Union, cast

import os
from io import BytesIO

import shutil

from diskcache import Cache

from medcat_den.den import Den
from medcat_den.base import ModelInfo
from medcat_den.wrappers import CATWrapper
from medcat_den.config import LocalCacheConfig


DEFAULT_EXPIRATION_TIME = 10 * 24 * 60 * 60  # 10 days
DEFAULT_MAX_SIZE = 100 * 2**30  # 100 GB total
DEFAULT_EVICTION_POLICY = 'least-recently-used'


class LocalCache:

    def __init__(self, cnf: LocalCacheConfig,) -> None:
        self._cnf = cnf
        self._cache_path = self._cnf.path
        self.cache = Cache(self._cnf.path,
                           size_limit=self._cnf.max_size,
                           eviction_policy=self._cnf.eviction_policy)

    def get(self, key: str) -> str:
        """Fetch file path from cache.

        Args:
            key (str): File key.

        Raises:
            ValueError: If key not found or expired.

        Returns:
            str: The file path.
        """
        if key not in self.cache:
            raise ValueError(f"The key {key} is not in the cache")
        # update expiry upon access
        self.cache.touch(key, expire=self._cnf.expiration_time)
        with self.cache.get(key, read=True) as fh:
            if fh is not None:
                return fh.name
        raise ValueError(f"The key {key} is not in the cache or has expired")

    def insert(self, key: str, file_path: str) -> None:
        """Insert a file into the cache.

        Args:
            key (str): The key to use.
            file_path (str): The path to the file to cache.
        """
        with open(file_path, "rb") as fh:
            self.cache.set(key, fh, read=True,
                           expire=self._cnf.expiration_time)

    def insert_raw(self, key: str, data: bytes) -> None:
        """Insert raw bytes into the cache.

        Args:
            key (str): The key to use.
            data (bytes): The raw bytes to cache.
        """
        with BytesIO(data) as fh:
            self.cache.set(key, fh, read=True,
                           expire=self._cnf.expiration_time)

    def delete(self, key: str) -> None:
        """Delete a key from the cache.

        Args:
            key (str): The key to delete.
        """
        if key in self.cache:
            file_path = self[key]
            del self.cache[key]
            folder_path = file_path.removesuffix(".zip")
            if os.path.exists(folder_path):
                shutil.rmtree(folder_path)
        # NOTE: if there's an expiry, then the folder will NOT be deleted

    def __getitem__(self, key: str) -> str:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self.cache

    def __setitem__(self, key: str, file: Union[str, bytes]) -> None:
        if isinstance(file, str):
            self.insert(key, file)
        else:
            self.insert_raw(key, file)

    def __delitem__(self, key: str) -> None:
        self.delete(key)

    def add_to_den(self, den: Den) -> None:
        """Add this local cache to the given den.

        Args:
            den (Den): The den to add the cache to.
        """
        # wrap push_model to add to cache
        orig_push = den._push_model_from_file

        def push_wrapper(cat_path: str, description: str) -> None:
            # do remote push frist
            orig_push(cat_path, description)
            # and then cache it locally
            base_name = os.path.basename(cat_path)
            model_hash = base_name.removesuffix(".zip")
            self[model_hash] = cat_path

        den._push_model_from_file = push_wrapper  # type: ignore
        # wrap fetch_model to check cache first
        orig_fetch = den.fetch_model

        def fetch_wrapper(model_info: ModelInfo) -> CATWrapper:
            model_hash = model_info.model_id
            if model_hash in self:
                model_path = self[model_hash]
                return cast(CATWrapper, CATWrapper.load_model_pack(
                    model_path, model_info=model_info))
            cat = orig_fetch(model_info)
            # cache it
            model_path = f"{model_hash}.zip"
            self[model_hash] = model_path
            return cat

        den.fetch_model = fetch_wrapper  # type: ignore
        den.cache = self  # type: ignore


def has_local_cache(den: Den) -> bool:
    """Check if the given den has a local cache.

    Args:
        den (Den): The den to check.

    Returns:
        bool: True if it has a local cache, False otherwise.
    """
    return hasattr(den, 'cache') and isinstance(den.cache, LocalCache)
