import pytest
from unittest.mock import MagicMock

from medcat_den.backend import DenType, _remote_den_map, register_remote_den
from medcat_den.resolver import resolve
from medcat_den.den import Den


class FakeDen(MagicMock):

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw, spec=Den)


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
