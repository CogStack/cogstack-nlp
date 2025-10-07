from medcat_den.den import get_default_den
from medcat_den.backend import DenType
from medcat_den.den_impl.file_den import LocalFileDen


def test_defaults_to_local():
    cache = get_default_den()
    assert isinstance(cache, LocalFileDen)


def test_only_has_one_default_cache():
    cache1 = get_default_den()
    cache2 = get_default_den()
    assert cache1 is cache2


def test_only_has_one_den_per_type():
    cache1 = get_default_den(DenType.LOCAL_MACHINE)
    cache2 = get_default_den(DenType.LOCAL_MACHINE)
    assert cache1 is cache2
