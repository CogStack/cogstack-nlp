from typing import TypedDict


from medcat.plugins.catalog import get_catalog


class MissingPluginInfo(TypedDict):
    name: str
    provides: list[tuple[str, str]]
    author: str | None
    url: str | None


class MissingPluginError(ImportError):
    """Custom exception raised when required plugins are missing."""

    def __init__(self, missing_plugins: list[MissingPluginInfo],
                 message: str | None = None) -> None:
        self.missing_plugins = missing_plugins
        if message is None:
            message = self._generate_message()
        super().__init__(message)

    def _generate_message(self) -> str:
        catalog = get_catalog()
        msg = "The following required plugins are missing:\n"
        for plugin in self.missing_plugins:
            msg += f"  - Plugin: {plugin['name']}\n"
            provided_components = ', '.join(
                [f'{c_type}:{c_name}' for c_type, c_name in plugin['provides']])
            msg += f"    Provides components: {provided_components}\n"
            if plugin['author']:
                msg += f"    Author: {plugin['author']}\n"
            if plugin['url']:
                msg += f"    URL: {plugin['url']}\n"
            if catalog.get_plugin(plugin['name']) is not None:
                msg += "\n    NB: You should be able to install this plugin using:\n"
                msg += f"        python -m medcat install-plugins {plugin['name']}\n"
            msg += "\n"
        msg += "Please install the missing plugins to load this model pack."
        return msg

