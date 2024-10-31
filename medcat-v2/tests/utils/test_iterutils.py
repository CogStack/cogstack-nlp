from typing import Generator

from medcat2.utils import iterutils

import unittest
from unittest.mock import MagicMock


class TestCallbackIterator(unittest.TestCase):
    IDENTIFIER = "test_id"

    def setUp(self):
        self.callback = MagicMock()
        self.data_with_len = list(range(12))
        self.data_without_len = (i for i in range(18))

    def test_with_len_returns_same_object(self):
        result = iterutils.callback_iterator(self.IDENTIFIER,
                                             self.data_with_len, self.callback)
        self.assertIs(result, self.data_with_len)

    def test_with_len_callback_called_before_iterating(self):
        result = iterutils.callback_iterator(self.IDENTIFIER,
                                             self.data_with_len, self.callback)
        self.callback.assert_called_once_with(self.IDENTIFIER,
                                              len(self.data_with_len))
        self.assertEqual(list(result), self.data_with_len)

    def test_without_len_callback_not_called_before_iterating(self):
        iterutils.callback_iterator(self.IDENTIFIER, self.data_without_len,
                                    self.callback)
        self.callback.assert_not_called()

    def test_without_len_callback_not_called_during_partial_iteration(self):
        result = iterutils.callback_iterator(self.IDENTIFIER,
                                             self.data_without_len,
                                             self.callback)
        _ = next(result)  # Partial iteration
        self.callback.assert_not_called()

    def test_without_len_callback_called_with_partial_count_on_exception(self):
        exp_calls = 2

        def error_prone_gen() -> Generator[int, None, None]:
            yield 1
            yield 2
            raise ValueError("Test exception")

        data_with_exception = error_prone_gen()
        result = iterutils.callback_iterator(self.IDENTIFIER,
                                             data_with_exception,
                                             self.callback)
        with self.assertRaises(ValueError):
            list(result)  # Trigger the exception
        self.callback.assert_called_once_with(self.IDENTIFIER, exp_calls)
