import platform
import os
import json # Added

import unittest.mock 

from medcat.cat import CAT

from medcat_den.den import DenBackend, Den # Changed
from medcat_den.resolver import resolve as main_resolve, resolve_from_config
from medcat_den.backend import DenType
from medcat_den.backend_impl.file_den import LocalFileDen
from medcat_den.cache.local_cache import has_local_cache, LocalCache
from medcat_den.config import LocalDenConfig
from medcat_den.base import ModelInfo # Added
from medcat_den.resolver.resolver import MEDCAT_DEN_BACKENDS_JSON # Added

from . import MODEL_PATH

import pytest

os_name = platform.system()


IS_LINUX = os_name == "Linux"
IS_MACOS = os_name == "Darwin"
IS_WINDOWS = os_name == "Windows"


def resolve(*args, **kwargs) -> DenBackend:
    backends, name = main_resolve(*args, **kwargs)
    return backends[name]


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


@pytest.fixture
def multi_backend_json_file(tmp_path):
    config = {
        "default_backend": "user_local",
        "backends": {
            "user_local": {
                "type": "local_user",
                "location": str(tmp_path / "user_local_den")
            },
            "machine_local": {
                "type": "local_machine",
                "location": str(tmp_path / "machine_local_den")
            }
        }
    }
    json_path = tmp_path / "multi_backend_config.json"
    with open(json_path, "w") as f:
        json.dump(config, f)
    return json_path


def test_resolve_multi_backend_from_json(multi_backend_json_file):
    os.environ[MEDCAT_DEN_BACKENDS_JSON] = str(multi_backend_json_file)
    backends, default_name = main_resolve()
    assert isinstance(backends, dict)
    assert default_name == "user_local"
    assert "user_local" in backends
    assert "machine_local" in backends
    assert isinstance(backends["user_local"], LocalFileDen)
    assert backends["user_local"].den_type == DenType.LOCAL_USER
    assert isinstance(backends["machine_local"], LocalFileDen)
    assert backends["machine_local"].den_type == DenType.LOCAL_MACHINE
    del os.environ[MEDCAT_DEN_BACKENDS_JSON]


def test_multi_backend_individual_access(multi_backend_json_file):
    os.environ[MEDCAT_DEN_BACKENDS_JSON] = str(multi_backend_json_file)
    backends, default_name = main_resolve()
    den = Den(backends=backends, default_backend_name=default_name)

    # Access default backend
    default_den = den._get_backend()
    assert isinstance(default_den, LocalFileDen)
    assert default_den.den_type == DenType.LOCAL_USER

    # Access named backends
    user_local_den = den._get_backend("user_local")
    assert isinstance(user_local_den, LocalFileDen)
    assert user_local_den.den_type == DenType.LOCAL_USER

    machine_local_den = den._get_backend("machine_local")
    assert isinstance(machine_local_den, LocalFileDen)
    assert machine_local_den.den_type == DenType.LOCAL_MACHINE
    del os.environ[MEDCAT_DEN_BACKENDS_JSON]


@pytest.fixture
def multi_backend_den(multi_backend_json_file) -> Den:
    os.environ[MEDCAT_DEN_BACKENDS_JSON] = str(multi_backend_json_file)
    backends, default_name = main_resolve()
    den = Den(backends=backends, default_backend_name=default_name)

    # Mock a method on one of the backends
    with unittest.mock.patch.object(
            den._backends["user_local"], 'list_available_models',
            return_value=[ModelInfo(model_id="testhash_user", model_card=None, base_model=None)]):
        with unittest.mock.patch.object(
                den._backends["machine_local"], 'list_available_models',
                return_value=[ModelInfo(model_id="testhash_machine", model_card=None, base_model=None)]):
            yield den


def test_multi_backend_method_delegation_default(multi_backend_den):
    models = multi_backend_den.list_available_models()
    assert len(models) == 1
    assert models[0].model_id == "testhash_user"


def test_multi_backend_method_delegation_dif_backend(multi_backend_den):
    models_machine = multi_backend_den.list_available_models(backend_name="machine_local")
    assert len(models_machine) == 1
    assert models_machine[0].model_id == "testhash_machine"
    del os.environ[MEDCAT_DEN_BACKENDS_JSON]
