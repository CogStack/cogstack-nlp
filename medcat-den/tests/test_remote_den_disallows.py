from typing import cast
from medcat_den.config import RemoteDenConfig
from medcat_den.backend import DenType
from medcat_den.injection import injected_den
from medcat_den.wrappers import CATWrapper, CannotSendToRemoteException
from medcat_den.wrappers import NotAllowedToFineTuneLocallyException
from medcat_den.den import Den
from medcat_den.den_impl.file_den import LocalFileDen
from medcat_den.base import ModelInfo

from medcat.cat import CAT

import pytest

from .test_file_system_den import def_model_pack, den, UNSUP_TRAIN_EXAMPLE  # noqa


def get_wrapped_model_pack(
        in_model_pack: CAT, cnf: RemoteDenConfig) -> CATWrapper:  # noqa
    # make it a wrapper
    in_model_pack.__class__ = CATWrapper
    model_pack = cast(CATWrapper, in_model_pack)
    # set required stuff, mostly the config
    model_pack._den_cnf = cnf
    # set model info
    model_pack._model_info = ModelInfo.from_model_pack(model_pack)
    return model_pack


@pytest.fixture
def cnf_disallow_all():
    return RemoteDenConfig(type=DenType.MEDCATTERY,
                           host="ABC",
                           credentials={"A": "B"},
                           allow_local_fine_tune=False,
                           allow_push_fine_tuned=False,
                           )


@pytest.fixture
def cnf_allow_push_only():
    return RemoteDenConfig(type=DenType.MEDCATTERY,
                           host="ABC",
                           credentials={"A": "B"},
                           allow_local_fine_tune=False,
                           allow_push_fine_tuned=True,
                           )


@pytest.fixture
def cnf_allow_finetune_only():
    return RemoteDenConfig(type=DenType.MEDCATTERY,
                           host="ABC",
                           credentials={"A": "B"},
                           allow_local_fine_tune=True,
                           allow_push_fine_tuned=False,
                           )


@pytest.fixture
def cnf_allow_both():
    return RemoteDenConfig(type=DenType.MEDCATTERY,
                           host="ABC",
                           credentials={"A": "B"},
                           allow_local_fine_tune=True,
                           allow_push_fine_tuned=True,
                           )


@pytest.fixture
def den_disallow_all(den: LocalFileDen, cnf_disallow_all: RemoteDenConfig) -> Den:  # noqa
    # NOTE: local den with remote config
    den._cnf = cnf_disallow_all
    return den


@pytest.fixture
def den_allow_push_only(den: LocalFileDen, cnf_allow_push_only: RemoteDenConfig) -> Den:  # noqa
    # NOTE: local den with remote config
    den._cnf = cnf_allow_push_only
    return den


@pytest.fixture
def den_allow_finetune_only(den: LocalFileDen, cnf_allow_finetune_only: RemoteDenConfig) -> Den:  # noqa
    # NOTE: local den with remote config
    den._cnf = cnf_allow_finetune_only
    return den


def test_can_normally_push(def_model_pack: CAT, den: LocalFileDen):  # noqa
    model_pack = get_wrapped_model_pack(
        def_model_pack, den._cnf)
    with injected_den(lambda: den, inject_save=True):
        # do some training
        model_pack.trainer.train_unsupervised(UNSUP_TRAIN_EXAMPLE)
        # should be able to just send to den
        model_pack.save_model_pack("Did some fine-tuning")



def test_can_disallow_push_all(def_model_pack: CAT, den_disallow_all: LocalFileDen):  # noqa
    model_pack = get_wrapped_model_pack(
        def_model_pack, den_disallow_all._cnf)
    with injected_den(lambda: den_disallow_all, inject_save=True):
        # do some training
        model_pack.trainer.train_unsupervised(UNSUP_TRAIN_EXAMPLE)
        # attempt to save to den
        with pytest.raises(CannotSendToRemoteException):
            model_pack.save_model_pack("Did some fine-tuning")


def test_can_disallow_save_finetune_only(def_model_pack: CAT, den_allow_finetune_only: LocalFileDen):  # noqa
    model_pack = get_wrapped_model_pack(
        def_model_pack, den_allow_finetune_only._cnf)
    with injected_den(lambda: den_allow_finetune_only, inject_save=True):
        # do some training
        model_pack.trainer.train_unsupervised(UNSUP_TRAIN_EXAMPLE)
        # attempt to save to den
        with pytest.raises(CannotSendToRemoteException):
            model_pack.save_model_pack("Did some fine-tuning")



def test_can_normally_fine_tune(def_model_pack: CAT, den: LocalFileDen):  # noqa
    model_pack = get_wrapped_model_pack(
        def_model_pack, den._cnf)
    with injected_den(lambda: den, inject_save=True):
        # should be able to just do some supervised training
        model_pack.trainer.train_supervised_raw({"projects": []})


def test_can_disallow_fine_tune_all(def_model_pack: CAT, den_disallow_all: LocalFileDen):  # noqa
    model_pack = get_wrapped_model_pack(
        def_model_pack, den_disallow_all._cnf)
    with injected_den(lambda: den_disallow_all, inject_save=True):
        # attempt to save do supervised training
        with pytest.raises(NotAllowedToFineTuneLocallyException):
            model_pack.trainer.train_supervised_raw({"projects": []})


def test_can_disallow_fine_tune_push_only(def_model_pack: CAT, den_allow_push_only: LocalFileDen):  # noqa
    model_pack = get_wrapped_model_pack(
        def_model_pack, den_allow_push_only._cnf)
    with injected_den(lambda: den_allow_push_only, inject_save=True):
        # attempt to save do supervised training
        with pytest.raises(NotAllowedToFineTuneLocallyException):
            model_pack.trainer.train_supervised_raw({"projects": []})
            model_pack.save_model_pack("Did some fine-tuning")
