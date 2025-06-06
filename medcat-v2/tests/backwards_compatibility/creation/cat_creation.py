import os
import sys
import pandas as pd
import json

from medcat import __version__ as MCT_VER
from medcat.vocab import Vocab
from medcat.config import Config
from medcat.model_creation.cdb_maker import CDBMaker
from medcat.cdb import CDB
from medcat.cat import CAT


vi = sys.version_info
PY_VER = f"{vi.major}.{vi.minor}"


# paths
VOCAB_DATA_PATH = os.path.join(
    os.path.dirname(__file__), 'vocab_data.txt'
    # os.path.dirname(__file__), 'vocab_data_auto.txt'
)
CDB_PREPROCESSED_PATH = os.path.join(
    os.path.dirname(__file__), 'preprocessed4cdb.txt'
)
SELF_SUPERVISED_DATA_PATH = os.path.join(
    os.path.dirname(__file__), 'selfsupervised_data.txt'
)
SUPERVISED_DATA_PATH = os.path.join(
    os.path.dirname(__file__), 'supervised_mct_export.json'
)
SAVE_PATH = os.path.dirname(__file__)
SAVE_NAME = f"simple_model4test-{PY_VER}-{MCT_VER}"

# vocab

vocab = Vocab()
vocab.add_words(VOCAB_DATA_PATH)

# CDB
config = Config()
config.general.nlp.provider = "spacy"

maker = CDBMaker(config)

cdb: CDB = maker.prepare_csvs([CDB_PREPROCESSED_PATH])

# CAT
cat = CAT(cdb, vocab)

# training
# self-supervised
unsup_data = pd.read_csv(SELF_SUPERVISED_DATA_PATH)
cat.trainer.train_unsupervised(unsup_data.text.values)

print("[sst] cui2count_train", cat.cdb.get_cui2count_train())

# supervised

with open(SUPERVISED_DATA_PATH) as f:
    sup_data = json.load(f)

cat.trainer.train_supervised_raw(sup_data)

print("[sup] cui2count_train", cat.cdb.get_cui2count_train())

# save
full_path = cat.save_model_pack(SAVE_PATH, pack_name=SAVE_NAME,
                                only_archive=True)
print("Saved to")
print(full_path)
