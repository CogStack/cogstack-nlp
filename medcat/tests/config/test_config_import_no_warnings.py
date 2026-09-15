from unittest import TestCase

import sys
import subprocess


def _import_in_subprocess(module_name: str):
    code = f"""
import warnings, importlib
with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    importlib.import_module('{module_name}')
    assert not w
    """
    res = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True)
    res.check_returncode()
    return res.stdout


class TestConfigImportHasNoWarnings(TestCase):
    pkg = "medcat.config.config"

    def test_has_no_warnings(self):
        _import_in_subprocess(self.pkg)


class TestConfigMetaCATImportHasNoWarnings(TestConfigImportHasNoWarnings):
    pkg = "medcat.config.config_meta_cat"


class TestConfigRelCATImportHasNoWarnings(TestConfigImportHasNoWarnings):
    pkg = "medcat.config.config_rel_cat"


class TestConfigTrfNerImportHasNoWarnings(TestConfigImportHasNoWarnings):
    pkg = "medcat.config.config_transformers_ner"
