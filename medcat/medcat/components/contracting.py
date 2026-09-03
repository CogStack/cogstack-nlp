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
) -> list[str]:
    """Verify the parts for this text.

    Args:
        text (str): The text to use.
        doc_getter (Callable[[str], MutableDocument]): The document getter.
        component (BaseComponent): The component to check.
        paths (list[str]): The paths to check.
        access_type (AccessType): The type of access to check.
        raise_on_violation (bool): Whether to raise on a violation.
            Defaults to True.
        min_feedbacks (int): The minimum number of feedbacks expected.
            Defaults to 0.

    Raises:
        ContractViolation: If there are violations and instructed to raise.

    Returns:
        list[str]: The list of violations, if any.
    """
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
    """Verify the needs portion of a contract.

    Args:
        text (str): The text to use.
        doc_getter (Callable[[str], MutableDocument]): The document getter.
        component (BaseComponent): The component to check.
        contract (ComponentContract): The contract to check.
        raise_on_violation (bool): Whether to raise on violations.
            Defaults to True.
        min_feedbacks (int,): The minimum number of feedbacks expected.
            Defaults to 0.

    Returns:
        list[str]: The list of violations, if any.
    """
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
    """Verify the must-provide portion of a contract.

    Args:
        text (str): The text to use.
        doc_getter (Callable[[str], MutableDocument]): The document getter.
        component (BaseComponent): The component to check.
        contract (ComponentContract): The contract to check.
        raise_on_violation (bool): Whether to raise on violations.
            Defaults to True.
        min_feedbacks (int,): The minimum number of feedbacks expected.
            Defaults to 0.

    Returns:
        list[str]: The list of violations, if any.
    """
    return verify_part(
        text, doc_getter, component, list(contract.must_provide),
        AccessType.WRITE, raise_on_violation=raise_on_violation,
        min_feedbacks=min_feedbacks,
    )


def verify_collections_contracts(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    contract: ComponentContract,
    raise_on_violation: bool = True,
    min_feedbacks: int = 0,
) -> list[str]:
    """Verify the collection contracts portion of a contract.

    This method only really checks the length of the collection
    and that each item in there has a truthy value for each required
    field. The expectation is that the write action (for the collection)
    is checked by other parts. And because these entities may be created
    in order to put them in the lists (i.e for NER) without the data filled
    in, it's fair to assume that if the data exists, it was filled in.

    Args:
        text (str): The text to use.
        doc_getter (Callable[[str], MutableDocument]): The document getter.
        component (BaseComponent): The component to check.
        contract (ComponentContract): The contract to check.
        raise_on_violation (bool): Whether to raise on violations.
            Defaults to True.
        min_feedbacks (int): The minimum number of feedbacks expected.
            Defaults to 0.

    Returns:
        list[str]: The list of violations, if any.
    """
    violations: list[str] = []
    if not contract.collection_contracts:
        return violations
    doc = doc_getter(text)
    doc = component(doc)
    for cc in contract.collection_contracts:
        if not cc.field.startswith("doc."):
            violations.append(
                f"Collection contract field '{cc.field}' is not a doc-level "
                f"field — only doc.* fields are currently supported")
            continue
        attr = cc.field.split(".", 1)[1]
        try:
            collection = getattr(doc, attr)
        except AttributeError:
            violations.append(
                f"Component {component.full_name} did not provide "
                f"collection '{cc.field}' at all")
            continue
        items = list(collection)
        if len(items) < min_feedbacks:
            violations.append(
                f"Collection '{cc.field}' has too few items "
                f"({len(items)} with minimum {min_feedbacks})")
        for i, item in enumerate(items):
            for field in cc.must_provide:
                try:
                    val = getattr(item, field)
                except AttributeError:
                    violations.append(
                        f"Item {i} in '{cc.field}' is missing "
                        f"required field '{field}'")
                    continue
                if not val:
                    violations.append(
                        f"Item {i} in '{cc.field}' has falsy value "
                        f"for required field '{field}' (got {val!r})")
    if violations and raise_on_violation:
        raise ContractViolation("\n".join(violations))
    return violations


def verify_contract(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    contract: ComponentContract,
    raise_on_violation: bool = True,
    min_feedbacks_need: int = 0,
    min_feedbacks_provide: int = 0,
    min_feedbacks_contracts: int = 0,
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
    # verify collections contracts
    violations += verify_collections_contracts(
        text, doc_getter, component, contract, raise_on_violation=False,
        min_feedbacks=min_feedbacks_contracts,
    )

    if violations and raise_on_violation:
        raise ContractViolation("\n".join(violations))

    return violations
