"""
MedCAT Trainer extension API.

Stable contract used by enterprise / third-party plugins. The OSS app itself
emits these signals and consults the registries from a small number of
explicit sites (see :mod:`api.signals`, :mod:`api.views`, :mod:`api.permissions`).

Plugins are discovered via the ``mct.plugins`` Python entry-point group; each
entry point points at a Django ``AppConfig`` subclass. Plugin URL configs are
mounted at ``/api/ee/<app_label>/`` when the ``AppConfig`` sets
``is_mct_plugin = True``. See :mod:`core.settings` and :mod:`core.urls`.

The shape of this module is contract-tested by ``test_extensions.py`` and the
``contract-tests`` CI job; changes that break the documented shape are
breaking changes.
"""
from __future__ import annotations

import copy
from collections.abc import Callable, Iterable
from typing import Any, Optional

from django.dispatch import Signal

# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------
#
# All signals MUST include at least the documented kwargs. Extra kwargs may
# be added over time but documented kwargs are stable.

#: Sent immediately before a document is submitted to training.
#: kwargs: ``project`` (ProjectAnnotateEntities), ``document`` (Document),
#:         ``user`` (User or None).
pre_document_submit = Signal()

#: Sent immediately after a document is submitted to training.
#: kwargs: ``project`` (ProjectAnnotateEntities), ``document`` (Document),
#:         ``user`` (User or None).
post_document_submit = Signal()

#: Sent after an :class:`AnnotatedEntity` row is created.
#: kwargs: ``annotation`` (AnnotatedEntity), ``project`` (ProjectAnnotateEntities),
#:         ``document`` (Document), ``user`` (User or None).
annotation_created = Signal()

#: Sent after an :class:`AnnotatedEntity` row is updated.
#: kwargs: ``annotation`` (AnnotatedEntity), ``project`` (ProjectAnnotateEntities),
#:         ``document`` (Document), ``user`` (User or None).
annotation_updated = Signal()

#: Sent after an :class:`AnnotatedEntity` row is deleted.
#: kwargs: ``annotation`` (AnnotatedEntity, instance prior to delete),
#:         ``project`` (ProjectAnnotateEntities), ``document`` (Document).
annotation_deleted = Signal()

#: Sent after a :class:`ProjectGroup` row is created.
#: kwargs: ``project_group`` (ProjectGroup).
project_group_created = Signal()

#: Sent after a :class:`ProjectGroup` row is updated.
#: kwargs: ``project_group`` (ProjectGroup).
project_group_updated = Signal()

#: Sent after the OIDC user resolver returns a Django user.
#: kwargs: ``user`` (User), ``id_token`` (dict), ``created`` (bool).
user_oidc_resolved = Signal()


# ---------------------------------------------------------------------------
# Permission hook registry
# ---------------------------------------------------------------------------
#
# Permission hooks are grant-only: a hook returning ``True`` grants the
# permission; ``None`` or ``False`` abstains and the OSS default decision is
# used. Hooks MUST NOT be used to deny access that the OSS code would
# otherwise grant.
#
# Hooks are called with two positional arguments. For the ``is_project_admin``
# hook these are the ``User`` and ``ProjectAnnotateEntities`` instances; the
# arguments are typed as ``Any`` so the registry stays generic across hook
# names without coupling to specific model classes.

PermissionHook = Callable[[Any, Any], Optional[bool]]
_permission_hooks: dict[str, list[PermissionHook]] = {}


def register_permission_hook(name: str, fn: PermissionHook) -> None:
    """Register a grant-only permission hook for ``name``.

    Hooks are called in registration order until one returns ``True``.
    Any value other than ``True`` (including ``None`` and ``False``) abstains.
    """
    if not callable(fn):
        raise TypeError("permission hook must be callable")
    _permission_hooks.setdefault(name, []).append(fn)


def get_permission_hooks(name: str) -> Iterable[PermissionHook]:
    return tuple(_permission_hooks.get(name, ()))


def clear_permission_hooks(name: Optional[str] = None) -> None:
    """Clear hooks. Intended for tests."""
    if name is None:
        _permission_hooks.clear()
    else:
        _permission_hooks.pop(name, None)


# ---------------------------------------------------------------------------
# Menu / route / feature registries (frontend bootstrap)
# ---------------------------------------------------------------------------

_menu_extensions: list[dict[str, Any]] = []
_plugin_routes: list[dict[str, Any]] = []
_features: set[str] = set()


def register_menu_extension(item: dict[str, Any]) -> None:
    """Register a top-nav menu item exposed via ``GET /api/bootstrap/``.

    ``item`` MUST contain ``id`` (str) and ``label`` (str). It SHOULD
    contain ``route`` (str) or ``href`` (str). Additional keys pass through
    verbatim to the frontend.
    """
    if not isinstance(item, dict):
        raise TypeError("menu extension item must be a dict")
    if "id" not in item or "label" not in item:
        raise ValueError("menu extension item requires 'id' and 'label'")
    _menu_extensions.append(copy.deepcopy(item))


def get_menu_extensions() -> list[dict[str, Any]]:
    return [copy.deepcopy(it) for it in _menu_extensions]


def register_route(route: dict[str, Any]) -> None:
    """Register a frontend route descriptor exposed via ``GET /api/bootstrap/``.

    ``route`` MUST contain ``path`` (str) and ``component`` (str — module
    specifier or registered component name resolved by the frontend).
    """
    if not isinstance(route, dict):
        raise TypeError("route must be a dict")
    if "path" not in route or "component" not in route:
        raise ValueError("route requires 'path' and 'component'")
    _plugin_routes.append(copy.deepcopy(route))


def get_routes() -> list[dict[str, Any]]:
    return [dict(r) for r in _plugin_routes]


def register_feature(name: str) -> None:
    """Declare a license-gated feature as enabled."""
    if not isinstance(name, str) or not name:
        raise ValueError("feature name must be a non-empty string")
    _features.add(name)


def get_features() -> list[str]:
    return sorted(_features)


def clear_registries() -> None:
    """Reset menu / route / feature registries. Intended for tests."""
    _menu_extensions.clear()
    _plugin_routes.clear()
    _features.clear()


# ---------------------------------------------------------------------------
# Plugin discovery state
# ---------------------------------------------------------------------------

#: Populated by :mod:`core.settings` at import time with the dotted ``AppConfig``
#: paths of installed MCT plugins. Read-only at runtime.
discovered_plugin_apps: list[str] = []


__all__ = [
    "pre_document_submit",
    "post_document_submit",
    "annotation_created",
    "annotation_updated",
    "annotation_deleted",
    "project_group_created",
    "project_group_updated",
    "user_oidc_resolved",
    "register_permission_hook",
    "get_permission_hooks",
    "clear_permission_hooks",
    "register_menu_extension",
    "get_menu_extensions",
    "register_route",
    "get_routes",
    "register_feature",
    "get_features",
    "clear_registries",
    "discovered_plugin_apps",
]
