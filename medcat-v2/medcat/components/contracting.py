from enum import Enum, auto
from typing import Any, Iterator, Callable
from pydantic import BaseModel
from contextlib import contextmanager

from medcat.tokenizing.tokens import MutableDocument
from medcat.components.base import BaseComponent


class CollectionContract(BaseModel, frozen=True):
    """Contract for a collection field — what each item in the collection provides."""
    field: str                        # e.g. 'ner_ents'
    must_provide: frozenset[str]      # fields every item must have
    may_provide: frozenset[str] = frozenset()


class ComponentContract(BaseModel, frozen=True):
    needs: frozenset[str]
    must_provide: frozenset[str]
    may_provide: frozenset[str] = frozenset()
    collection_contracts: frozenset[CollectionContract] = frozenset()


class ContractViolation(Exception):
    pass


def iter_relevant_parts(doc: MutableDocument, path: str) -> Iterator[Any]:
    if path.startswith("doc."):
        yield doc
        return
    if path.startswith("token."):
        yield from doc[:]
    else:
        raise ValueError(f"Unknown path: {path}")


class AccessType(Enum):
    READ = auto()
    WRITE = auto()


@contextmanager
def wrap_relevant_parts(
    doc: MutableDocument,
    path: str,
    access_type: AccessType = AccessType.READ,
):
    member_name = path.split(".", 1)[1]
    out_list: list[list[Any]] = []
    for part in iter_relevant_parts(doc, path):
        # TODO: wrap such that I can tell that it has been accessed
        member = getattr(part, member_name)
        feedback: list[Any] = []
        setattr(part, WrappedMember(member, feedback, access_type=access_type))
        out_list.append(feedback)
    yield feedback


def verify_part(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    paths: list[str],
    access_type: AccessType,
    raise_on_violation: bool = True,
):
    violations: list[str] = []
    for path in paths:
        doc = doc_getter(text)
        with wrap_relevant_parts(doc, path) as feedback:
            doc = component(doc)
        # verify each one accessed
        accessed = sum(fb for fb in feedback)
        total = len(feedback)
        if accessed != total:
            violations.append(
                f"Component {component.full_name} does not {access_type.name}"
                f"{path} ({accessed} / {total} accessed)")
    if raise_on_violation:
        raise ContractViolation("\n".join(violations))
    return violations


def verify_needs(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    contract: ComponentContract,
    raise_on_violation: bool = True,
) -> list[str]:
    return verify_part(
        text, doc_getter, component, contract.needs,
        AccessType.READ, raise_on_violation=raise_on_violation,
    )


def verify_must_provide(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    contract: ComponentContract,
    raise_on_violation: bool = True,
) -> list[str]:
    return verify_part(
        text, doc_getter, component, contract.must_provide,
        AccessType.WRITE, raise_on_violation=raise_on_violation,
    )


def verify_contract(
    text: str,
    doc_getter: Callable[[str], MutableDocument],
    component: BaseComponent,
    contract: ComponentContract,
    raise_on_violation: bool = True,
) -> list[str]:
    """
    Verify a ComponentContract against a document before/after a component ran.
    Returns a list of violation messages. Raises ContractViolation if raise_on_violation.
    """
    # verify needs are met
    violations = verify_needs(
        text, doc_getter, component, contract, raise_on_violation=False
    )
    # verify mandatory returns are done
    violations += verify_must_provide(
        text, doc_getter, component, contract, raise_on_violation=False
    )

    if violations and raise_on_violation:
        raise ContractViolation("\n".join(violations))

    return violations
