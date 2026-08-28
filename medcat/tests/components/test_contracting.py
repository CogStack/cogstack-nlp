from unittest import TestCase

from medcat.cat import CAT
from medcat.components import contracting_testing
from medcat.components.base import CoreComponentType
from tests import UNPACKED_EXAMPLE_MODEL_PACK_PATH


class TestContractingForModel(TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._model = CAT.load_model_pack(UNPACKED_EXAMPLE_MODEL_PACK_PATH)

    def test_all_contracts_hold(self):
        contracting_testing.assert_component_contracts(self._model)

    def test_individual_contracts_hold(self):
        for ct in [CoreComponentType.ner, CoreComponentType.linking]:
            comp = self._model.pipe.get_component(ct)
            contracting_testing.assert_single_component_holds(self._model, comp)
