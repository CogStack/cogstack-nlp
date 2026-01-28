"""Protocol definitions for plugin installation backends."""

from typing import Protocol, Optional
from dataclasses import dataclass


@dataclass
class PluginInstallSpec:
    """Specification for installing a plugin."""
    name: str
    version_spec: str  # e.g., ">=1.0.0,<2.0.0" or git ref like "main", "v1.2.3"
    source: str  # PyPI package name, GitHub URL, etc.
    source_type: str  # "pypi", "github", "github_subdir", "url"
    subdirectory: Optional[str] = None  # Path within repo, e.g., "plugins/negation"

    def to_pip_spec(self) -> str:
        """Convert to pip-installable spec."""
        if self.source_type == "pypi":
            return f"{self.source}{self.version_spec}"
        elif self.source_type == "github":
            # Standard GitHub install
            return f"git+{self.source}@{self.version_spec}"
        elif self.source_type == "github_subdir":
            # GitHub with subdirectory
            # Format: git+https://github.com/user/repo.git@ref#subdirectory=path/to/plugin
            base_url = self.source.rstrip('/')
            if not base_url.endswith('.git'):
                base_url += '.git'

            spec = f"git+{base_url}@{self.version_spec}"
            if self.subdirectory:
                spec += f"#subdirectory={self.subdirectory}"
            return spec
        elif self.source_type == "url":
            # Direct URL (could be a tarball, wheel, etc.)
            return self.source
        else:
            raise ValueError(f"Unknown source_type: {self.source_type}")


class PluginInstaller(Protocol):
    """Protocol for plugin installation backends."""

    def install(self, spec: PluginInstallSpec, dry_run: bool = False) -> bool:
        """
        Install a plugin.

        Args:
            spec: Plugin installation specification
            dry_run: If True, only check what would be installed

        Returns:
            True if successful, False otherwise
        """
        pass
    
    def is_available(self) -> bool:
        """Check if this installer is available in the environment."""
        pass

    def get_name(self) -> str:
        """Get the name of this installer (e.g., 'pip', 'uv')."""
        pass


class CredentialProvider(Protocol):
    """Protocol for providing credentials for private repositories."""

    def get_credentials(self, source: str) -> Optional[dict]:
        """
        Get credentials for a given source.

        Args:
            source: The source URL or identifier

        Returns:
            Dictionary with credentials (e.g., {'token': '...'}) or None
        """
        pass
