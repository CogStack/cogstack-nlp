from typing import Optional

import os
import logging
import platform

from platformdirs import user_data_dir, site_data_dir

from medcat_den.backend import (
    DenType, get_registered_remote_den, has_registered_remote_den)
from medcat_den.den import Den

from medcat_den.den_impl.file_den import LocalFileDen
from medcat_den.cache import LocalCache
from medcat_den.cache.local_cache import (
    DEFAULT_EXPIRATION_TIME, DEFAULT_MAX_SIZE, DEFAULT_EVICTION_POLICY)
from medcat_den.config import (
    DenConfig, LocalDenConfig, RemoteDenConfig, LocalCacheConfig)
from medcat_den.utils import cache_on_model


logger = logging.getLogger(__name__)


DEFAULT_USER_PATH = user_data_dir("medcat-den", "CogStack")
DEFAULT_MACHINE_PATH = site_data_dir("medcat-den", "CogStack")
IS_LINUX = platform.system() == "Linux"
IS_MACOS = platform.system() == "Darwin"
ALT_LOCATION_LINUX = "/var/tmp/medcat-den"

# the evnironment variable names
MEDCAT_DEN_TYPE = "MEDCAT_DEN_TYPE"
MEDCAT_DEN_PATH = "MEDCAT_DEN_PATH"
MEDCAT_DEN_REMOTE_HOST = "MEDCAT_DEN_REMOTE_HOST"
MEDCAT_DEN_LOCAL_CACHE_PATH = "MEDCAT_DEN_LOCAL_CACHE_PATH"
MEDCAT_DEN_LOCAL_CACHE_EXPIRATION_TIME = (
    "MEDCAT_DEN_LOCAL_CACHE_EXPIRATION_TIME")
MEDCAT_DEN_LOCAL_CACHE_MAX_SIZE = "MEDCAT_DEN_LOCAL_CACHE_MAX_SIZE"
MEDCAT_DEN_LOCAL_CACHE_EVICTION_POLICY = (
    "MEDCAT_DEN_LOCAL_CACHE_EVICTION_POLICY")


def is_writable(path: str, propgate: bool = True) -> bool:
    if os.path.exists(path):
        return os.access(path, os.W_OK)
    elif not propgate:
        return False
    return is_writable(os.path.dirname(path), propgate=False)


def _init_den_cnf(
        type_: Optional[DenType] = None,
        location: Optional[str] = None,
        host: Optional[str] = None,
        credentials: Optional[dict] = None,) -> DenConfig:
    # Priority: args > env > defaults
    type_in = (
        type_
        or os.getenv(MEDCAT_DEN_TYPE)
        or DenType.LOCAL_USER
    )
    type_final = DenType(type_in)
    logger.info("Resolving Den of type: %s", type_final)

    if type_final.is_local():
        location_final = str(
            location
            or os.getenv(MEDCAT_DEN_PATH)
            or (DEFAULT_MACHINE_PATH if type_final == DenType.LOCAL_MACHINE
                else DEFAULT_USER_PATH)
        )
        if (location_final and (IS_LINUX or IS_MACOS) and
                not is_writable(location_final) and
                location_final == DEFAULT_MACHINE_PATH):
            logger.warning(
                "The machine-local location '%s' does not have write access. "
                "Using an alternative of '%s' instead",
                location, ALT_LOCATION_LINUX)
            location_final = ALT_LOCATION_LINUX
    den_cnf: DenConfig
    if type_final.is_local():
        den_cnf = LocalDenConfig(type=type_final,
                                 location=location_final)
    else:
        if not host:
            raise ValueError("Need to specify a host for remote den")
        if not credentials:
            raise ValueError("Need to specify credentials for remote den")
        den_cnf = RemoteDenConfig(type=type_final,
                                  host=host,
                                  credentials=credentials)
    return den_cnf


def resolve(
    type_: Optional[DenType] = None,
    location: Optional[str] = None,
    host: Optional[str] = None,
    credentials: Optional[dict] = None,
    local_cache_path: Optional[str] = None,
    expiration_time: Optional[int] = None,
    max_size: Optional[int] = None,
    eviction_policy: Optional[str] = None,
) -> Den:
    den_cnf = _init_den_cnf(type_, location, host, credentials)
    den = resolve_from_config(den_cnf)
    lc_cnf = _init_lc_cnf(
        local_cache_path, expiration_time, max_size, eviction_policy)
    if lc_cnf:
        _add_local_cache(den, lc_cnf)
    return den


def _resolve_local(config: LocalDenConfig) -> LocalFileDen:
    # NOTE: currently will be in a subfolder still, but I think it's fine
    den = LocalFileDen(cnf=config)
    if config.type == DenType.LOCAL_MACHINE:
        # NOTE: this isn't currently done on the den init side
        den._den_type = DenType.LOCAL_MACHINE
    return den


# NOTE: caching on model json
#       so cannot use @lru_cache directly
@cache_on_model
def resolve_from_config(config: DenConfig) -> Den:
    if isinstance(config, LocalDenConfig):
        return _resolve_local(config)
    # TODO: support remote (e)
    # elif type_final == DenType.MEDCATTERY:
    #     host = host or os.getenv(MEDCAT_DEN_REMOTE_HOST)
    #     if host is None:
    #         raise ValueError("Remote DEN requires a host address")
    #     # later you’d plug in MedcatteryRemoteDen, MLFlowDen, etc.
    #     return MedCATteryDen(host=host, credentials=credentials)
    elif has_registered_remote_den(config.type):
        den_cls = get_registered_remote_den(config.type)
        den = den_cls(cnf=config)
        if not isinstance(den, Den):
            raise ValueError(
                f"Registered den class for {config.type} is not a Den")
        return den
    else:
        raise ValueError(
            f"Unsupported Den type: {config.type}")


def _init_lc_cnf(local_cache_path: Optional[str],
                 expiration_time_in: Optional[int],
                 max_size_in: Optional[int],
                 eviction_policy_in: Optional[str]
                 ) -> Optional[LocalCacheConfig]:
    local_cache_path = (
        local_cache_path
        or os.getenv(MEDCAT_DEN_LOCAL_CACHE_PATH)
    )
    if not local_cache_path:
        return None
    expiration_time = expiration_time_in or int(
        os.getenv(MEDCAT_DEN_LOCAL_CACHE_EXPIRATION_TIME,
                  DEFAULT_EXPIRATION_TIME))
    max_size = max_size_in or int(os.getenv(
        MEDCAT_DEN_LOCAL_CACHE_MAX_SIZE, DEFAULT_MAX_SIZE))
    eviction_policy = str(eviction_policy_in or os.getenv(
        MEDCAT_DEN_LOCAL_CACHE_EVICTION_POLICY,
        DEFAULT_EVICTION_POLICY))
    return LocalCacheConfig(
            path=local_cache_path,
            expiration_time=expiration_time,
            max_size=max_size,
            eviction_policy=eviction_policy,
    )


def _add_local_cache(den: Den, lc_cnf: LocalCacheConfig) -> None:
    if not os.path.exists(lc_cnf.path):
        os.makedirs(lc_cnf.path, exist_ok=True)
    cache = LocalCache(lc_cnf)
    logger.info("Using local cache at %s", lc_cnf.path)
    cache.add_to_den(den)
