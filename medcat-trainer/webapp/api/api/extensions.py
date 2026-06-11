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

Security / trust model
----------------------
An installed ``mct.plugins`` package runs as **first-class Django application
code**: it executes at import time and in ``AppConfig.ready()`` with full access
to the database, filesystem, environment, and request/session data. There is no
sandbox. Treat plugins like kernel modules — only install packages you trust and
have vetted. See ``docs/plugins.md`` for the full trust model and secure
plugin-authoring guidance.

The registry helpers below apply light input validation (URL-scheme validation on
menu/route entries) and signal emission is isolated via :func:`dispatch` so that
a plugin receiver cannot break core request flows. These are
validation measures, **not** a security boundary against malicious code
running in-process.
"""
from __future__ import annotations


import copy

import logging
import re

from collections.abc import Callable, Iterable
from typing import Any, Optional

from django.dispatch import Signal

logger = logging.getLogger(__name__)

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
# Signal dispatch (plugin-isolating)
# ---------------------------------------------------------------------------

def dispatch(signal: Signal, **kwargs: Any) -> None:
    """Emit a plugin-facing signal without letting receivers break core flows.

    Core OSS code only ever *emits* the signals in this module; all receivers
    are third-party plugin code. We therefore use :meth:`Signal.send_robust`,
    which isolates and returns any exception raised by a receiver instead of
    propagating it into the request path. Receiver failures are logged and then
    ignored so a plugin cannot block document submission,
    annotation persistence, or OIDC login.
    """
    for receiver, response in signal.send_robust(**kwargs):
        if isinstance(response, Exception):
            logger.error(
                "MCT plugin signal receiver %r raised %s: %s",
                getattr(receiver, "__qualname__", receiver),
                type(response).__name__,
                response,
                exc_info=response,
            )


# ---------------------------------------------------------------------------
# URL validation for bootstrap-exposed entries
# ---------------------------------------------------------------------------
#
# Menu ``href``/``route`` and route ``path`` values are served via
# ``GET /api/bootstrap/`` and rendered into the authenticated SPA. A
# plugin must not be able to inject ``javascript:``/``data:`` (etc.)
# URLs that would execute in the browser of any logged-in user, nor
# protocol-relative ("//host") references that navigate off-origin.

_ALLOWED_URL_SCHEMES = ("http", "https")
_URL_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")
# Browsers ignore ASCII control chars / whitespace inside a scheme
# (e.g. "java\tscript:..."), so strip them before inspecting the scheme.
_URL_STRIP_RE = re.compile(r"[\x00-\x20\x7f]")


def _validate_safe_url(value: Any, *, field: str) -> None:
    """Reject dangerous URL values for bootstrap-exposed link fields.

    Allowed: same-document/relative references (no scheme, e.g. ``/ee/adj``,
    ``./x``, ``#frag``, ``?q=1``) and absolute ``http(s)`` URLs. Rejected:
    any other scheme (``javascript:``, ``data:``, ``vbscript:``, ``file:`` …)
    and protocol-relative ``//host`` references.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    cleaned = _URL_STRIP_RE.sub("", value)
    if cleaned == "":
        raise ValueError(f"{field} must not be empty")
    if cleaned.startswith("//"):
        raise ValueError(f"{field} must not be a protocol-relative URL")
    match = _URL_SCHEME_RE.match(cleaned)
    if match is None:
        # No scheme => relative path / fragment / query. Allowed.
        return
    if match.group(1).lower() not in _ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"{field} has a disallowed URL scheme '{match.group(1)}'; "
            f"only {', '.join(_ALLOWED_URL_SCHEMES)} and relative paths are permitted"
        )


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

    Any ``route``/``href`` value is validated to be a relative path or an
    ``http(s)`` URL (see :func:`_validate_safe_url`) so a plugin cannot inject
    a ``javascript:`` link that runs in an authenticated user's browser.
    """
    if not isinstance(item, dict):
        raise TypeError("menu extension item must be a dict")
    if "id" not in item or "label" not in item:
        raise ValueError("menu extension item requires 'id' and 'label'")
    if "route" in item:
        _validate_safe_url(item["route"], field="menu extension 'route'")
    if "href" in item:
        _validate_safe_url(item["href"], field="menu extension 'href'")
    _menu_extensions.append(copy.deepcopy(item))


def get_menu_extensions() -> list[dict[str, Any]]:
    return [copy.deepcopy(it) for it in _menu_extensions]


def register_route(route: dict[str, Any]) -> None:
    """Register a frontend route descriptor exposed via ``GET /api/bootstrap/``.

    ``route`` MUST contain ``path`` (str) and ``component`` (str — module
    specifier or registered component name resolved by the frontend).

    ``path`` is validated to be a relative SPA path (no off-origin or
    non-``http(s)`` scheme); see :func:`_validate_safe_url`.
    """
    if not isinstance(route, dict):
        raise TypeError("route must be a dict")
    if "path" not in route or "component" not in route:
        raise ValueError("route requires 'path' and 'component'")
    _validate_safe_url(route["path"], field="route 'path'")
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
    "dispatch",
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
