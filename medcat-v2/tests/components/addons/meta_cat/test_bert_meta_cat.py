import socket
from contextlib import contextmanager

from medcat.components.addons.meta_cat import meta_cat
from medcat.storage.serialisers import serialise, deserialise

import unittest
import tempfile
import os

from .test_meta_cat import FakeTokenizer


@contextmanager
def no_network():
    real_socket = socket.socket

    def guard(*args, **kwargs):
        raise OSError("Network disabled for test")

    socket.socket = guard
    try:
        yield
    finally:
        socket.socket = real_socket


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
        cls.mc_save_path = os.path.join(cls.temp_dir.name, "bert_meta_cat")
        serialise('dill', cls.meta_cat, cls.mc_save_path)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_no_network_load(self):
        with no_network():
            mc = deserialise(self.mc_save_path)
        self.assertIsInstance(mc, meta_cat.MetaCATAddon)
