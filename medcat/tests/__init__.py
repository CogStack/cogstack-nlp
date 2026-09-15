import atexit
import os
import shutil

from .resource_fetch import get_resource


RESOURCES_PATH = os.path.join(os.path.dirname(__file__), "resources")
EXAMPLE_MODEL_PACK_ZIP = get_resource("mct2_model_pack.zip")
UNPACKED_EXAMPLE_MODEL_PACK_PATH = EXAMPLE_MODEL_PACK_ZIP.removesuffix(".zip")
V1_MODEL_PACK_PATH = get_resource("mct_v1_model_pack.zip")
UNPACKED_V1_MODEL_PACK_PATH = V1_MODEL_PACK_PATH.removesuffix(".zip")


# unpack model pack at start so we can access stuff like Vocab
print("Unpacking included test model pack")
shutil.unpack_archive(
    EXAMPLE_MODEL_PACK_ZIP, UNPACKED_EXAMPLE_MODEL_PACK_PATH)

print("Unpacking the included v1 model pack for test time")
shutil.unpack_archive(
    V1_MODEL_PACK_PATH, UNPACKED_V1_MODEL_PACK_PATH)


def _del_unpacked_model():
    print("Cleaning up! Removing unpacked exmaple model pack:",
          UNPACKED_EXAMPLE_MODEL_PACK_PATH)
    shutil.rmtree(UNPACKED_EXAMPLE_MODEL_PACK_PATH)
    shutil.rmtree(UNPACKED_V1_MODEL_PACK_PATH)


atexit.register(_del_unpacked_model)
