from typing import Callable
from logging import Logger

from medcat.tokenizing.tokens import MutableDocument
from medcat.components.base import BaseComponent, ComponentContract
from medcat.components.contracting_utils import (
    AccessType, wrap_relevant_parts, ContractViolation)


logger = Logger(__name__)


def verify_part(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    paths: list[str],
    access_type: AccessType,
    raise_on_violation: bool = True,
    min_feedbacks: int = 0,
):
    violations: list[str] = []
    for path in paths:
        doc = doc_getter(text)
        with wrap_relevant_parts(doc, path) as feedback:
            doc = component(doc)
        # verify each one access
        accessed = sum(bool(fb) for fb in feedback)
        total = len(feedback)
        if accessed != total:
            violations.append(
                f"Component {component.full_name} does not {access_type.name} "
                f"{path} ({accessed} / {total} accessed)")
            logger.debug(
                "Found a virolation in component '%s' for %s at '%s': "
                "(%d / %d) accessed with feedback %s",
                component.full_name, access_type.name,
                path, accessed, total, feedback,
            )
        elif total < min_feedbacks:
            violations.append(
                f"Component {component.full_name} did not {access_type.name} "
                f"{path} enough ({total} with minimum {min_feedbacks})")
            logger.debug(
                "Component '%s' did not %s "
                "'%s' enough (%d with minimum %d)",
                component.full_name, access_type.name,
                path, total, min_feedbacks,
            )
    if raise_on_violation:
        raise ContractViolation("\n".join(violations))
    return violations


def verify_needs(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    contract: ComponentContract,
    raise_on_violation: bool = True,
    min_feedbacks: int = 0,
) -> list[str]:
    return verify_part(
        text, doc_getter, component, list(contract.needs),
        AccessType.READ, raise_on_violation=raise_on_violation,
        min_feedbacks=min_feedbacks,
    )


def verify_must_provide(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    contract: ComponentContract,
    raise_on_violation: bool = True,
    min_feedbacks: int = 0,
) -> list[str]:
    return verify_part(
        text, doc_getter, component, list(contract.must_provide),
        AccessType.WRITE, raise_on_violation=raise_on_violation,
        min_feedbacks=min_feedbacks,
    )


def verify_contract(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    contract: ComponentContract,
    raise_on_violation: bool = True,
    min_feedbacks_need: int = 0,
    min_feedbacks_provide: int = 0,
) -> list[str]:
    """
    Verify a ComponentContract against a document before/after a component ran.
    Returns a list of violation messages.

    Raises ContractViolation if violations found and raise_on_violation.
    """
    # verify needs are met
    violations = verify_needs(
        text, doc_getter, component, contract, raise_on_violation=False,
        min_feedbacks=min_feedbacks_need,
    )
    # verify mandatory returns are done
    violations += verify_must_provide(
        text, doc_getter, component, contract, raise_on_violation=False,
        min_feedbacks=min_feedbacks_provide,
    )

    if violations and raise_on_violation:
        raise ContractViolation("\n".join(violations))

    return violations
