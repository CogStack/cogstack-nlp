import unittest

from medcat_service.nlp_processor import MedCatProcessor
from medcat_service.test.common import setup_medcat_processor


class TestMedCatProcessorReadiness(unittest.TestCase):
    def setUp(self):
        setup_medcat_processor()
        self.processor = MedCatProcessor()

    def test_readiness_is_ok(self):
        result = self.processor._check_medcat_readiness()
        self.assertTrue(result)

    def test_readiness_is_not_ok(self):
        self.processor.cat = None
        result = self.processor._check_medcat_readiness()
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
