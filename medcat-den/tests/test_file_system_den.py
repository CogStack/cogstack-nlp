from functools import lru_cache
from typing import cast
import os

from medcat.cat import CAT

from medcat_den.den import Den
from medcat_den.config import LocalDenConfig
from medcat_den.backend import DenType
from medcat_den.den_impl import LocalFileDen
from medcat_den.base import ModelInfo, ModelCard
from medcat_den.wrappers import CannotSaveOnDiskException

import pytest

from . import MODEL_PATH


UNSUP_TRAIN_EXAMPLE = [
    "The acute kidney failure we noticed was not an issue",
    "the doctor was not at all concerned by the loss of kidney function "
    "in an otherwise fit 25 year old male",
]


@pytest.fixture
def den(tmp_path: str):
    cnf = LocalDenConfig(type=DenType.LOCAL_USER, location=tmp_path)
    return LocalFileDen(cnf=cnf)


@pytest.fixture
def def_model_card() -> ModelCard:
    return {
        "Model ID": "SomeID",
        "Last Modified On": "date-modified",
        "History (from least to most recent)": [],
        'Description': "FAKE MODEL / not exists",
        'Source Ontology': ["NO-REAL-ONT"],
        'Location': "CI",
        'MetaCAT models': [],
        'Basic CDB Stats': {
            "Number of concepts": 1,
            "Number of names": 2,
            "Number of concepts that received training": 0,
            "Number of seen training examples in total": 0,
            "Average training examples per concept": 0,
            "Unsupervised training history": [],
            "Supervised training history": [],
        },
        'Performance': {},
        ('Important Parameters '
         '(Partial view, all available in cat.config)'): {},
        'MedCAT Version': "v2.0.0",
    }


@pytest.fixture
def def_model_info(def_model_card: ModelCard) -> ModelInfo:
    return ModelInfo(
            model_id='ID', model_card=def_model_card, base_model=None)


@lru_cache
def _load_model(path: str) -> CAT:
    return _load_model_internal(path)


def _load_model_internal(path: str) -> CAT:
    cat = CAT.load_model_pack(path)
    cat.config.meta.ontology = ["FAKE-ONT"]
    return cat


@pytest.fixture
def def_model_pack() -> CAT:
    return _load_model(MODEL_PATH)


# test empty den


def test_empty_den_has_no_models(den: Den):
    assert not den.list_available_models()


def test_empty_den_has_no_base_models(den: Den):
    assert not den.list_available_base_models()


def test_empty_den_returns_no_model(den: Den, def_model_info: ModelInfo):
    with pytest.raises(ValueError):
        den.fetch_model(model_info=def_model_info)


# test den with item


@pytest.fixture(scope='module')
def den_with_item(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("den_data")
    cnf = LocalDenConfig(type=DenType.LOCAL_USER, location=tmp_path)
    den = LocalFileDen(cnf=cnf)
    den.push_model(_load_model(MODEL_PATH), "BASE MODEL")
    return den


@pytest.fixture(scope='module')
def model_with_sup_training() -> CAT:  # NOTE: it's UNSUPERVISED
    cat = _load_model_internal(MODEL_PATH)
    cat.trainer.train_unsupervised(UNSUP_TRAIN_EXAMPLE)
    return cat


def test_has_a_model(den_with_item: Den):
    models = den_with_item.list_available_models()
    assert len(models) == 1


def test_is_a_base_model(den_with_item: Den):
    models = den_with_item.list_available_base_models()
    assert len(models) == 1


def test_den_has_correct_model(den_with_item: Den, def_model_pack: CAT):
    model = den_with_item.list_available_models()[0]
    assert model.model_id == def_model_pack.get_model_card(True)["Model ID"]


def test_den_has_correct_base_model(den_with_item: Den, def_model_pack: CAT):
    model = den_with_item.list_available_base_models()[0]
    assert model.model_id == def_model_pack.get_model_card(True)["Model ID"]


def test_den_returns_same_model(den_with_item: Den, def_model_pack: CAT):
    model = den_with_item.list_available_models()[0]
    smc = model.model_card
    rmc = def_model_pack.get_model_card(True)
    assert smc == rmc


def test_den_returned_model_cannot_be_saved(den_with_item: Den):
    model_info = den_with_item.list_available_base_models()[0]
    model = den_with_item.fetch_model(model_info)
    with pytest.raises(CannotSaveOnDiskException):
        model.save_model_pack(".", "model_pack_name")


def test_den_cannot_add_same_model(den_with_item: Den,
                                   def_model_pack: CAT):
    with pytest.raises(ValueError):
        den_with_item.push_model(def_model_pack, "No changes!")


def test_den_can_add_trained_model(den_with_item: Den,
                                   model_with_sup_training: CAT):
    base_model_info = den_with_item.list_available_base_models()[0]
    den_with_item.push_model(model_with_sup_training, "2 lines of training")
    avail_models = den_with_item.list_available_models()
    assert len(avail_models) == 2
    avail_model_ids = [model.model_id for model in avail_models]
    assert model_with_sup_training.get_model_card(
        True)["Model ID"] in avail_model_ids
    # not a base model
    assert len(den_with_item.list_available_base_models()) == 1
    # listed as derivative of base model
    derivs = den_with_item.list_available_derivative_models(base_model_info)
    assert len(derivs) == 1
    deriv_ids = [model.model_id for model in derivs]
    assert model_with_sup_training.get_model_card(
        True)["Model ID"] in deriv_ids


def test_den_cannot_remove_base_model(den_with_item: Den) -> None:
    mi = den_with_item.list_available_base_models()[0]
    with pytest.raises(ValueError):
        den_with_item.delete_model(mi)


def test_den_can_delete_non_base_model(den_with_item: Den) -> None:
    base = den_with_item.list_available_base_models()[0]
    deriv = den_with_item.list_available_derivative_models(base)[0]
    den_with_item.delete_model(deriv)
    zip_path = cast(LocalFileDen, den_with_item)._get_model_zip_path(deriv)
    assert den_with_item.list_available_base_models() == [base]
    assert den_with_item.list_available_models() == [base]
    assert not os.path.exists(zip_path)
    assert not os.path.exists(zip_path.removesuffix(".zip"))


def test_den_can_delete_model(den_with_item: Den) -> None:
    mi = den_with_item.list_available_models()[0]
    den_with_item.delete_model(mi, allow_delete_base_models=True)
    assert den_with_item.list_available_base_models() == []
