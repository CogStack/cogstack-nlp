from unicodedata import category
from medcat.cat import CAT

from medcat_den import wrappers

from .test_file_system_den import def_model_pack


def wrap(cat: CAT) -> wrappers.CATWrapper:
    return wrappers.CATWrapper(cat)


def test_wrapper_saves_as_CAT(tmpdir, def_model_pack):
    cat = wrap(def_model_pack)
    mpp = cat.save_model_pack(tmpdir, force_save_local=True)
    loaded = CAT.load_model_pack(mpp)
    assert isinstance(loaded, CAT)
    assert not isinstance(loaded, wrappers.CATWrapper)


def test_wrapper_gets_attributes(def_model_pack: CAT):
    cat = wrap(def_model_pack)
    assert cat.cdb is def_model_pack.cdb


def test_wrapper_gets_properties(def_model_pack: CAT):
    cat = wrap(def_model_pack)
    assert cat.pipe is def_model_pack.pipe


def test_wrapper_gets_methods(def_model_pack: CAT):
    cat = wrap(def_model_pack)
    text = "Kidney disease causes autism and fever in diabetes patients"
    assert cat.get_entities(text) == def_model_pack.get_entities(text)
