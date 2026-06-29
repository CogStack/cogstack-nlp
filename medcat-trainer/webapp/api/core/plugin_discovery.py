"""
Discover and mount MedCAT Trainer plugins (``mct.plugins`` entry-point group).

Security note
-------------
Discovery imports and installs any package that advertises an ``mct.plugins``
entry point pointing at an ``AppConfig`` with ``is_mct_plugin = True``. The
``is_mct_plugin`` flag is an *opt-in marker*, not an authorisation check — a
discovered plugin runs as trusted in-process Django code. Only install plugins
from sources you trust; see ``docs/plugins.md`` for the trust model.

Mounted plugin URLs (``/api/ee/<app_label>/``) are served on the same origin as
the core app; plugins are responsible for enforcing authentication and
authorisation on their own views (see ``docs/plugins.md`` for the required
pattern).
"""
from __future__ import annotations

import logging
from importlib import import_module
from importlib.metadata import entry_points

from django.apps import AppConfig
from django.urls import include, path

logger = logging.getLogger(__name__)


def discover_mct_plugin_app_configs() -> list[str]:
    """Return dotted paths of :class:`~django.apps.AppConfig` classes to append to INSTALLED_APPS."""
    try:
        eps = entry_points(group='mct.plugins')
    except Exception as exc:
        logger.warning('Failed to enumerate mct.plugins entry points: %s', exc)
        return []

    discovered: list[str] = []
    for ep in eps:
        app_config_path = ep.value
        try:
            module_path, _, class_name = app_config_path.rpartition('.')
            if not class_name:
                logger.warning('Invalid mct.plugins entry %s: %s', ep.name, app_config_path)
                continue
            mod = import_module(module_path)
            config_cls = getattr(mod, class_name)
            if not isinstance(config_cls, type) or not issubclass(config_cls, AppConfig):
                logger.warning('mct.plugins entry %s is not an AppConfig: %s', ep.name, app_config_path)
                continue
            if not getattr(config_cls, 'is_mct_plugin', False):
                logger.warning(
                    'Skipping mct.plugins entry %s (%s): is_mct_plugin is not True',
                    ep.name,
                    app_config_path,
                )
                continue
            discovered.append(app_config_path)
            logger.info('Discovered MCT plugin: %s -> %s', ep.name, app_config_path)
        except Exception as exc:
            logger.warning('Failed to load mct.plugins entry %s (%s): %s', ep.name, app_config_path, exc)
    return discovered


def build_mct_plugin_urlpatterns():
    """URL patterns for ``/api/ee/<app_label>/`` for each installed MCT plugin."""
    from django.apps import apps

    patterns = []
    for app_config in apps.get_app_configs():
        if not getattr(app_config, 'is_mct_plugin', False):
            continue
        urls_module = f'{app_config.name}.urls'
        try:
            import_module(urls_module)
        except ImportError:
            logger.debug('MCT plugin %s has no urls module', app_config.label)
            continue
        patterns.append(
            path(
                f'api/ee/{app_config.label}/',
                include((urls_module, app_config.label)),
            )
        )
        logger.info('Mounted MCT plugin URLs at /api/ee/%s/', app_config.label)
    return patterns
