from typing import runtime_checkable

from medcat.components.ner.trf import deid
from medcat.components.ner.trf.helpers import make_or_update_cdb

from medcat.tokenizing.tokenizers import create_tokenizer
from medcat.components.ner.trf import transformers_ner
from medcat.components.types import CoreComponentType
from medcat.tokenizing.tokens import MutableDocument
from medcat.config.config import Config
from medcat.cdb.cdb import CDB

from typing import Any
import os
import tempfile
import shutil

import unittest

FILE_DIR = os.path.dirname(os.path.realpath(__file__))


# NB! This 'training data' is extremely flawed
# it is only (somewhat) useful for the purpose of this
# test
# DO NOT USE THIS DATA ELSEWHERE - IT WILL NOT BE USEFUL
TRAIN_DATA = os.path.join(FILE_DIR, "..", "..",
                          "resources", "deid_train_data.json")

TEST_DATA = os.path.join(FILE_DIR, "..", "..",
                         "resources", "deid_test_data.json")

USE_CACHE_TEST_MODEL = False  # Choose True for local dev to skip train/test every run

cnf = Config()
cnf.general.nlp.provider = 'spacy'


def _get_def_cdb():
    return CDB(config=cnf)


class DeIDmodelCreationTests(unittest.TestCase):
    save_folder = os.path.join("results", "final_model")

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.save_folder):
            shutil.rmtree(cls.save_folder)

    def test_can_make_cdb(self):
        cdb = make_or_update_cdb(TRAIN_DATA, _get_def_cdb())
        self.assertIsNotNone(cdb)

    def test_can_create_model(self):
        cdb = make_or_update_cdb(TRAIN_DATA, _get_def_cdb())
        config = transformers_ner.ConfigTransformersNER()
        config.general.test_size = 0.1  # Usually set this to 0.1-0.2
        # ner = transformers_ner.TransformersNER(cdb=cdb, config=config,
        #                                        base_tokenizer=self.tokenizer)
        deid_model = deid.DeIdModel.create(cdb, config)
        self.assertIsNotNone(deid_model)


tokenizer = create_tokenizer('spacy', Config())


def _create_model() -> deid.DeIdModel:
    cdb = make_or_update_cdb(TRAIN_DATA, _get_def_cdb())
    config = transformers_ner.ConfigTransformersNER()
    config.general.test_size = 0.1  # Usually set this to 0.1-0.2
    config.general.chunking_overlap_window = None
    model = deid.DeIdModel.create(cdb, config)
    _ner = model.trf_ner
    ner = _ner._component
    ner.training_arguments.num_train_epochs = 1  # Use 5-10 normally
    # As we are NOT training on a GPU that can, we'll set it to 1
    ner.training_arguments.per_device_train_batch_size = 1
    # No need for acc
    ner.training_arguments.gradient_accumulation_steps = 1
    ner.training_arguments.per_device_eval_batch_size = 1
    # For the metric to be used for best model we pick Recall here,
    # as for deid that is most important
    ner.training_arguments.metric_for_best_model = 'eval_recall'
    return model


def _train_model_once() -> tuple[tuple[Any, Any, Any], deid.DeIdModel]:
    if USE_CACHE_TEST_MODEL:
        print("Using cached model for local repeats instead of create/train each time")
        model_path = "tmp/deid_test_model.zip"
        if not os.path.exists(model_path):
            model = _create_model()
            retval = model.train(TRAIN_DATA)
            model.cat.save_model_pack("tmp", pack_name="deid_test_model",  make_archive=True)
        model = deid.DeIdModel.load_model_pack(model_path)
        return retval, model

    model = _create_model()
    retval = model.train(TRAIN_DATA)
    # mpp = 'temp/deid_multiprocess/dumps/temp_model_save'
    # NOTE: it seems that after training the model leaves
    #       it in a state where it can no longer be used
    #       for multiprocessing. So in order to avoid that
    #       we save the model on disk and load it agains
    with tempfile.TemporaryDirectory() as dir_name:
        print("Saving model on disk")
        mpn = model.cat.save_model_pack(dir_name, make_archive=False)
        model = deid.DeIdModel.load_model_pack(mpn)
        print("Loaded model off disk")
    model.trf_ner._component.training_arguments.save_strategy = 'no'
    return retval, model


_TRAINED_MODEL_AND_INFO = _train_model_once()


def train_model_once() -> tuple[tuple[Any, Any, Any], deid.DeIdModel]:
    return _TRAINED_MODEL_AND_INFO


class DeIDModelTests(unittest.TestCase):
    save_folder = os.path.join("results", "final_model")

    @classmethod
    def setUpClass(cls) -> None:
        cls.deid_model = _create_model()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.save_folder):
            shutil.rmtree(cls.save_folder)

    def test_training(self):
        df, examples, dataset = train_model_once()[0]
        self.assertIsNotNone(df)
        self.assertIsNotNone(examples)
        self.assertIsNotNone(dataset)

    def test_add_new_concepts(self):
        self.deid_model.add_new_concepts({'CONCEPT': "Concept"},
                                         with_random_init=True)
        self.assertTrue("CONCEPT" in self.deid_model.cat.cdb.cui2info)
        self.assertEqual(self.deid_model.cat.cdb.cui2info["CONCEPT"]['names'],
                         {"concept"})
        tner = self.deid_model.cat._pipeline.get_component(
            CoreComponentType.ner)._component
        self.assertIn("CONCEPT", tner.model.config.label2id)
        self.assertIn("CONCEPT", tner.tokenizer.label_map)
        self.assertIn("CONCEPT", tner.tokenizer.cui2name)


input_text = '''
James Joyce 
7 Eccles Street, 
Dublin
CC: Memory difficulty.

HX: Mr James is a 64 y/o RHM, had difficulty remembering names, phone numbers and events for 12 months prior to presentation, on 2/28/95. He had visited London recently and had had no professional or social faux pas or mishaps due to his memory. J.J. could not tell whether his problem was becoming worse, so he brought himself to the Neurology clinic on his own referral. 

FHX: Both parents (Mary and John) experienced memory problems in their ninth decades, but not earlier. 5 siblings have had no memory trouble. There are no neurological illnesses in his family.

SHX: Writer and Poet. Tobacco/ETOH/illicit drug use.

The rest of the neurologic exam was unremarkable and there were no extrapyramidal signs or primitive reflexes noted.
11/1996 in Dublin.

The findings indicated multiple areas of cerebral dysfunction. With the exception of the patient's report of minimal occupational dysfunction ( which may reflect poor insight), the clinical picture is consistent with a progressive dementia syndrome such as Alzheimer disease. MRI brain, 3/6/95, showed mild generalized atrophy, more severe in the occipital-parietal regions.

Seen by Dr. M. Sully on 11/11/1996.
'''  # noqa


class DeIDModelWorks(unittest.TestCase):
    save_folder = os.path.join("results", "final_model")

    @classmethod
    def setUpClass(cls) -> None:
        cls.deid_model = train_model_once()[1]
        # import torch
        # torch.set_num_threads(1)

    def tearDown(self):
        if os.path.exists(self.save_folder):
            shutil.rmtree(self.save_folder)

    def assert_deid_annotations(self, anon_text: str):
        self.assertIn("[DOCTOR]", anon_text)
        self.assertNotIn("M. Sully", anon_text)
        self.assertIn("[HOSPITAL]", anon_text)
        # self.assertNotIn("Dublin", anon_text)
        self.assertNotIn("7 Eccles Street", anon_text)

    def assert_deid_redact(self, anon_text: str):
        self.assertIn("****", anon_text)
        self.assertNotIn("[DOCTOR]", anon_text)
        self.assertNotIn("M. Sully", anon_text)
        self.assertNotIn("[HOSPITAL]", anon_text)
        # self.assertNotIn("Dublin", anon_text)
        self.assertNotIn("7 Eccles Street", anon_text)

    def test_model_works_deid_text(self):
        anon_text = self.deid_model.deid_text(input_text)
        self.assert_deid_annotations(anon_text)

    def test_model_works_dunder_call(self):
        anon_doc = self.deid_model(input_text)
        self.assertIsInstance(anon_doc, runtime_checkable(MutableDocument))
        self.assertTrue(anon_doc.ner_ents)

    def test_model_works_deid_text_redact(self):
        anon_text = self.deid_model.deid_text(input_text, redact=True)
        self.assert_deid_redact(anon_text)

    def test_model_works_deid_multi_text_single_threaded(self):
        processed = self.deid_model.deid_multi_texts([input_text, input_text],
                                                     n_process=1)
        self.assertEqual(len(processed), 2)
        for anon_text in processed:
            self.assert_deid_annotations(anon_text)

    def test_model_works_deid_multi_text_single_threaded_redact(self):
        processed = self.deid_model.deid_multi_texts([input_text, input_text],
                                                     n_process=1, redact=True)
        self.assertEqual(len(processed), 2)
        for anon_text in processed:
            self.assert_deid_redact(anon_text)

    # @timeout_decorator.timeout(3 * 60)  # 3 minutes max
    @unittest.skip("Deid Multiprocess is broken. Exits the process, no errors shown")
    def test_model_can_multiprocess_no_redact(self):

        processed = self.deid_model.deid_multi_texts(
            [input_text, input_text], n_process=2)
        self.assertEqual(len(processed), 2)
        for tid, new_text in enumerate(processed):
            with self.subTest(str(tid)):
                self.assert_deid_annotations(new_text)

    # @timeout_decorator.timeout(3 * 60)  # 3 minutes max
    @unittest.skip("Deid Multiprocess is broken. Exits the process, no errors shown.")
    def test_model_can_multiprocess_redact(self):
        """ 
         deid_multi_text is broken for n_process >1.
         Issue: Running this just exits the whole process, no errors or exceptions shown
         """
        try:
            print("Calling test_model_can_multiprocess_redact")
            processed = self.deid_model.deid_multi_texts(
                [input_text, input_text], n_process=2, redact=True
            )
            print("Finished processing")
            self.assertEqual(len(processed), 5)
            for tid, new_text in enumerate(processed):
                with self.subTest(str(tid)):
                    self.assert_deid_redact(new_text)
        except Exception as e:
            self.fail(f"Multiprocessing redact test raised an exception: {e}")
