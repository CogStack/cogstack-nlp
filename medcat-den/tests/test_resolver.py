import platform
import os

from medcat.cat import CAT

from medcat_den.resolver import resolve, resolve_from_config
from medcat_den.backend import DenType
from medcat_den.den_impl.file_den import LocalFileDen
from medcat_den.cache.local_cache import has_local_cache, LocalCache
from medcat_den.config import LocalDenConfig

from . import MODEL_PATH

import pytest

os_name = platform.system()


IS_LINUX = os_name == "Linux"
IS_MACOS = os_name == "Darwin"
IS_WINDOWS = os_name == "Windows"


def test_defaults_to_user_local():
    den = resolve()
    assert isinstance(den, LocalFileDen)
    models_folder = den._models_folder
    if IS_LINUX:
        assert models_folder.startswith("/home")
        assert ".local" in models_folder
    elif IS_MACOS:
        assert models_folder.startswith("/Users")
        assert "/Library/Application Support/" in models_folder
    elif IS_WINDOWS:
        assert models_folder.startswith("C:\\Users")
        assert "AppData" in models_folder
    else:
        raise ValueError("Unable to test against platform...")
    assert not has_local_cache(den)


def test_can_do_machine_local():
    den = resolve(DenType.LOCAL_MACHINE)
    assert isinstance(den, LocalFileDen)
    models_folder = den._models_folder
    if IS_LINUX:
        assert (
            models_folder.startswith("/usr/local/share/") or
            models_folder.startswith("/var/tmp/"))
    elif IS_MACOS:
        assert (
            models_folder.startswith("/Library/Application Support/") or
            # NOTE: the above is not accessible unless you use sudo
            models_folder.startswith("/var/tmp/"))
    elif IS_WINDOWS:
        assert models_folder.startswith("C:\\ProgramData")
    else:
        raise ValueError("Unable to test against platform...")
    assert not has_local_cache(den)


def test_can_use_local_cache(tmp_path: str):
    den = resolve(local_cache_path=tmp_path)
    assert has_local_cache(den)


@pytest.fixture
def cat() -> CAT:
    cat = CAT.load_model_pack(MODEL_PATH)
    cat.config.meta.ontology = ["FAKE-ONT"]
    return cat


def test_saves_to_local_cache(cat: CAT, tmp_path: str):
    den_path = os.path.join(tmp_path, "den")
    den = resolve(local_cache_path=tmp_path, location=den_path)
    den.push_model(cat, "Some Base CAT")
    cache: LocalCache = den.cache
    model_id = cat.get_model_card(True)["Model ID"]
    model_path = cache.get(model_id)
    assert os.path.exists(model_path)


@pytest.fixture
def user_cnf(tmp_path: str):
    return LocalDenConfig(type=DenType.LOCAL_USER, location=tmp_path)


@pytest.fixture
def machine_cnf(tmp_path: str):
    return LocalDenConfig(type=DenType.LOCAL_MACHINE, location=tmp_path)


@pytest.fixture
def all_cnfs(user_cnf: LocalDenConfig, machine_cnf: LocalDenConfig
             ) -> list[LocalDenConfig]:
    return [user_cnf, machine_cnf]


def test_resolves_to_same_with_same_cnf(all_cnfs: list[LocalDenConfig]):
    for cnf in all_cnfs:
        assert isinstance(cnf, LocalDenConfig)
        cache1 = resolve_from_config(cnf)
        cache2 = resolve_from_config(cnf)
        assert cache1 is cache2


def test_resolves_to_same_with_copied_cnf(all_cnfs: list[LocalDenConfig]):
    for cnf in all_cnfs:
        assert isinstance(cnf, LocalDenConfig)
        cache1 = resolve_from_config(cnf)
        cache2 = resolve_from_config(cnf.model_copy())
        assert cache1 is cache2


def test_change_in_config_values_provides_new_den(user_cnf: LocalDenConfig):
    cache1 = resolve_from_config(user_cnf)
    user_cnf.type = DenType.LOCAL_MACHINE
    cache2 = resolve_from_config(user_cnf)
    assert cache1 is not cache2


def test_resolves_to_different_instances_upon_different_cnf(
        user_cnf, machine_cnf):
    cache1 = resolve_from_config(user_cnf)
    cache2 = resolve_from_config(machine_cnf)
    assert cache1 is not cache2
