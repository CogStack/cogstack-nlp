from medcat.utils.legacy import identifier

from unittest import TestCase

from ... import UNPACKED_EXAMPLE_MODEL_PACK_PATH as v2_model_pack_path
from ... import UNPACKED_V1_MODEL_PACK_PATH as v1_model_pack_path


class CanIdentifyLegacyModelPackTests(TestCase):
    def test_can_identify_legacy_model_pack(self):
        self.assertTrue(identifier.is_legacy_model_pack(v1_model_pack_path))

    def test_can_identify_v2_model_pack(self):
        self.assertFalse(identifier.is_legacy_model_pack(v2_model_pack_path))
