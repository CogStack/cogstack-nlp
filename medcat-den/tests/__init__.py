import os
import atexit
import shutil

from medcat.cat import CAT

from .resource_fetch import get_resource

MODEL_PATH = get_resource("mct2_model_pack.zip", 'medcat_den')
V1_MODEL_PATH = get_resource("mct_v1_model_pack.zip", 'medcat_den')


# unpack
_model_folder = CAT.attempt_unpack(MODEL_PATH)
_v1_model_folder = CAT.attempt_unpack(V1_MODEL_PATH)


def remove_model_folder():
    if os.path.exists(_model_folder):
        shutil.rmtree(_model_folder)
    if os.path.exists(_v1_model_folder):
        shutil.rmtree(_v1_model_folder)


# cleanup
atexit.register(remove_model_folder)
