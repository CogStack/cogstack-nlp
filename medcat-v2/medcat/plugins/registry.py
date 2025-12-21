from typing import Any, TypedDict, cast
from dataclasses import dataclass, field

from medcat.components.types import BaseComponent, CoreComponent


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


def find_provider(component: BaseComponent) -> str:
    all_plugins = plugin_registry.get_all_plugins()
    provider = "medcat"  # Default provider
    component_identifier = ""
    if component.is_core():
        core_comp = cast(CoreComponent, component)
        component_type = core_comp.get_type().name
        component_name = component.name
        component_identifier = f"core:{component_type}:{component_name}"
    else:
        component_name = component.name
        component_identifier = f"addon:{component_name}"

    # Check if this component is provided by a plugin via direct registration
    for plugin_info in all_plugins.values():
        found = False
        # Check core components registered by the plugin
        core_comps = plugin_info.registered_components["core"].items()
        for c_type, registered_comps in core_comps:
            for reg_comp_name, _ in registered_comps:
                if component_identifier == f"core:{c_type}:{reg_comp_name}":
                    provider = plugin_info.name
                    found = True
                    break
            if found:
                break
        if found:
            break

        # If not found in core, check addon components registered by the plugin
        if not found:
            for reg_comp_name, _ in plugin_info.registered_components["addons"]:
                if component_identifier == f"addon:{reg_comp_name}":
                    provider = plugin_info.name
                    found = True
                    break
        if found:
            break

    # Fallback: If not found by explicit registration, check module paths
    if provider == "medcat":
        component_module = component.__class__.__module__
        for plugin_info in all_plugins.values():
            for module_path in plugin_info.module_paths:
                if component_module.startswith(module_path):
                    provider = plugin_info.name
                    break
            if provider != "medcat":  # If a provider was found, break outer loop
                break
    return provider
