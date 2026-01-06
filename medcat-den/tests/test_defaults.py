from medcat_den.den import get_default_den
from medcat_den.backend import DenType
from medcat_den.backend_impl.file_den import LocalFileDen


def test_defaults_to_local():
    cache = get_default_den()
    assert isinstance(cache._get_backend(), LocalFileDen)


def test_only_has_one_default_cache_backend():
    cache1 = get_default_den()._backends
    cache2 = get_default_den()._backends
    assert cache1 == cache2
    assert len(cache1) == 1
    assert list(cache1.values())[0] is list(cache2.values())[0]


def test_only_has_one_backend_per_type():
    cache1 = get_default_den(DenType.LOCAL_MACHINE)._backends
    cache2 = get_default_den(DenType.LOCAL_MACHINE)._backends
    assert cache1 == cache2
    assert len(cache1) == 1
    assert list(cache1.values())[0] is list(cache2.values())[0]
