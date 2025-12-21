from importlib.metadata import EntryPoint, entry_points, metadata

from medcat.plugins.registry import PluginInfo, plugin_registry, RegisteredComponents
from medcat.plugins.registry import create_empty_reg_comps
from medcat.components.types import get_registered_components, CoreComponentType
from medcat.components.addons.addons import get_registered_addons


ENTRY_POINT_PATH = "medcat.plugins"


def _get_registered_components() -> RegisteredComponents:
    registered: RegisteredComponents = create_empty_reg_comps()
    for comp_type in CoreComponentType:
        registered["core"][comp_type.name] = get_registered_components(
            comp_type).copy()
    registered["addons"].extend(get_registered_addons().copy())
    return registered


def _get_changes(before_load_components: RegisteredComponents,
                 after_load_components: RegisteredComponents
                 ) -> RegisteredComponents:
    newly_registered: RegisteredComponents = create_empty_reg_comps()
    for comp_type, components in after_load_components["core"].items():
        diff = set(components) - set(before_load_components["core"].get(comp_type, []))
        if diff:
            newly_registered["core"][comp_type] = list(diff)

    diff = set(after_load_components["addons"]) - set(
        before_load_components["addons"])
    if diff:
        newly_registered["addons"] = list(diff)
    return newly_registered


def _load_plugin(ep: EntryPoint) -> None:
    # Get components before plugin load
    before_load_components = _get_registered_components()

    # this will init the addon
    ep.load()

    # Get components after plugin load
    after_load_components = _get_registered_components()

    # Identify newly registered components
    newly_registered: RegisteredComponents = _get_changes(
        before_load_components, after_load_components)

    # Extract package metadata
    # The entry point name is not necessarily the distribution name, so we use ep.dist.name
    # if available (Python 3.10+). Otherwise, we fall back to ep.name.
    # See: https://docs.python.org/3/library/importlib.metadata.html#entry-points
    distribution_name = ep.dist.name if hasattr(ep, 'dist') and ep.dist else ep.name
    pkg_metadata = metadata(distribution_name)
    plugin_name = pkg_metadata.get("Name", distribution_name)
    plugin_version = pkg_metadata.get("Version")
    plugin_author = pkg_metadata.get("Author")
    plugin_url = pkg_metadata.get("Home-page")
    if plugin_url is None:
        plugin_url = pkg_metadata.get("Project-URL")

    # Create PluginInfo and register
    plugin_info = PluginInfo(
        name=plugin_name,
        version=plugin_version,
        author=plugin_author,
        url=plugin_url,
        registered_components=newly_registered,
        metadata={key: pkg_metadata[key] for key in pkg_metadata},
    )
    plugin_registry.register_plugin(plugin_info)


def load_plugins():
    eps = entry_points(group=ENTRY_POINT_PATH)
    for ep in eps:
        _load_plugin(ep)
