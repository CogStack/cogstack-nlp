from contextlib import contextmanager
from typing import runtime_checkable
from medcat.components.types import CoreComponentType
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.pipeline import pipeline
from medcat.tokenizing.tokens import MutableDocument
from medcat.vocab import Vocab
from medcat.config import Config

from ..components.ner.test_vocab_based_ner import FakeCDB as BFakeCDB

import unittest
import unittest.mock


class FakeCDB(BFakeCDB):

    def __init__(self, config):
        super().__init__(config)
        self.token_counts: dict = {}
        self.cui2info: dict = {}
        self.name2info: dict = {}

    def weighted_average_function(self, v: int) -> float:
        return v / 2.0

    def has_subname(self, sn: str) -> bool:
        return sn in self.name2info


class PipelineInitTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()
        cls.cdb = FakeCDB(cls.cnf)
        cls.vocab = Vocab()

    def test_can_create_pipeline(self):
        pf = pipeline.Pipeline(self.cdb, self.vocab, None)
        self.assertIsInstance(pf, pipeline.Pipeline)


class PipelineComponentTests(unittest.TestCase):
    text = "example text"

    @classmethod
    def setUpClass(cls):
        cls.cnf = cls._init_cnf()
        cls.cdb = FakeCDB(cls.cnf)
        cls.vocab = Vocab()
        cls.pipe = pipeline.Pipeline(cls.cdb, cls.vocab, None)

    @classmethod
    def _init_cnf(cls):
        cnf = Config()
        meta_cat_cnf = ConfigMetaCAT()
        cnf.components.addons.append(meta_cat_cnf)
        return cnf

    def test_pipe_works_normally(self):
        doc = self.pipe.get_doc(self.text)
        self.assertIsInstance(doc, runtime_checkable(MutableDocument))

    @contextmanager
    def none_returning_core_comp(
            self, cct: CoreComponentType = CoreComponentType.linking):
        linker = self.pipe.get_component(cct)
        linker_cls = linker.__class__
        orig_call = linker_cls.__call__

        def new_call(*args, **kwargs):
            orig_call(*args, **kwargs)
            return None
        with unittest.mock.patch.object(
            linker_cls, '__call__', new_call
        ):
            yield

    @contextmanager
    def none_returning_addon(self):
        addon = next(self.pipe.iter_addons())
        addon_cls = addon.__class__
        orig_call = addon_cls.__call__

        def new_call(*args, **kwargs):
            orig_call(*args, **kwargs)
            return None
        with unittest.mock.patch.object(
            addon_cls, '__call__', new_call
        ):
            yield

    def test_core_components_cannot_return_none(self):
        with self.none_returning_core_comp():
            with self.assertRaises(pipeline.IncorrectCoreComponent):
                self.pipe.get_doc(self.text)

    def test_addon_components_cannot_return_none(self):
        with self.none_returning_addon():
            with self.assertRaises(pipeline.IncorrectAddonComponent):
                self.pipe.get_doc(self.text)
