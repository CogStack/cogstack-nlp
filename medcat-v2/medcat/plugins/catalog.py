"""Management of the curated plugin catalog."""

import json
import logging
from typing import Optional
import importlib.resources
import requests

from packaging.specifiers import SpecifierSet
from packaging.version import Version
from pydantic import BaseModel, Field

from .downloadable import PluginSourceSpec

logger = logging.getLogger(__name__)


LOCAL_CATALOG_PATH = (
    importlib.resources.files('medcat.plugins.data') /
    'plugin_catalog.json'
)

class PluginCompatibility(BaseModel):
    medcat_version: str
    plugin_version: str


class PluginInfo(BaseModel):
    name: str
    display_name: str
    description: str
    source_spec: PluginSourceSpec
    homepage: str
    compatibility: list[PluginCompatibility]
    requires_auth: bool = False

    def can_merge(self, other: 'PluginInfo') -> bool:
        """Checks if 2 plugin infos can be merged.

        This checks to make sure the name and the source spec is the same.
        In that case the two objects likely refer to the same plugin. But
        one might have updated information.

        Args:
            other (PluginInfo): The other plugin info.

        Returns:
            bool: Whether they can be merged.
        """
        return (
            self.name == other.name and
            self.source_spec == other.source_spec)

    def merge(self, other: 'PluginInfo', prefer_other: bool = True) -> None:
        """Merge other plugin info into this one.

        Normally it is likely the "other" plugin info is newer so we want to
        prefer its data if/when possible.

        Args:
            other (PluginInfo): The other plugin info.
            prefer_other (bool): Whether to prefer other. Defaults to True.

        Raises:
            UnmergablePluginInfo: If the infos cannot be merged.
        """
        if not self.can_merge(other):
            raise UnmergablePluginInfo(self, other)
        if prefer_other:
            self.display_name = other.display_name
            self.description = other.description
            self.homepage = other.homepage
            self.requires_auth = other.requires_auth
        existing_plugin_versions = {cur.plugin_version for cur in self.compatibility}
        for other_comp in other.compatibility:
            if other_comp.plugin_version not in existing_plugin_versions:
                self.compatibility.append(other_comp)
            elif prefer_other:
                prev_index = [idx for idx, cur in enumerate(self.compatibility)
                              if cur.plugin_version == other_comp.plugin_version][0]
                self.compatibility[prev_index] = other_comp


class CatalogModel(BaseModel):
    """Pydantic model for the top-level catalog JSON."""
    plugins: dict[str, PluginInfo] = Field(default_factory=dict)
    version: str
    last_updated: str

    def merge(self, other: 'CatalogModel', prefer_other: bool = True) -> None:
        """Merge another catalog into this one.

        Args:
            other (CatalogModel): The other catalog to merge.
            prefer_other (bool): Whether to prefer other. Defaults to True.
        """
        if prefer_other:
            self.version = other.version
            self.last_updated = other.last_updated
        for plugin_name, info in other.plugins.items():
            if plugin_name not in self.plugins:
                self.plugins[plugin_name] = info
            elif prefer_other:
                self.plugins[plugin_name].merge(info, prefer_other=prefer_other)


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
        self._catalog: CatalogModel = CatalogModel(
            version="N/A", last_updated='N/A', plugins={})
        self._load_local_catalog()
        if use_remote:
            try:
                self._update_from_remote()
            except Exception as e:
                logger.debug(f"Could not fetch remote catalog: {e}")

    def _load_local_catalog(self):
        """Load the catalog from the packaged JSON file."""
        try:
            catalog_data = LOCAL_CATALOG_PATH.read_text()
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
        """Parse catalog JSON data into PluginInfo objects.

        This uses Pydantic models for schema validation and forward compatibility,
        so that adding fields to the JSON does not require rewriting this method.
        """
        payload = CatalogModel.model_validate(data)
        self._catalog.merge(payload)


    def get_plugin(self, name: str) -> Optional[PluginInfo]:
        """Get plugin info by name."""
        plugin = self._catalog.plugins.get(name)
        if plugin:
            return plugin
        # try lower case and with "-" instead of "_"
        return self._catalog.plugins.get(name.lower().replace("_", "-"))


    def list_plugins(self) -> list[PluginInfo]:
        """List all available plugins."""
        return list(self._catalog.plugins.values())

    def is_curated(self, name: str) -> bool:
        """Check if a plugin is in the curated catalog."""
        return name in self._catalog.plugins

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


class UnmergablePluginInfo(ValueError):

    def __init__(self, info1: PluginInfo, info2: PluginInfo) -> None:
        super().__init__(
            "The two plugin infos cannot be merged:\n"
            f"One:\n{info1}\nand two:\n{info2}"
        )
