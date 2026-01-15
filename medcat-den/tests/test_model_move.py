import pytest

from medcat.cat import CAT
from medcat.config import Config
from medcat.cdb import CDB
from medcat.vocab import Vocab

from medcat_den.base import ModelInfo
from medcat_den.den import Den, DenType, DuplicateModelException, NoSuchBackendException, NoSuchModel
from medcat_den.config import LocalDenConfig
from medcat_den.backend_impl.file_den import LocalFileDen


def _create_file_den(path: str) -> LocalFileDen:
    cnf = LocalDenConfig(type=DenType.LOCAL_USER, location=path)
    return LocalFileDen(cnf)


@pytest.fixture
def mbe_den(tmp_path_factory) -> Den:
    den1 = _create_file_den(str(tmp_path_factory.mktemp("den_path1")))
    den2 = _create_file_den(str(tmp_path_factory.mktemp("den_path2")))
    full_den = Den({
        "den1": den1,
        "den2": den2,
    }, "den1")
    return full_den


@pytest.fixture
def tiny_cat() -> CAT:
    cnf = Config()
    cdb = CDB(cnf)
    vocab = Vocab()
    return CAT(cdb, vocab, cnf)


def test_has_multiple_back_ends(mbe_den):
    assert len(mbe_den._backends) > 1


def test_can_add_cat_default(mbe_den: Den, tiny_cat: CAT):
    assert not mbe_den.list_available_models()
    mbe_den.push_model(tiny_cat, "msg")
    assert mbe_den.list_available_models()
    # other is empty
    assert not mbe_den.list_available_models('den2')


def test_can_add_cat_other(mbe_den: Den, tiny_cat: CAT):
    assert not mbe_den.list_available_models('den2')
    mbe_den.push_model(tiny_cat, "msg", 'den2')
    assert mbe_den.list_available_models('den2')
    # default is empty
    assert not mbe_den.list_available_models()


def test_can_move_model(mbe_den: Den, tiny_cat: CAT):
    mbe_den.push_model(tiny_cat, "msg", backend_name='den1')
    assert not mbe_den.list_available_models("den2")
    # only one
    model_info = mbe_den.list_available_models()[0]
    # move
    mbe_den.move_model(model_info, 'den1', 'den2')
    assert mbe_den.list_available_models("den2")


def test_canot_move_origin_not_exist(mbe_den: Den):
    with pytest.raises(NoSuchBackendException):
        mbe_den.move_model(None, 'denX', 'den2')


def test_canot_move_dest_not_exist(mbe_den: Den):
    with pytest.raises(NoSuchBackendException):
        mbe_den.move_model(None, 'den1', 'denX')


def test_cannot_move_model_not_exist_in_origin(mbe_den: Den, tiny_cat: CAT):
    mi = ModelInfo.from_model_pack(tiny_cat)
    with pytest.raises(NoSuchModel):
        mbe_den.move_model(mi, 'den1', 'den2')


def test_cannot_move_model_duplicate_in_destination(mbe_den: Den, tiny_cat: CAT):
    mi = ModelInfo.from_model_pack(tiny_cat)
    mbe_den.push_model(tiny_cat, "msg", 'den2')
    with pytest.raises(DuplicateModelException):
        mbe_den.move_model(mi, 'den1', 'den2')
