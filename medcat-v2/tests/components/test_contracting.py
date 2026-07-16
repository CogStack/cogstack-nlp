from unittest import TestCase
from typing import Callable

from medcat.cat import CAT
from medcat.components import contracting
from medcat.components.base import CoreComponentType
from medcat.components.ner.vocab_based_ner import NER
from medcat.components.linking.context_based_linker import Linker
from medcat.tokenizing.tokens import MutableDocument
from tests import UNPACKED_EXAMPLE_MODEL_PACK_PATH


class TestContractingNer(TestCase):
    comp_type = CoreComponentType.ner
    comp_cls = NER
    args: Callable[[], list] = list
    min_feedbacks_need = 0
    min_feedbacks_provide = 1
    text = "John had been diagnosed with acute Kidney Failure the week before."

    @classmethod
    def component_prep(cls, text: str) -> MutableDocument:
        return cls._model.pipe.pipe_until(text, cls.comp_type)

    @classmethod
    def setUpClass(cls) -> None:
        cls._model = CAT.load_model_pack(UNPACKED_EXAMPLE_MODEL_PACK_PATH)
        cls.tokenizer = cls._model.pipe.tokenizer
        cls.cdb = cls._model.cdb
        if not cls.args():
            cls.comp = cls.comp_cls(cls.tokenizer, cls.cdb)
        else:
            cls.comp = cls.comp_cls(*cls.args())
        return super().setUpClass()

    def test_contract_held(self):
        violations = contracting.verify_contract(
            self.text, self.component_prep, self.comp, self.comp_type.value,
            raise_on_violation=False,
            min_feedbacks_need=self.min_feedbacks_need,
            min_feedbacks_provide=self.min_feedbacks_provide,
        )
        self.assertFalse(violations, "Expected not violations")


class TestContractingLinker(TestContractingNer):
    comp_type = CoreComponentType.linking
    comp_cls = Linker
    min_feedbacks_need = 1

    @classmethod
    def setUpClass(cls) -> None:
        cls.args = lambda: [
            cls.cdb, cls._model.vocab, cls._model.config]
        return super().setUpClass()
