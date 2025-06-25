import os

from medcat.components.addons.relation_extraction import rel_cat
from medcat.utils.legacy.convert_rel_cat import get_rel_cat_from_old
from medcat.tokenizing.tokenizers import create_tokenizer
from medcat.storage.serialisers import AvailableSerialisers
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.config import Config

import unittest
import tempfile
import shutil
from urllib import request as url_request

from .... import UNPACKED_EXAMPLE_MODEL_PACK_PATH


S3_RELCAT_PATH = (
    "https://cogstack-medcat-example-models.s3.eu-west-2.amazonaws.com/"
    "medcat-example-models/ade_relcat_model_smaller.zip")


class LoadedRelCATTests(unittest.TestCase):
    SER_TYPE = AvailableSerialisers.dill
    temp_dir = tempfile.TemporaryDirectory()
    _model_pack_folder_name = 'rel_cat_model_pack'
    # model_pack_path = os.path.join(temp_dir.name, _model_pack_folder_name)
    _rel_cat_zip_path = os.path.join(temp_dir.name, "ade_relcat_model.zip")
    _unpacked_v1_rel_cat_path = os.path.join(temp_dir.name, "ade_relcat_model")
    # model_rel_cat_path = os.path.join(model_pack_path, "addon_rel_cat.DRUG-DOSE_DRUG-AE")

    @classmethod
    def setUpClass(cls):
        # # make the model pack path
        # os.makedirs(cls.model_pack_path)
        # # copy stuff from unpacked exmaple model pack
        # for part in os.listdir(UNPACKED_EXAMPLE_MODEL_PACK_PATH):
        #     from_path = os.path.join(
        #         UNPACKED_EXAMPLE_MODEL_PACK_PATH, part)
        #     to_path = os.path.join(cls.model_pack_path, part)
        #     if os.path.isdir(from_path):
        #         shutil.copytree(from_path, to_path)
        #     else:
        #         shutil.copy(from_path, to_path)
        # download, extract, and copy the RelCAT model
        url_request.urlretrieve(S3_RELCAT_PATH, cls._rel_cat_zip_path)
        # NOTE: the actual context will be in the ade_relcat_model folder
        shutil.unpack_archive(cls._rel_cat_zip_path, cls.temp_dir.name)
        # convert legacy (v1) to v2 RelCAT
        cnf = Config()
        cnf.general.nlp.provider = 'spacy'
        cdb = CDB(cnf)
        tokenizer = create_tokenizer("spacy", cdb.config)
        rc = get_rel_cat_from_old(cdb, cls._unpacked_v1_rel_cat_path, tokenizer)
        # add to model
        cat = CAT.load_model_pack(UNPACKED_EXAMPLE_MODEL_PACK_PATH)
        cat.add_addon(rc)
        # and save as part of model
        cls.model_pack_path = cat.save_model_pack(
            cls.temp_dir.name, cls._model_pack_folder_name).removesuffix(".zip")
        # serialise(cls.SER_TYPE, rc, cls.model_rel_cat_path)
        saved_comps_path = os.path.join(cls.model_pack_path, "saved_components")
        print("IN", saved_comps_path, ":", os.listdir(saved_comps_path))
        cls.model_rel_cat_path = [os.path.join(saved_comps_path, folder)
                                  for folder in os.listdir(saved_comps_path)
                                  if folder.startswith("addon_rel_cat")][0]
        print("Model RElCAT PATH", cls.model_rel_cat_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_can_load_rel_cat(self):
        rc = rel_cat.RelCAT.load(self.model_rel_cat_path)
        self.assertIsInstance(rc, rel_cat.RelCAT)

    def assert_has_rel_cat(self, cat: CAT):
        self.assertTrue(any(isinstance(comp, rel_cat.RelCATAddon)
                            for comp in cat._pipeline.iter_addons()))


    def test_can_load_model_pack(self):
        cat = CAT.load_model_pack(self.model_pack_path)
        self.assertIsInstance(cat, CAT)
        self.assert_has_rel_cat(cat)
