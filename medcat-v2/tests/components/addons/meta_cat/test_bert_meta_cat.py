import socket
from contextlib import contextmanager
import time
import threading

from medcat.components.addons.meta_cat import meta_cat
from medcat.storage.serialisers import serialise, deserialise

import unittest
import tempfile
import os

import transformers

from .test_meta_cat import FakeTokenizer


@contextmanager
def assert_tries_network():
    real_socket = socket.socket
    calls = []

    def guard(*args, **kwargs):
        calls.append((len(args), len(kwargs)))
        raise OSError("Network disabled for test")

    socket.socket = guard
    try:
        yield
    finally:
        socket.socket = real_socket
        assert calls, "No network calls were made during the test"


# NOTE: need to disable the usage of the cache
#       otherwise other parts of the test suite
#       might have already downloaded and cached
#       the model and no network calls may be made
#       in such a situation
@contextmanager
def force_hf_download():
    with tempfile.TemporaryDirectory() as temp_dir:
        with _force_hf_download(temp_dir):
            yield


@contextmanager
def _force_hf_download(temp_dir_path: str):
    orig_from_pretrained = transformers.BertModel.from_pretrained

    method_calls = []

    def replacement_method(*args, **kwargs):
        method_calls.append((len(args), len(kwargs)))
        return orig_from_pretrained(
            *args, force_download=True,
            cache_dir=temp_dir_path, **kwargs)
    transformers.BertModel.from_pretrained = replacement_method
    try:
        yield
    finally:
        transformers.BertModel.from_pretrained = orig_from_pretrained
        assert method_calls, "BertModel.from_pretrained should be called"


class BERTMetaCATTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cnf = meta_cat.ConfigMetaCAT()
        cls.cnf.model.model_name = 'bert'
        cls.cnf.general.vocab_size = 10
        cls.cnf.model.padding_idx = 5
        cls.cnf.general.tokenizer_name = 'bert-tokenizer'
        cls.cnf.model.model_variant = 'prajjwal1/bert-tiny'
        cls.cnf.general.category_name = 'FAKE_category'
        cls.cnf.general.category_value2id = {
            'Future': 0, 'Past': 2, 'Recent': 1}
        cls.tokenizer = FakeTokenizer()
        cls.meta_cat = meta_cat.MetaCATAddon.create_new(cls.cnf, cls.tokenizer)

        cls.temp_dir = tempfile.TemporaryDirectory()
        # change model variant to force a network call upon load
        cls.cnf.model.model_variant = 'prajjwal1/bert-small'
        cls.mc_save_path = os.path.join(cls.temp_dir.name, "bert_meta_cat")
        serialise('dill', cls.meta_cat, cls.mc_save_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_no_network_load(self):
        import threading
        import sys
        import os

        print("=== DEBUG: Environment ===")
        print(f"CI: {os.getenv('CI')}")
        print(f"GITHUB_ACTIONS: {os.getenv('GITHUB_ACTIONS')}")
        print(f"Python version: {sys.version}")
        print(f"Transformers version: {transformers.__version__}")
        print(f"Initial thread count: {threading.active_count()}")
        print(f"Initial threads: {[t.name for t in threading.enumerate()]}")

        from medcat.tokenizing.spacy_impl.tokenizers import SpacyTokenizer
        from medcat.config import Config
        cnf = Config()
        nlp = cnf.general.nlp
        tokenizer = SpacyTokenizer("en_core_web_md",
                                   nlp.disabled_components,
                                   False,
                                   1_000_000)
        with assert_tries_network():
            with force_hf_download():
                print("=== DEBUG: Before deserialise ===")
                print(f"Thread count: {threading.active_count()}")
                mc = deserialise(self.mc_save_path)
                # NOTE: the network calls are done async
                #       and as such we may need to wait for them
                #       to be done before we exit the context managers,
                print("=== DEBUG: After deserialise ===")
                print(f"Thread count: {threading.active_count()}")
                print(f"Current threads: {[t.name for t in threading.enumerate()]}")
                wait_time = 5.0 if os.getenv('CI') else 1.0
                print(f"=== DEBUG: Waiting {wait_time}s for background threads ===")
                time.sleep(wait_time)
                print("=== DEBUG: After wait ===")
                print(f"Thread count: {threading.active_count()}")

                self.assertIsInstance(mc, meta_cat.MetaCATAddon)
                mc: meta_cat.MetaCATAddon
                doc = tokenizer("Some Text With Something")
                ent = doc[2:4]
                ent.detected_name = 'something'
                ent.link_candidates = ['s', 'ome', 'thing']
                ent.confidence = ent.context_similarity = 0.95
                ent.cui = 'C123'
                ent.id = 0
                doc.ner_ents = [ent]
                doc.linked_ents = [ent]
                mc(doc)
                self.assertTrue(ent.has_addon_data(meta_cat._META_ANNS_PATH))
                print("=== DEBUG: After usage ===")
                print(f"Thread count: {threading.active_count()}")
