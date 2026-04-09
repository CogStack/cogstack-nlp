import os
import json

from medcat.tokenizing.tokens import MutableDocument
from medcat.trainer import Trainer
from medcat.config import Config
from medcat.vocab import Vocab
from medcat.data.mctexport import MedCATTrainerExport

import unittest
import unittest.mock

import random
import pandas as pd

from .pipeline.test_pipeline import FakeCDB as BFakeCDB
from .utils.legacy.test_convert_config import TESTS_PATH
from .test_cat import TrainedModelTests


class FakeCDB(BFakeCDB):

    def __init__(self, config):
        super().__init__(config)

    def _add_concept(self, *args, **kwargs) -> None:
        pass


class FakeMutToken:

    def __init__(self, doc: 'FakeMutDoc',
                 index: int, start_char_index: int,
                 end_char_index: int) -> None:
        self.index = index
        self.char_index = start_char_index
        self.text = doc.text[start_char_index: end_char_index]
        self.to_skip = False
        self.base = self

    @property
    def lower(self):
        return self.text.lower()


class FakeMutEnt:

    def __init__(self, doc: 'FakeMutDoc',
                 start_index: int, end_index: int):
        self.doc = doc
        self.start_index = start_index
        self.end_index = end_index
        self.to_skip = False
        self.base = self
        self.text = doc.text

    @property
    def lower(self) -> str:
        return self.text.lower()


class FakeMutDoc:

    def __init__(self, text: str):
        self.text = text
        self.base = self
        self.ner_ents = []
        self.linked_ents = []

    def isupper(self) -> bool:
        return self.text.isupper()

    def get_tokens(self, start_index: int, end_index: int, chars_per_tkns: int = 5):
        return [
            FakeMutToken(self, (cstart // chars_per_tkns), cstart, cstart + chars_per_tkns)
            for cstart in range(start_index, end_index, chars_per_tkns)
        ]

    def __iter__(self):
        yield from self.get_tokens(0, len(self.text))


class FakeComponent:
    pass


class FakePipeline:

    def tokenizer(self, text: str) -> FakeMutDoc:
        return FakeMutDoc(text)

    def tokenizer_with_tag(self, text: str) -> FakeMutDoc:
        return FakeMutDoc(text)

    def get_component(self, comp_type):
        return FakeComponent

    def entity_from_tokens_in_doc(self, tkns: list, doc: MutableDocument) -> FakeMutEnt:
        return FakeMutEnt(doc, tkns[0].index, tkns[-1].index)


class TrainerTestsBase(unittest.TestCase):
    DATA_CNT = 14
    TRAIN_DATA = [
        "TEXT#{num}" for num in range(DATA_CNT)
    ]
    DATA_GEN = (dp for dp in TRAIN_DATA)

    @classmethod
    def setUpClass(cls):
        cls.cnf = Config()
        cls.cdb = FakeCDB(cls.cnf)
        cls.vocab = Vocab()
        cls.trainer = Trainer(cls.cdb,
                              cls.caller, FakePipeline())

    def setUp(self):
        self.cnf = Config()
        self.cdb.config = self.cnf
        self.trainer.config = self.cnf

    @classmethod
    def caller(cls, text: str):
        return FakeMutDoc(text)

    @classmethod
    def unlinker(cls, *args, **kwargs):
        return

    @classmethod
    def adder(cls, *args, **kwargs):
        return

    def assert_remembers_training_data(self,
                                       num_docs: int,
                                       num_epochs: int,
                                       unsup: bool = True,
                                       exp_total: int = 1):
        if unsup:
            trained = self.cnf.meta.unsup_trained
        else:
            trained = self.cnf.meta.sup_trained
        self.assertEqual(len(trained), exp_total)
        last_trained = trained[0]
        self.assertEqual(last_trained.num_docs, num_docs)
        self.assertEqual(last_trained.num_epochs, num_epochs)


class TrainerUnsupervisedTests(TrainerTestsBase):
    NEPOCHS = 1
    UNSUP = True

    def train(self, data):
        if self.UNSUP:
            return self.trainer.train_unsupervised(data, nepochs=self.NEPOCHS)
        else:
            return self.trainer.train_supervised_raw(data)

    def test_training_gets_remembered_list(self):
        self.train(self.TRAIN_DATA)
        self.assert_remembers_training_data(self.DATA_CNT, self.NEPOCHS,
                                            unsup=self.UNSUP)

    def test_training_gets_remembered_gen(self):
        self.train(self.DATA_GEN)
        self.assert_remembers_training_data(self.DATA_CNT, self.NEPOCHS,
                                            unsup=self.UNSUP)

    def test_training_gets_remembered_multi(self, repeats: int = 3):
        for _ in range(repeats):
            self.train(self.TRAIN_DATA)
        self.assert_remembers_training_data(self.DATA_CNT, self.NEPOCHS,
                                            exp_total=repeats,
                                            unsup=self.UNSUP)


class TrainerSupervisedTests(TrainerUnsupervisedTests):
    DATA_CNT = 1
    UNSUP = False
    TRAIN_DATA: MedCATTrainerExport = {
        "projects": [
            {
                'cuis': '',
                'tuis': '',
                'documents': [
                    {
                        'id': "P1D1",
                        'name': "Project#1Doc#1",
                        'last_modified': 'N/A',
                        'text': 'Some long text',
                        'annotations': [
                            {
                                'cui': "C1",
                                'start': 0,
                                'end': 4,
                                'value': 'SOME',
                            }
                        ]
                    }
                ],
                'id': "PID#1",
                'name': "PROJECT#1",
            }
        ]
    }
    TRAIN_DATA_MULTI: MedCATTrainerExport = {
        "projects": [
            *TRAIN_DATA['projects'],
            {
                'cuis': '',
                'tuis': '',
                'documents': [
                    {
                        'id': "P2D1",
                        'name': "Project#2Doc#1",
                        'last_modified': 'N/A',
                        'text': 'Some long text',
                        'annotations': [
                            {
                                'cui': "C1",
                                'start': 0,
                                'end': 4,
                                'value': 'SOME',
                            }
                        ]
                    }
                ],
                'id': "PID#2",
                'name': "PROJECT#2",
            }
        ]
    }

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_training_gets_remembered_gen(self):
        pass  # NOTE: no generation for supervised training

    def test_trains_all_projects(self):
        with unittest.mock.patch.object(self.trainer, "_train_supervised_for_project") as mock_train_project:
            self.train(self.TRAIN_DATA_MULTI)
        self.assertTrue(mock_train_project.call_count, 2)

    def test_training_happens_on_linked_ents_on_doc(self):
        with unittest.mock.patch.object(self.trainer, "add_and_train_concept") as mock_add_and_train_concept:
            self.train(self.TRAIN_DATA)
        for num, args in enumerate(mock_add_and_train_concept.call_args_list):
            with self.subTest(str(num)):
                mock_add_and_train_concept.assert_called()
                doc, ent = args.kwargs['mut_doc'], args.kwargs['mut_entity']
                self.assertIn(ent, doc.linked_ents)

    def test_empty_token_annotation_is_skipped_when_not_strict(self):
        self.trainer.strict_train = False
        with unittest.mock.patch.object(
                self.trainer._pipeline, "entity_from_tokens_in_doc",
                side_effect=ValueError("No tokens found in span")), \
                unittest.mock.patch.object(
                FakeMutDoc, "get_tokens", return_value=[]), \
                unittest.mock.patch.object(self.trainer, "add_and_train_concept"):
            try:
                self.train(self.TRAIN_DATA)
            except ValueError as err:
                self.fail(f"Unexpected ValueError for empty-token annotation: {err}")

    def test_empty_token_annotation_raises_when_strict(self):
        self.trainer.strict_train = True
        with unittest.mock.patch.object(
                self.trainer._pipeline, "entity_from_tokens_in_doc",
                side_effect=ValueError("No tokens found in span")), \
                unittest.mock.patch.object(
                FakeMutDoc, "get_tokens", return_value=[]), \
                unittest.mock.patch.object(self.trainer, "add_and_train_concept"):
            with self.assertRaises(ValueError):
                self.train(self.TRAIN_DATA)


class FromSratchBase(TrainedModelTests):
    RNG_SEED = 42

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model.cdb.reset_training()
        random.seed(cls.RNG_SEED)


class TrainFromScratchTests(FromSratchBase):
    UNSUP_DATA_PATH = os.path.join(
        TESTS_PATH, "resources", "selfsupervised_data.txt")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.all_words = list(cls.model.vocab.vocab.keys())
        cls.all_concepts = [(cui, cls.model.cdb.get_name(cui))
                            for cui in cls.model.cdb.cui2info]
        cls.model.trainer.train_unsupervised(cls.get_data())

    @classmethod
    def get_data(cls) -> list[str]:
        df = pd.read_csv(cls.UNSUP_DATA_PATH)
        return df['text'].tolist()

    def test_can_train_unsupervised(self):
        for cui, _ in self.all_concepts:
            with self.subTest(cui):
                self.assertGreater(
                    self.model.cdb.cui2info[cui]['count_train'], 0)


class TrainFromScratchSupervisedTests(TrainFromScratchTests):
    SUP_DATA_PATH = os.path.join(
        TESTS_PATH, "resources", "mct_export_for_test_exp_perfect.json"
    )

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cnts_before = {
            cui: info['count_train']
            for cui, info in cls.model.cdb.cui2info.items()
        }
        cls.model.trainer.train_supervised_raw(
            cls.get_sup_data()
        )

    @classmethod
    def get_sup_data(cls) -> MedCATTrainerExport:
        with open(cls.SUP_DATA_PATH) as f:
            return json.load(f)

    def test_has_trained_all(self):
        for cui, prev_count in self.cnts_before.items():
            with self.subTest(cui):
                info = self.model.cdb.cui2info[cui]
                self.assertGreater(info['count_train'], prev_count)
