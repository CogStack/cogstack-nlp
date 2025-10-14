from typing import TypedDict
import json
import os
import time
import urllib.request
from pathlib import Path
from packaging.version import Version, InvalidVersion
import logging

from medcat.utils.defaults import (
    MEDCAT_DISABLE_VERSION_CHECK_ENVIRON, MEDCAT_PYPI_URL_ENVIRON,
    MEDCAT_MINOR_UPDATE_THRESHOLD_ENVIRON,
    MEDCAT_PATCH_UPDATE_THRESHOLD_ENVIRON,
    MEDCAT_VERSION_UPDATE_LOG_LEVEL_ENVIRON,
    MEDCAT_VERSION_UPDATE_YANKED_LOG_LEVEL_ENVIRON,
)
from medcat.utils.defaults import (
    DEFAULT_PYPI_URL, DEFAULT_MINOR_FOR_INFO, DEFAULT_PATCH_FOR_INFO,
    DEFAULT_VERSION_INFO_LEVEL, DEFAULT_VERSION_INFO_YANKED_LEVEL)


DEFAULT_CACHE_PATH = (
    Path.home() / ".cache" / "cogstack" / "medcat_version.json")
# 1 week
DEFAULT_CHECK_INTERVAL = 7 * 24 * 3600


logger = logging.getLogger(__name__)


def log_info(msg: str, *args, yanked: bool = False, **kwargs):
    if yanked:
        lvl = os.environ.get(MEDCAT_VERSION_UPDATE_YANKED_LOG_LEVEL_ENVIRON,
                             DEFAULT_VERSION_INFO_YANKED_LEVEL).upper()
    else:
        lvl = os.environ.get(MEDCAT_VERSION_UPDATE_LOG_LEVEL_ENVIRON,
                             DEFAULT_VERSION_INFO_LEVEL).upper()
    _level_map = {
        "NOTSET": logging.NOTSET,
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARN": logging.WARNING,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.FATAL,
    }
    level = _level_map.get(lvl, logging.INFO)
    logger.log(level, msg, *args, **kwargs)


def _get_env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _should_check(cache_path: Path, check_interval: int) -> bool:
    if not cache_path.exists():
        return True
    try:
        with open(cache_path) as f:
            last_check = json.load(f)["last_check"]
        return time.time() - last_check > check_interval
    except Exception:
        return True


class UpdateCheckConfig(TypedDict):
    pkg_name: str
    cache_path: Path
    url: str
    enabled: bool
    minor_threshold: int
    patch_threshold: int
    timeout: float
    check_interval: int


def _get_config(pkg_name: str) -> UpdateCheckConfig:
    if os.getenv(MEDCAT_DISABLE_VERSION_CHECK_ENVIRON,
                 "False").lower() in ("true", "yes", "disable"):
        return {
            "pkg_name": pkg_name,
            "enabled": False,
            "cache_path": Path("."),
            "url": "-1",
            "minor_threshold": -1,
            "patch_threshold": -1,
            "timeout": -1.0,
            "check_interval": -1,
        }
    base_url = os.getenv(MEDCAT_PYPI_URL_ENVIRON, DEFAULT_PYPI_URL).rstrip("/")
    url = f"{base_url}/{pkg_name}/json"
    minor_thresh = _get_env_int(MEDCAT_MINOR_UPDATE_THRESHOLD_ENVIRON,
                                DEFAULT_MINOR_FOR_INFO)
    patch_thresh = _get_env_int(MEDCAT_PATCH_UPDATE_THRESHOLD_ENVIRON,
                                DEFAULT_PATCH_FOR_INFO)
    # TODO: add env variables for timeout and default cache?
    return {
        "pkg_name": pkg_name,
        "enabled": True,
        "cache_path": DEFAULT_CACHE_PATH,
        "url": url,
        "minor_threshold": minor_thresh,
        "patch_threshold": patch_thresh,
        "timeout": 3.0,
        "check_interval": DEFAULT_CHECK_INTERVAL,
    }


def check_for_updates(pkg_name: str, current_version: str):
    cnf = _get_config(pkg_name)
    if not cnf["enabled"]:
        return

    if not _should_check(cnf["cache_path"], cnf["check_interval"]):
        return

    try:
        with urllib.request.urlopen(cnf["url"],
                                    timeout=cnf["timeout"]) as r:
            data = json.load(r)
        releases = {
            v: files for v, files in data.get("releases", {}).items()
            if files  # skip empty entries
        }
    except Exception as e:
        log_info("Unable to check for update", exc_info=e)
        return

    # cache update time
    cnf["cache_path"].parent.mkdir(parents=True, exist_ok=True)
    with open(cnf["cache_path"], "w") as f:
        json.dump({"last_check": time.time()}, f)

    _do_check(cnf, releases, current_version)


def _do_check(cnf: UpdateCheckConfig, releases: dict,
              current_version: str):
    try:
        current = Version(current_version)
    except InvalidVersion:
        return
    pkg_name = cnf["pkg_name"]
    patch_thresh = cnf["patch_threshold"]
    minor_thresh = cnf["minor_threshold"]

    newer_minors, newer_patches = [], []
    yanked = False
    for v_str, files in releases.items():
        try:
            v = Version(v_str)
        except InvalidVersion:
            continue
        if v <= current:
            continue
        if any(f.get("yanked") for f in files):
            continue  # don’t count yanked releases in comparisons
        if v.major == current.major and v.minor == current.minor:
            newer_patches.append(v)
        elif v.major == current.major and v.minor > current.minor:
            newer_minors.append(v)

    # detect if current version is yanked
    for f in releases.get(current_version, []):
        if f.get("yanked"):
            reason = f.get("yanked_reason", "")
            msg = (f"⚠️  You are using a yanked version ({pkg_name} "
                   f"{current_version}). {reason}")
            log_info(msg, yanked=True)
            yanked = True
            break

    # report newer versions
    if len(newer_patches) >= patch_thresh:
        latest_patch = max(newer_patches)
        msg = (f"ℹ️  {pkg_name} {current_version} → {latest_patch} "
               f"({len(newer_patches)} newer patch releases available)")
        log_info(msg)
    elif len(newer_minors) >= minor_thresh:
        latest_minor = max(newer_minors)
        msg = (f"⚠️  {pkg_name} {current_version} → {latest_minor} "
               f"({len(newer_minors)} newer minor releases available)")
        log_info(msg)

    if yanked and not (newer_minors or newer_patches):
        msg = (f"⚠️  Your installed version {current_version} was yanked and "
               "has no newer stable releases yet.")
        log_info(msg, yanked=True)
