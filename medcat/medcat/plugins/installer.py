"""Plugin installation functionality."""

import sys
import subprocess
import logging
from typing import Optional

from .downloadable import PluginInstaller, PluginInstallSpec
from .catalog import get_catalog
import medcat

logger = logging.getLogger(__name__)


class PipInstaller:
    """Plugin installer using pip."""

    def install(
        self, 
        spec: PluginInstallSpec, 
        dry_run: bool = False
    ) -> bool:
        """Install a plugin using pip."""
        cmd = [
            sys.executable, "-m", "pip", "install",
            spec.to_pip_spec()
        ]

        if dry_run:
            cmd.insert(3, "--dry-run")

        logger.info(f"Installing {spec.name}: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            logger.debug(f"Install output: {result.stdout}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Installation failed: {e.stderr}")
            return False

    def is_available(self) -> bool:
        """Check if pip is available."""
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "--version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def get_name(self) -> str:
        return "pip"


class PluginInstallationManager:
    """Manages plugin installation."""

    def __init__(self, installer: Optional[PluginInstaller] = None):
        """
        Initialize the installation manager.

        Args:
            installer: Plugin installer to use (defaults to PipInstaller)
        """
        self.installer = installer or PipInstaller()
        self.catalog = get_catalog()

    def install_plugin(
        self, 
        plugin_name: str,
        dry_run: bool = False,
        force_version: Optional[str] = None
    ) -> bool:
        """
        Install a curated plugin.

        Args:
            plugin_name: Name of the plugin to install
            dry_run: If True, only check what would be installed
            force_version: Specific version/ref to install (overrides compatibility)

        Returns:
            True if installation succeeded

        Raises:
            ValueError: If plugin is not in curated catalog
            RuntimeError: If no compatible version found
        """
        plugin_info = self.catalog.get_plugin(plugin_name)

        if not plugin_info:
            plugins = ', '.join(p.name for p in self.catalog.list_plugins())
            raise ValueError(
                f"Plugin '{plugin_name}' is not in the curated catalog.\n"
                f"Available plugins: {plugins}"
            )

        # Warn about authentication if needed
        if plugin_info.requires_auth:
            logger.warning(
                f"Plugin '{plugin_name}' requires authentication.\n"
                "Ensure you have configured Git credentials for "
                f"{plugin_info.source_spec.source}"
            )

        # Determine version/ref to install
        if force_version:
            version_spec = force_version
        else:
            version_spec = self.catalog.get_compatible_version(
                plugin_name,
                medcat.__version__
            )

            if not version_spec:
                raise RuntimeError(
                    f"No compatible version of '{plugin_name}' found for "
                    f"MedCAT {medcat.__version__}.\n"
                    f"Visit {plugin_info.homepage} for more information."
                )

        spec = PluginInstallSpec(
            name=plugin_name,
            version_spec=version_spec,
            source_spec=plugin_info.source_spec,
        )

        logger.info(
            f"Installing {plugin_info.display_name} "
            f"({plugin_name}{version_spec})"
        )

        if plugin_info.source_spec.subdirectory:
            logger.info(f"  From subdirectory: {plugin_info.source_spec.subdirectory}")

        try:
            return self.installer.install(spec, dry_run=dry_run)
        except subprocess.CalledProcessError as e:
            # Provide helpful error messages
            if "subdirectory" in spec.to_pip_spec():
                logger.error(
                    "Installation failed. This plugin is in a subdirectory.\n"
                    "Common issues:\n"
                    "  - The subdirectory path might be incorrect\n"
                    f"  - The git ref '{version_spec}' might not exist\n"
                    "  - setup.py/pyproject.toml might be missing in the subdirectory"
                )

            if plugin_info.requires_auth:
                logger.error(
                    "Authentication might be required.\n"
                    "Configure git credentials with:\n"
                    "  git config --global credential.helper store"
                )

            raise


    def install_multiple(
        self, 
        plugin_names: list[str],
        dry_run: bool = False
    ) -> dict:
        """
        Install multiple plugins.

        Returns:
            Dictionary mapping plugin names to success status
        """
        results = {}
        for name in plugin_names:
            try:
                results[name] = self.install_plugin(name, dry_run=dry_run)
            except Exception as e:
                logger.error(f"Failed to install {name}: {e}")
                results[name] = False

        return results
