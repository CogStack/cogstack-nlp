# NOTE: mostly copied from medcat tests
import atexit
import os
import shutil


RESOURCES_PATH = os.path.join(os.path.dirname(__file__), "resources")
EXAMPLE_MODEL_PACK_ZIP = os.path.join(RESOURCES_PATH, "mct2_model_pack.zip")
UNPACKED_EXAMPLE_MODEL_PACK_PATH = os.path.join(
    RESOURCES_PATH, "mct2_model_pack")


# unpack model pack at start so we can access stuff like Vocab
print("Unpacking included test model pack")
shutil.unpack_archive(EXAMPLE_MODEL_PACK_ZIP, UNPACKED_EXAMPLE_MODEL_PACK_PATH)


def _del_unpacked_model():
    print(
        "Cleaning up! Removing unpacked exmaple model pack:",
        UNPACKED_EXAMPLE_MODEL_PACK_PATH,
    )
    shutil.rmtree(UNPACKED_EXAMPLE_MODEL_PACK_PATH)


atexit.register(_del_unpacked_model)
