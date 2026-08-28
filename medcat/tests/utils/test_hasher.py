import unittest

from copy import deepcopy

from medcat.utils.hasher import Hasher


class HasherTests(unittest.TestCase):

    def setUp(self) -> None:
        self.hasher = Hasher()

    def assertHashesString(self):
        hash_value = self.hasher.hexdigest()
        self.assertIsInstance(hash_value, str)

    def test_empty_hasher_returns_string(self):
        self.assertHashesString()

    def test_hasher_can_hash_object_normal(self,
                                           to_hash=(1, '2', 'a')) -> None:
        self.hasher.update(to_hash)
        self.assertHashesString()

    def test_hasher_can_hash_object_length(self,
                                           to_hash=(1, '2', 'a')) -> None:
        self.hasher.update(to_hash, length=True)
        self.assertHashesString()

    def test_hasher_can_hash_bytes(self, to_hash=b'a32csa') -> None:
        self.hasher.update_bytes(to_hash)
        self.assertHashesString()


EXAMPLE_DICT = {"k1": "v1", "k2": {"sk1": 1, "sk2": 'two'}}
EXAMPLE_TUPLE = (1, '2', 'e2', b'23aa', 0x1359abf, 0b1011011)


class HasherPersistanceTests(unittest.TestCase):
    # the expected values recorded at time of writing
    # and they should stay consisent for a very long time

    def setUp(self) -> None:
        self.h1 = Hasher()
        self.h2 = Hasher()

    def assertHashesEqual(self, expected_hash: str):
        h1 = self.h1.hexdigest()
        h2 = self.h2.hexdigest()
        self.assertEqual(h1, h2)
        self.assertEqual(self.h1.hexdigest(), expected_hash)
        self.assertEqual(self.h2.hexdigest(), expected_hash)

    def add_and_check(self, add1, add2, add_type: str = 'normal',
                      expected_hash: str = ''):
        if add_type == 'normal':
            self.h1.update(add1)
            self.h2.update(add2)
        elif add_type == 'length':
            self.h1.update(add1, length=True)
            self.h2.update(add2, length=True)
        elif add_type == 'bytes':
            self.h1.update_bytes(add1)
            self.h2.update_bytes(add2)
        else:
            raise ValueError(f"Unknown add type: {add_type}")
        self.assertHashesEqual(expected_hash)

    def test_empty_consistent(self):
        self.assertHashesEqual('ef46db3751d8e999')

    def test_add_same_consistent(self, add='object',
                                 expected_hash='d217e6ff5cffb338'):
        self.add_and_check(add, add, add_type='normal',
                           expected_hash=expected_hash)

    def test_add_same_consistent_length(self, add=312,
                                        expected_hash='e7c539dc2781ec25'):
        self.add_and_check(add, add, add_type='length',
                           expected_hash=expected_hash)

    def test_add_same_consistent_bytes(self, add=b'53abc',
                                       expected_hash='a1de155e3ceca068'):
        self.add_and_check(add, add, add_type='bytes',
                           expected_hash=expected_hash)

    def test_hashes_identical_consistent_dict(self, add1=EXAMPLE_DICT,
                                              expected_hash='d2c45556c3b4f2c0'
                                              ):
        add2 = deepcopy(add1)
        self.add_and_check(add1, add2, add_type='normal',
                           expected_hash=expected_hash)

    def test_hashes_identical_consistent_dict_length(
            self, add1=EXAMPLE_DICT,
            expected_hash='92e1e77ffeaf65ed'
            ):
        add2 = deepcopy(add1)
        self.add_and_check(add1, add2, add_type='length',
                           expected_hash=expected_hash)

    def test_hashes_identical_consistent_tuple(
            self, add1=EXAMPLE_TUPLE,
            expected_hash='d2cb48c4d74e6fd2'):
        add2 = deepcopy(add1)
        self.add_and_check(add1, add2, add_type='normal',
                           expected_hash=expected_hash)

    def test_hashes_identical_consistent_tuple_length(
            self, add1=EXAMPLE_TUPLE,
            expected_hash='6ea84233651fcd2e'):
        add2 = deepcopy(add1)
        self.add_and_check(add1, add2, add_type='length',
                           expected_hash=expected_hash)
