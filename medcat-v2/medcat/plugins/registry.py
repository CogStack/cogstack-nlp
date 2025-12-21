from typing import Any, TypedDict
from dataclasses import dataclass, field


class RegisteredComponents(TypedDict):
    core: dict[str, list[tuple[str, str]]]
    addons: list[tuple[str, str]]


def create_empty_reg_comps() -> RegisteredComponents:
    return {"core": {}, "addons": []}


@dataclass
class PluginInfo:
    name: str
    version: str | None = None
    author: str | None = None
    url: str | None = None
    module_paths: list[str] = field(default_factory=list)
    registered_components: RegisteredComponents = field(
        default_factory=create_empty_reg_comps)
    metadata: dict[str, Any] = field(default_factory=dict)


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, PluginInfo] = {}

    def register_plugin(self, plugin_info: PluginInfo):
        self._plugins[plugin_info.name] = plugin_info

    def get_plugin_info(self, name: str) -> PluginInfo | None:
        return self._plugins.get(name)

    def get_all_plugins(self) -> dict[str, PluginInfo]:
        return self._plugins.copy()


plugin_registry = PluginRegistry()

