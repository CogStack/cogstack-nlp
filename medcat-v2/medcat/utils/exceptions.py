from typing import TypedDict


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
            msg += "\n"
        msg += "Please install the missing plugins to load this model pack."
        return msg

