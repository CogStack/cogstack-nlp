from unittest import TestCase

from medcat.cat import CAT
from medcat.components import contracting_testing
from tests import UNPACKED_EXAMPLE_MODEL_PACK_PATH


class TestContractingForModel(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._model = CAT.load_model_pack(UNPACKED_EXAMPLE_MODEL_PACK_PATH)

    def test_contracts_held(self):
        contracting_testing.assert_component_contracts(self._model)
