from typing import Callable

from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.config import Config
from medcat.vocab import Vocab
from medcat.utils.defaults import DEFAULT_PACK_NAME

from medcat.preprocessors.cleaners import prepare_name

from medcat_den.den import get_default_den, Den
from medcat_den.backend import DenType

from medcat_den.injection import medcat_injector

import unittest.mock
import pytest
import numpy as np

from .. import MODEL_PATH as EXAMPLE_MODEL_PATH


_ORIG_LOAD_METHOD = CAT.load_model_pack


def test_context_manager_works():
    assert CAT.load_model_pack == _ORIG_LOAD_METHOD
    with medcat_injector.injected_den():
        assert CAT.load_model_pack != _ORIG_LOAD_METHOD
    assert CAT.load_model_pack == _ORIG_LOAD_METHOD


def test_calls_injected_method():
    with unittest.mock.patch(
            "medcat_den.injection.medcat_injector.injected_load_model_pack"
            ) as mock_load_model_pack:
        with medcat_injector.injected_den():
            CAT.load_model_pack("SOME MODEL")
            mock_load_model_pack.assert_called_once()


@pytest.fixture
def cat() -> CAT:
    cnf = Config()
    cdb = CDB(cnf)
    return CAT(cdb)


@pytest.fixture
def den_with_model(tmp_path: str, cat: CAT) -> Den:
    den = get_default_den(DenType.LOCAL_USER, location=tmp_path)
    cat._versioning("Brand New Base Model")
    model_hash = cat.config.meta.hash
    den.push_model(cat, f"Empty Model w {model_hash}")
    return den


@pytest.fixture
def den_with_nonempty_model(den_with_model: Den):
    model = den_with_model.fetch_model(
        den_with_model.list_available_base_models()[0])
    model.vocab = Vocab()
    model.vocab.add_word("acute", 4, np.array([1, 0, 0]))
    model.vocab.add_word("chronic", 3, np.array([-1, 0, 0]))
    model.vocab.add_word("does", 10, np.array([0, 1, 0]))
    model.vocab.add_word("never", 8, np.array([0, 0, 1]))
    new_stuff = [
        ["C1", ["Kidney Failure", "renal failure"]],
        ["C2", ["epileptic fit", "epilepsy", "fit"]],
    ]
    for cui, raw_names in new_stuff:
        names = {}
        for raw_name in raw_names:
            prepare_name(
                raw_name, model.pipe.tokenizer, names,
                (model.config.general, model.config.preprocessing,
                 model.config.cdb_maker))
        model.cdb.add_names(cui, names)
    den_with_model.push_model(model, "added some vocab stuff and concepts")
    return den_with_model


def test_can_load_model(den_with_model: Den):
    model_hash = den_with_model.list_available_models()[0].model_id
    with medcat_injector.injected_den(den_getter=lambda: den_with_model):
        cat = CAT.load_model_pack(model_hash)
    assert cat.config.meta.hash == model_hash


def test_no_prefix_cannot_load_from_disk(den_with_model: Den):
    with medcat_injector.injected_den(den_getter=lambda: den_with_model):
        with pytest.raises(ValueError):
            CAT.load_model_pack(EXAMPLE_MODEL_PATH)


def test_can_load_model_with_mappings(den_with_model: Den):
    model_name = "My Model - really good"
    model_hash = den_with_model.list_available_models()[0].model_id
    name_map = {model_name: model_hash}
    with medcat_injector.injected_den(den_getter=lambda: den_with_model,
                                      model_name_mapper=name_map):
        cat = CAT.load_model_pack(model_name)
    assert cat.config.meta.hash == model_hash


def test_with_prefix_can_load_from_disk(den_with_model: Den):
    with medcat_injector.injected_den(den_getter=lambda: den_with_model,
                                      prefix="DEN:"):
        cat = CAT.load_model_pack(EXAMPLE_MODEL_PATH)
    assert isinstance(cat, CAT)


def test_with_prefix_can_load_from_den(den_with_model: Den):
    model_hash = den_with_model.list_available_base_models()[0].model_id
    with medcat_injector.injected_den(den_getter=lambda: den_with_model,
                                      prefix="DEN:"):
        cat = CAT.load_model_pack(f"DEN:{model_hash}")
    assert isinstance(cat, CAT)


def test_with_prefix_can_load_from_den_with_mapping(den_with_model: Den):
    model_name = "Cool model - works 1337"
    model_hash = den_with_model.list_available_base_models()[0].model_id
    name_map = {model_name: model_hash}
    with medcat_injector.injected_den(den_getter=lambda: den_with_model,
                                      prefix="DEN:",
                                      model_name_mapper=name_map):
        cat = CAT.load_model_pack(f"DEN:{model_hash}")
    assert isinstance(cat, CAT)


# inject with saving


def test_den_has_model_with_data(den_with_nonempty_model: Den):
    base_model_info = den_with_nonempty_model.list_available_base_models()[0]
    deriv_models = den_with_nonempty_model.list_available_derivative_models(
        base_model_info)
    assert deriv_models
    assert len(deriv_models) == 1
    model = den_with_nonempty_model.fetch_model(deriv_models[0])
    assert model.cdb.cui2info
    assert model.cdb.name2info


def _helper_can_save_model(den: Den, saver: Callable[[CAT, str], None]):
    message = "Made Some Good Changes"
    base_model_info = den.list_available_base_models()[0]
    derivs_before = den.list_available_derivative_models(
        base_model_info)
    example_hash = derivs_before[0].model_id
    with medcat_injector.injected_den(
            den_getter=lambda: den,
            inject_save=True):
        cat = CAT.load_model_pack(example_hash)
        cat.trainer.train_unsupervised([
            "Well, acute kidney failure never gets old, does it?",
            "What does a chronic epileptic fit even mean?"])
        # save
        saver(cat, message)
        derivs = den.list_available_derivative_models(
            base_model_info)
        assert derivs
        assert len(derivs) > len(derivs_before)
        # NOTE: find latest deriv
        deriv = max(derivs, key=lambda mi: len(
            mi.model_card["History (from least to most recent)"]))
        latest_description = deriv.model_card["Description"].split("\n")[-1]
        # NOTE: date is added
        assert message in latest_description


def test_can_save_model_when_injecting_with_saver_target_folder(
        den_with_nonempty_model: Den):
    # NOTE: sending message as target folder
    _helper_can_save_model(
        den_with_nonempty_model,
        lambda cat, message: cat.save_model_pack(message))


def test_can_save_model_when_injecting_with_saver_change_message_kwarg(
        den_with_nonempty_model: Den):
    # use change_description as explicit kwarg
    _helper_can_save_model(
        den_with_nonempty_model,
        lambda cat, message: cat.save_model_pack(
            None, change_description=message))


def test_can_save_model_when_injecting_with_saver_change_message_pack_name(
        den_with_nonempty_model: Den):
    # use change_description as explicit kwarg
    _helper_can_save_model(
        den_with_nonempty_model,
        lambda cat, message: cat.save_model_pack(
            None, message))


def test_can_save_model_when_injecting_with_saver_change_message_pos_arg(
        den_with_nonempty_model: Den):
    # use change_description as explicit kwarg
    _helper_can_save_model(
        den_with_nonempty_model,
        lambda cat, message: cat.save_model_pack(
            None, DEFAULT_PACK_NAME, 'dill', True, False, True, message))
