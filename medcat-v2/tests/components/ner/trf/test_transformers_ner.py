from medcat2.components.ner.trf import transformers_ner

from medcat2.storage.serialisables import ManualSerialisable

from unittest import TestCase

from ...addons.meta_cat.test_meta_cat import FakeTokenizer
from ....pipeline.test_pipeline import FakeCDB, Config


class TransformersNERTestS(TestCase):

    @classmethod
    def setUpClass(cls):
        cdb = FakeCDB(Config())
        tokenizer = FakeTokenizer()
        cls.tner = transformers_ner.TransformersNER.create_new(cdb, tokenizer)

    def test_is_manually_serialisable(self):
        self.assertIsInstance(self.tner, ManualSerialisable)
