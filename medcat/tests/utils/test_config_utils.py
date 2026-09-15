from medcat.utils import config_utils
from medcat.config import Config

import unittest


class ChangedValueTests(unittest.TestCase):
    TARGET_PATH = "modelname"
    NON_DEF_VAL = "SOMETHING ELSE"

    def setUp(self):
        self._def_config = Config()
        self.config = Config()

    def cnf_part(self, config: Config):
        return config.general.nlp

    def get_value_at_path(self, cnf: Config):
        part = self.cnf_part(cnf)
        return getattr(part, self.TARGET_PATH)

    def assert_has_non_default_value(self):
        conf_val = self.get_value_at_path(self.config)
        def_val = self.get_value_at_path(self._def_config)
        self.assertNotEqual(conf_val, def_val)
        self.assertEqual(conf_val, self.NON_DEF_VAL)

    def assert_has_def_value(self):
        conf_val = self.get_value_at_path(self.config)
        def_val = self.get_value_at_path(self._def_config)
        self.assertEqual(conf_val, def_val)

    def changed_cnf(self, path_prefix: str = '',
                    path_suffix: str = ''):
        return config_utils.temp_changed_config(
            self.cnf_part(self.config),
            path_prefix + self.TARGET_PATH + path_suffix,
            self.NON_DEF_VAL)

    def test_has_changed_value(self):
        with self.changed_cnf():
            self.assert_has_non_default_value()

    def test_returns_def_value_after(self):
        with self.changed_cnf():
            pass
        self.assert_has_def_value()

    def test_fails_incorrect_path_prefix(self):
        with self.assertRaises(config_utils.IllegalConfigPathException):
            with self.changed_cnf(path_prefix='3'):
                pass

    def test_fails_incorrect_path_suffix(self):
        with self.assertRaises(config_utils.IllegalConfigPathException):
            with self.changed_cnf(path_suffix='#'):
                pass

    def test_resets_upon_exception(self):
        with self.assertRaises(ValueError):
            with self.changed_cnf():
                raise ValueError()
        self.assert_has_def_value()
