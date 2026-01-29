"""Management of the curated plugin catalog."""

import json
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
import importlib.resources
import requests

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .downloadable import PluginSourceSpec

logger = logging.getLogger(__name__)


@dataclass
class PluginCompatibility:
    """Compatibility information for a plugin version."""
    medcat_version: str
    plugin_version: str


@dataclass
class PluginInfo:
    """Information about a curated plugin."""
    name: str
    display_name: str
    description: str
    source_spec: PluginSourceSpec
    homepage: str
    compatibility: List[PluginCompatibility]
    requires_auth: bool = False


class PluginCatalog:
    """Manages the catalog of curated plugins."""

    REMOTE_CATALOG_URL = (
        "https://raw.githubusercontent.com/CogStack/cogstack-nlp/main/"
        "medcat-v2/medcat/plugins/data/plugin_catalog.json"
    )

    def __init__(self, use_remote: bool = True):
        """
        Initialize the plugin catalog.

        Args:
            use_remote: Whether to attempt fetching the remote catalog
        """
        self._catalog: Dict[str, PluginInfo] = {}
        self._load_local_catalog()
        if use_remote:
            try:
                self._update_from_remote()
            except Exception as e:
                logger.debug(f"Could not fetch remote catalog: {e}")

    def _load_local_catalog(self):
        """Load the catalog from the packaged JSON file."""
        try:
            catalog_path = (
                importlib.resources.files('medcat.plugins.data') / 
                'plugin_catalog.json'
            )
            catalog_data = catalog_path.read_text()
            self._parse_catalog(json.loads(catalog_data))
            logger.debug("Loaded local plugin catalog")
        except Exception as e:
            logger.warning(f"Could not load local catalog: {e}")

    def _update_from_remote(self, timeout: int = 5):
        """Fetch and update from the remote catalog."""
        response = requests.get(self.REMOTE_CATALOG_URL, timeout=timeout)
        response.raise_for_status()
        
        self._parse_catalog(response.json())
        logger.info("Updated plugin catalog from remote source")

    def _parse_catalog(self, data: dict):
        """Parse catalog JSON data into PluginInfo objects."""
        for plugin_name, plugin_data in data.get("plugins", {}).items():
            compatibility = [
                PluginCompatibility(
                    medcat_version=c["medcat_version"],
                    plugin_version=c["plugin_version"]
                )
                for c in plugin_data.get("compatibility", [])
            ]

            self._catalog[plugin_name] = PluginInfo(
                name=plugin_name,
                display_name=plugin_data.get("display_name", plugin_name),
                description=plugin_data.get("description", ""),
                source_spec=PluginSourceSpec(
                    source=plugin_data.get("source", ""),
                    source_type=plugin_data.get("source_type", "pypi"),
                    subdirectory=plugin_data.get("subdirectory"),
                ),
                homepage=plugin_data.get("homepage", ""),
                compatibility=compatibility,
                requires_auth=plugin_data.get("requires_auth", False),
            )


    def get_plugin(self, name: str) -> Optional[PluginInfo]:
        """Get plugin info by name."""
        plugin = self._catalog.get(name)
        if plugin:
            return plugin
        # try lower case and with "-" instead of "_"
        return self._catalog.get(name.lower().replace("_", "-"))


    def list_plugins(self) -> List[PluginInfo]:
        """List all available plugins."""
        return list(self._catalog.values())

    def is_curated(self, name: str) -> bool:
        """Check if a plugin is in the curated catalog."""
        return name in self._catalog

    def get_compatible_version(
        self, 
        plugin_name: str, 
        medcat_version: str
    ) -> str:
        """
        Get compatible plugin version for given MedCAT version.

        Args:
            plugin_name: Name of the plugin
            medcat_version: MedCAT version string

        Raises:
            NoSuchPluginException: If the plugin wasn't found / known.
            NoCompatibleSpecException: If compatibility spec was unable to be met.

        Returns:
            Compatible version specifier
        """
        plugin = self.get_plugin(plugin_name)
        if not plugin:
            raise NoSuchPluginException(plugin_name)

        medcat_ver = Version(medcat_version)

        for compat in plugin.compatibility:
            spec = SpecifierSet(compat.medcat_version)
            if medcat_ver in spec:
                return compat.plugin_version

        raise NoCompatibleSpecException(plugin, medcat_ver)


# Global catalog instance
_catalog: Optional[PluginCatalog] = None


def get_catalog() -> PluginCatalog:
    """Get the global plugin catalog instance."""
    global _catalog
    if _catalog is None:
        _catalog = PluginCatalog()
    return _catalog


class NoSuchPluginException(ValueError):

    def __init__(self, plugin_name: str) -> None:
        super().__init__(
            f"No plugin by the name '{plugin_name}' is known to MedCAT")


class NoCompatibleSpecException(ValueError):

    def __init__(self, plugin: PluginInfo, medcat_ver: Version) -> None:
        super().__init__(
            f"Was unable to find a version of the plugin {plugin.name} "
            f"that was compatible with MedCAT version {medcat_ver}. "
            f"Plugin details: {plugin}")
