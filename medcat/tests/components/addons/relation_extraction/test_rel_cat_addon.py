import logging

from medcat.cat import CAT
from medcat.components.addons.addons import AddonComponent
from medcat.components.addons.relation_extraction.rel_cat import (
    RelCATAddon)
from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.storage.serialisers import ManualSerialisable

import unittest
import unittest.mock

from .... import UNPACKED_EXAMPLE_MODEL_PACK_PATH


class RelCATAddonTests(unittest.TestCase):
    EXAMPLE_TEXT = (
        "The patient had a puncture would in their left thigh"
    )

    @classmethod
    def setUpClass(cls):
        cls.cat = CAT.load_model_pack(UNPACKED_EXAMPLE_MODEL_PACK_PATH)
        cls.cnf = ConfigRelCAT()
        cls.cnf.general.device = "cpu"
        cls.cnf.general.model_name = "bert-base-uncased"
        cls.cnf.train.batch_size = 1
        cls.cnf.train.nclasses = 3
        cls.cnf.model.hidden_size = 256
        cls.cnf.model.model_size = 2304
        cls.cnf.general.log_level = logging.DEBUG
        cls.rel_cat = RelCATAddon.create_new(
            cls.cnf, cls.cat._pipeline.tokenizer, cls.cat.cdb)
        cls.cat.add_addon(cls.rel_cat)

    def test_is_addon(self):
        self.assertIsInstance(self.rel_cat, AddonComponent)

    def test_is_manually_serialisable(self):
        self.assertIsInstance(self.rel_cat, ManualSerialisable)

    def test_rel_cat_runs(self):
        with unittest.mock.patch(
            'medcat.components.addons.relation_extraction.'
                'rel_cat.RelCAT.__call__') as mock_method:
            self.cat(self.EXAMPLE_TEXT)
        mock_method.assert_called_once()
