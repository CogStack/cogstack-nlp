from typing import Optional

from medcat.cat import CAT
from medcat.tokenizing.tokens import MutableDocument
from medcat.components.base import CoreComponentType
from medcat.components.types import CoreComponent
from medcat.components.contracting import verify_contract


_DEFAULT_CONTRACT_TEXT = """
John had been diagnosed with acute Kidney - Failure the week before.
"""
_DEFAULT_COMP_TYPES_TO_CHECK = [
    CoreComponentType.ner, CoreComponentType.linking]


class ContractViolationError(ValueError):

    def __init__(self, component_type: CoreComponentType, violations: list):
        self.component_type = component_type
        self.violations = violations
        super().__init__(
            f"Contract violations for {component_type.name}: {violations}"
        )


def assert_single_component_holds(
    model: CAT,
    component: CoreComponent,
    text: str = _DEFAULT_CONTRACT_TEXT,
):
    """Assert a specific component's contract holds.

    Example:

        def test_my_ner_contract(self):
            cat = create_model_with_my_ner()
            my_ner = cat.pipe.get_component(CoreComponentType.ner)
            assert_single_component_holds(cat, my_ner)

    Args:
        model (CAT): The model with the specific component.
        component (CoreComponent): The component under test.
        text (str): The text to use for the check.
            Defaults to _DEFAULT_CONTRACT_TEXT.
    """
    component_type = component.get_type()

    def prep(t: str) -> MutableDocument:
        return model.pipe.pipe_until(t, component_type)

    contract = component_type.value
    min_feedbacks_need = (
        len(list(prep(text))) if component_type is CoreComponentType.ner else 1
    )
    if not min_feedbacks_need:
        # NOTE: this would normally happen with NER if/when there's no tokens
        raise ContractViolationError(
            component_type,
            ["Cannot check for feedback needs if minimum is 0 "
             f"for {component.full_name}", ])
    violations = verify_contract(
        text, prep, component, contract,
        raise_on_violation=False,
        min_feedbacks_need=min_feedbacks_need,
        min_feedbacks_provide=1,
    )
    if violations:
        raise ContractViolationError(component_type, violations)


def assert_component_contracts(
    model: CAT,
    text: str = _DEFAULT_CONTRACT_TEXT,
    to_check: Optional[list[CoreComponentType]] = None
):
    """Verify that all components upholds its MedCAT contract.

    Intended for use in tests by external component implementers.
    Raises ContractViolationError if the contract is not upheld.

    Example:

        def test_my_ner_contract(self):
            cat = create_model_with_my_component()
            assert_component_contract(cat)

    Args:
        model (CAT): The model pack to use. This needs to refer to a model that
            is able to NER and link at least 1 entity in the provided text.
            This model needs to already have the relevant component(s) to be
            checked.
        to_check (Optional[list[CoreComponentType]]): The core component types
            to check. Defaults to NER and linking.
        text (str): The text to use for the check.
            Defaults to _DEFAULT_CONTRACT_TEXT.

    Raises:
        ContractViolationError: If there are any violations found.
    """
    if to_check is None:
        to_check = _DEFAULT_COMP_TYPES_TO_CHECK
    for cct in to_check:
        cur_comp = model.pipe.get_component(cct)
        assert_single_component_holds(model, cur_comp, text)
