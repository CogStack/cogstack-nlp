from typing import runtime_checkable

from medcat.preprocessors import cleaners
from medcat.config.config import General, Preprocessing, CDBMaker

import unittest


class AbstractionTests(unittest.TestCase):
    to_check = [
        (cleaners.LGeneral, General),
        (cleaners.LPreprocessing, Preprocessing),
        (cleaners.LCDBMaker, CDBMaker),
    ]

    def test_config_fits_local_config(self):
        for protocol, implementation in self.to_check:
            with self.subTest(implementation.__name__):
                self.assertIsInstance(implementation(),
                                      runtime_checkable(protocol))
