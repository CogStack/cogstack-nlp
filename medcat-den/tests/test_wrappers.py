import os

from medcat.cat import CAT
from medcat.storage.schema import load_schema

from medcat_den import wrappers

from .test_file_system_den import def_model_pack, _load_model, MODEL_PATH

import pytest


def wrap(cat: CAT) -> wrappers.CATWrapper:
    wrapped = wrappers.CATWrapper(cat)
    wrapped._model_info = "ABC"
    return wrapped


@pytest.fixture(scope='module')
def saved_model_pack_path(tmpdir_factory) -> str:
    tmpdir = tmpdir_factory.mktemp('model_path')
    cat = wrap(_load_model(MODEL_PATH))
    assert isinstance(cat, wrappers.CATWrapper)
    return cat.save_model_pack(tmpdir, force_save_local=True)


def test_wrapper_schema_CAT(saved_model_pack_path):
    schema = os.path.join(saved_model_pack_path.removesuffix(".zip"), '.schema.json')
    assert load_schema(schema)[0] == 'medcat.cat.CAT'


def test_wrapper_saves_as_CAT(saved_model_pack_path):
    loaded = CAT.load_model_pack(saved_model_pack_path)
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
