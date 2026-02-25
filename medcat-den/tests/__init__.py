import os
import atexit
import shutil

from medcat.cat import CAT


MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "resources", "mct2_model_pack.zip")
V1_MODEL_PATH = os.path.join(
    os.path.dirname(MODEL_PATH), "mct_v1_model_pack.zip"
)


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
