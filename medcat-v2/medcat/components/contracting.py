from enum import Enum, auto
from typing import Any, Iterator, Callable, Type
from contextlib import contextmanager, ExitStack
from collections import defaultdict
from logging import Logger

from medcat.tokenizing.tokens import MutableDocument
from medcat.components.base import BaseComponent, ComponentContract


logger = Logger(__name__)


_SENTINEL = object()


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


class WrappedMember:

    def __init__(
        self,
        part: Any,
        member_name: str,
        feedback: list[Any],
        access_type: AccessType,
    ) -> None:
        self.part = part
        self.member_name = member_name
        self.feedback = feedback
        self.access_type = access_type
        self._oirg_class = type(self.part)
        self._install()

    def _install(self):
        original_cls = type(self.part)
        spy = self  # capture for closure

        if self.access_type == AccessType.READ:

            class SpySubclass(original_cls):
                def __getattribute__(self, name):
                    val = super().__getattribute__(name)
                    if name == spy.member_name:
                        # saving str copy of value
                        spy.feedback.append(str(val))
                    return val

        elif self.access_type == AccessType.WRITE:

            class SpySubclass(original_cls):
                def __setattr__(self, name, value):
                    if name in spy.member_name:
                        try:
                            old = super().__getattribute__(name)
                        except AttributeError:
                            old = AttributeError  # sentinel: didn't exist yet
                        # saving str copies of state
                        spy.feedback.append((str(old), str(value)))
                    super().__setattr__(name, value)

        SpySubclass.__name__ = f"Spy({original_cls.__name__})"
        SpySubclass.__qualname__ = SpySubclass.__name__
        self.part.__class__ = SpySubclass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.part.__class__ = self._oirg_class


@contextmanager
def spy_token_class(
    token_cls: Type,
    watched_attr: str,
    access_type: AccessType,
):
    prev_getattr = token_cls.__dict__.get('__getattribute__', _SENTINEL)
    prev_setattr = token_cls.__dict__.get('__setattr__', _SENTINEL)

    per_instance_spied: dict[Any, list[Any]] = defaultdict(list)

    def __getattribute__(self, name: str) -> Any:
        val = object.__getattribute__(self, name)
        if name == watched_attr:
            per_instance_spied[self].append(str(val))
        return val

    def __setattr__(self, name: str, value: Any):
        old = object.__getattribute__(self, name)
        object.__setattr__(self, name, value)
        if name == watched_attr:
            per_instance_spied[self].append((str(old), str(value)))

    if access_type == AccessType.READ:
        token_cls.__getattribute__ = __getattribute__
    elif access_type == AccessType.WRITE:
        token_cls.__setattr__ = __setattr__
    else:
        raise ValueError(f"Unknown access type: {access_type}")
    try:
        yield per_instance_spied
    finally:
        if prev_getattr is _SENTINEL:
            del token_cls.__getattribute__
        else:
            token_cls.__getattribute__ = prev_getattr

        if prev_setattr is _SENTINEL:
            token_cls.__setattr__ = object.__setattr__
        else:
            token_cls.__setattr__ = prev_setattr


@contextmanager
def wrap_relevant_parts(
    doc: MutableDocument,
    path: str,
    access_type: AccessType = AccessType.READ,
):
    if path.startswith("doc."):
        with wrap_relevant_persistant_parts(
            doc, path, access_type
        ) as feedbacks:
            yield feedbacks
    elif path.startswith("token."):
        with wrap_relevant_token_cls(
            doc, path, access_type
        ) as feedbacks:
            yield feedbacks


@contextmanager
def wrap_relevant_token_cls(
    doc: MutableDocument,
    path: str,
    access_type: AccessType = AccessType.READ,
):
    _, attr_name = path.split(".", 1)
    tkn_cls = type(next(iter(doc)))
    with spy_token_class(
        tkn_cls, attr_name, access_type
    ) as per_instance_spied:
        yield list(per_instance_spied.values())


@contextmanager
def wrap_relevant_persistant_parts(
    doc: MutableDocument,
    path: str,
    access_type: AccessType = AccessType.READ,
):
    member_name = path.split(".", 1)[1]
    out_list: list[list[Any]] = []
    with ExitStack() as exit_stack:
        for part in iter_relevant_parts(doc, path):
            feedback: list[Any] = []
            exit_stack.enter_context(
                WrappedMember(
                    part, member_name,
                    feedback, access_type=access_type)
            )
            out_list.append(feedback)
        yield out_list


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
