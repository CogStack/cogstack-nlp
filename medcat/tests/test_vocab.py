import os

from medcat.vocab import Vocab
from medcat.storage.serialisers import get_serialiser, deserialise

import numpy as np

import unittest
import tempfile

from . import UNPACKED_EXAMPLE_MODEL_PACK_PATH, RESOURCES_PATH
from . import UNPACKED_V1_MODEL_PACK_PATH


ZIPPED_VOCAB_PATH = os.path.join(RESOURCES_PATH, "mct2_vocab.zip")


class VocabCreationTests(unittest.TestCase):
    word1 = {
        "word": "WORD1", "cnt": 1,
    }
    word2 = {
        "word": "WORD2", "cnt": 1,
        "vec": np.array([0,   100, 100]),
    }
    word3 = {
        "word": "WORD3", "cnt": 1,
        "vec": np.array([100,   0, 100]),
        "replace": True,
    }
    word4 = {
        "word": "WORD4", "cnt": 1,
        "vec": np.array([100, 100,   0]),
        "replace": False,
    }
    word5 = {
        "word": "WORD5", "cnt": 3,
        "vec": None,
        "replace": False
    }
    word6 = {
        "word": "WORD6", "cnt": 10,
        "vec": np.array([50,  50,  25]),
        "replace": False
    }
    all_words = [
        word1, word2, word3, word4,
        # for negative sampling stuff
        word5, word6
    ]

    def setUp(self):
        self._temp_file = tempfile.NamedTemporaryFile()
        self.temp_file = self._temp_file.name
        self.vocab = Vocab()

    def tearDown(self):
        self._temp_file.close()

    def test_does_not_have_words_by_default(self):
        for word in self.all_words:
            self.assertNotIn(word["word"], self.vocab)

    def test_remembers_words(self):
        for word in self.all_words:
            self.vocab.add_word(**word)
            self.assertIn(word["word"], self.vocab)

    def test_can_overwrite_word(self):
        word = self.word3.copy()  # allows to overwrite
        self.vocab.add_word(**word)
        word_cp = word.copy()
        word_cp["vec"] = 2 * word["vec"]
        self.vocab.add_word(**word_cp)
        got_vec = self.vocab.vec(word["word"])
        self.assertTrue(np.all(got_vec == word_cp["vec"]))


class VocabSaveTests(unittest.TestCase):
    serialiser = get_serialiser('dill')
    all_words = VocabCreationTests.all_words

    @classmethod
    def setUpClass(cls):
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.target_file = os.path.join(cls._temp_dir.name, "vocab.dat")
        cls.vocab = Vocab()
        for word in cls.all_words:
            cls.vocab.add_word(**word)

    @classmethod
    def tearDownClass(cls):
        cls._temp_dir.cleanup()

    def _serialise_default(self):
        self.serialiser.serialise(self.vocab, self.target_file)

    def test_can_serialise(self):
        self._serialise_default()
        self.assertTrue(os.path.exists(self.target_file))

    def assert_equal_dicts(self, d1: dict, d2: dict, path: str = '') -> None:
        keys1, keys2 = d1.keys(), d2.keys()
        if keys1 != keys2:
            raise AssertionError(
                f"Incompatible keys for vocabs: {keys1} vs {keys2}")
        for k, v1 in d1.items():
            v2 = d2[k]
            if isinstance(v2, dict):
                self.assert_equal_dicts(v1, v2,  f"{path}.{k}" if path else k)
                continue
            if isinstance(v1, np.ndarray) or isinstance(v2, np.ndarray):
                is_eq = np.all(v1 == v2)
            else:
                is_eq = v1 == v2
            if not is_eq:
                raise AssertionError(
                    f"Incompatible values for {k}: {v1} vs {v2}")

    def assert_vocab_equals(self, vocab1: Vocab, vocab2: Vocab):
        self.assert_equal_dicts(vocab1.__dict__, vocab2.__dict__)

    def test_can_deserialise(self):
        self._serialise_default()
        loaded = self.serialiser.deserialise(self.target_file)
        self.assertIsInstance(loaded, Vocab)
        self.assert_vocab_equals(self.vocab, loaded)

    def test_deserialised_has_all_words(self):
        self._serialise_default()
        vocab = self.serialiser.deserialise(self.target_file)
        for word in self.all_words:
            with self.subTest(word):
                self.assertIn(word["word"], vocab)


class VocabTests(unittest.TestCase):
    serialiser = get_serialiser('dill')
    all_words = VocabCreationTests.all_words

    @classmethod
    def setUpClass(cls):
        cls.vocab = Vocab()
        for word in cls.all_words:
            cls.vocab.add_word(**word)
        cls.vocab.init_cumsums()

    def test_neg_sampling_gets_list_of_ints(self, num_to_get: int = 10):
        neg_samples = self.vocab.get_negative_samples(num_to_get)
        self.assertIsInstance(neg_samples, list)
        self.assertEqual(len(neg_samples), num_to_get)
        for inum, index in enumerate(neg_samples):
            with self.subTest(f"INDEX: {index} @ {inum}"):
                self.assertIsInstance(index, int)

    def test_neg_sampling_does_not_include_vectorless(
            self, num_to_get: int = 30):
        inds = self.vocab.get_negative_samples(num_to_get)
        for index in inds:
            with self.subTest(f"Index: {index}"):
                # in the right list
                self.assertIn(index, self.vocab.vec_index2word)
                word = self.vocab.vec_index2word[index]
                info = self.vocab.vocab[word]
                # the info has vector
                self.assertIn("vector", info)
                # the vector is an array or a list
                self.assertIsInstance(self.vocab.vec(word), (np.ndarray, list))


class DefaultVocabTests(unittest.TestCase):
    VOCAB_PATH = os.path.join(UNPACKED_EXAMPLE_MODEL_PACK_PATH, 'vocab')
    LEGACY_VOCAB_PATH = os.path.join(UNPACKED_V1_MODEL_PACK_PATH, "vocab.dat")
    EXP_SHAPE = (7,)

    @classmethod
    def setUpClass(cls):
        cls.vocab: Vocab = deserialise(cls.VOCAB_PATH)

    # NOTE: the MCTv1 vocab has a vector (for 'chronic')
    #       that is longer than the rest (the reast are 7 length,
    #       this one is 8 length). So we want to make sure everything
    #       is in order here.
    def test_has_correct_vectors(self):
        for w, info in self.vocab.vocab.items():
            with self.subTest(w):
                self.assertEqual(info['vector'].shape, self.EXP_SHAPE)

    def test_convenience_save(self):
        with tempfile.TemporaryDirectory() as dir:
            self.vocab.save(dir)
            self.assertTrue(os.path.exists(dir))
            obj = deserialise(dir)
            self.assertIsInstance(obj, Vocab)

    def test_convenience_load(self):
        vocab = Vocab.load(self.VOCAB_PATH)
        self.assertIsInstance(vocab, Vocab)

    def test_can_load_from_zip(self):
        vocab = Vocab.load(ZIPPED_VOCAB_PATH)
        self.assertIsInstance(vocab, Vocab)

    def test_can_convert_legacy_upon_load(self):
        loaded = Vocab.load(self.LEGACY_VOCAB_PATH)
        self.assertIsInstance(loaded, Vocab)

    def test_can_save_to_zip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_name = os.path.join(temp_dir, 'vocab.zip')
            # NOTE: auto detection will write as zip
            self.vocab.save(file_name)
            self.assertTrue(os.path.exists(file_name))
            self.assertTrue(os.path.isfile(file_name))
            # and can load from saved zip
            loaded = Vocab.load(file_name)
            self.assertIsInstance(loaded, Vocab)
