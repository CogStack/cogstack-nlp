from unittest import TestCase

import warnings
import importlib

from medcat.config import config
from medcat.config import config_meta_cat
from medcat.config import config_rel_cat
from medcat.config import config_transformers_ner


class TestConfigImportHasNoWarnings(TestCase):
    pkg = config

    def test_has_no_warnings(self):
        # ensure import emits no warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Trigger import or reload if needed
            importlib.reload(self.pkg)
        # if *any* warnings were emitted, fail with details
        self.assertFalse(w, "Should have no warninings")


class TestConfigMetaCATImportHasNoWarnings(TestConfigImportHasNoWarnings):
    pkg = config_meta_cat


class TestConfigRelCATImportHasNoWarnings(TestConfigImportHasNoWarnings):
    pkg = config_rel_cat


class TestConfigTrfNerImportHasNoWarnings(TestConfigImportHasNoWarnings):
    pkg = config_transformers_ner
