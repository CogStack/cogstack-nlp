import pytest

from medcat.cat import CAT

from medcat_den.base import ModelInfo
from medcat_den.wrappers import CATWrapper
from medcat_den.backend import DenType, _remote_den_map, register_remote_den
from medcat_den.resolver import resolve


class FakeDen:
    def __init__(self, **kwargs):
        return

    @property
    def den_type(self) -> DenType:
        return DenType.MEDCATTERY

    def list_available_models(self) -> list[ModelInfo]:
        return []

    def list_available_base_models(self) -> list[ModelInfo]:
        return []

    def list_available_derivative_models(self, model: ModelInfo
                                         ) -> list[ModelInfo]:
        return []

    def fetch_model(self, model_info: ModelInfo) -> CATWrapper:
        return

    def push_model(self, cat: CAT, description: str) -> None:
        return

    def _push_model_from_file(self, file_path: str, description: str) -> None:
        return

    def delete_model(self, model_info: ModelInfo,
                     allow_delete_base_models: bool = False) -> None:
        return


@pytest.fixture()
def with_added_backend():
    register_remote_den(DenType.MEDCATTERY, FakeDen)
    yield
    del _remote_den_map[DenType.MEDCATTERY]


@pytest.fixture()
def avoid_adding_extra_backends():
    existing = dict(_remote_den_map)
    yield
    _remote_den_map.clear()
    _remote_den_map.update(existing)


def test_normally_no_remote_backend():
    with pytest.raises(ValueError):
        resolve(DenType.MEDCATTERY, host="example.com",
                credentials={"Hello": "World"})


def test_can_register_backend(avoid_adding_extra_backends):
    register_remote_den(DenType.MEDCATTERY, FakeDen)
    assert DenType.MEDCATTERY in _remote_den_map


def test_can_resolve_registered_backend(with_added_backend):
    den = resolve(DenType.MEDCATTERY, host="example.com",
                  credentials={"Hello": "World"})
    assert isinstance(den, FakeDen)
