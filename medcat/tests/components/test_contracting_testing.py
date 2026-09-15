from unittest import TestCase
from contextlib import contextmanager

from medcat.cat import CAT
from medcat.components import contracting_testing
from medcat.utils.cdb_state import captured_state_cdb
from tests import UNPACKED_EXAMPLE_MODEL_PACK_PATH


class ContractingTestingTests(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._model = CAT.load_model_pack(UNPACKED_EXAMPLE_MODEL_PACK_PATH)

    @contextmanager
    def empty_cdb(self):
        with captured_state_cdb(self._model.cdb):
            self._model.cdb.name2info.clear()
            self._model.cdb.cui2info.clear()
            yield

    def test_contracting_normally_passes(self):
        contracting_testing.assert_component_contracts(self._model)

    def test_contracting_fails_with_empty_cdb(self):
        with self.empty_cdb():
            with self.assertRaises(contracting_testing.ContractViolationError):
                contracting_testing.assert_component_contracts(self._model)

    def test_contracting_fails_with_no_entity(self):
        with self.assertRaises(contracting_testing.ContractViolationError):
            contracting_testing.assert_component_contracts(
                self._model, "Text with no entities")

    def test_contracting_fails_with_no_tokens(self):
        with self.assertRaises(contracting_testing.ContractViolationError):
            contracting_testing.assert_component_contracts(
                self._model, "")
