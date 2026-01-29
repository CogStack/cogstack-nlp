"""Protocol definitions for plugin installation backends."""

from typing import Protocol, Optional
from pydantic import BaseModel
import re


class PluginSourceSpec(BaseModel):
    """Where and how to obtain a plugin."""
    source: str  # PyPI package name, GitHub URL, SSH URL, etc.
    source_type: str
    # this includes: "pypi", "github", "github_subdir",
    # "github_ssh", "github_ssh_subdir", "url"
    subdirectory: Optional[str] = None  # Path within repo, e.g., "plugins/negation"


class PluginInstallSpec(BaseModel):
    """Specification for installing a plugin."""
    name: str
    version_spec: str  # e.g., ">=1.0.0,<2.0.0" or git ref like "main", "v1.2.3"
    source_spec: PluginSourceSpec

    def to_pip_spec(self) -> str:
        """Convert to pip-installable spec."""
        src = self.source_spec
        if src.source_type == "pypi":
            return f"{src.source}{self.version_spec}"
        elif src.source_type == "github":
            # Standard GitHub install
            return f"git+{src.source}@{self.version_spec}"
        elif src.source_type == "github_subdir":
            # GitHub with subdirectory
            # Format: git+https://github.com/user/repo.git@ref#subdirectory=path/to/plugin
            base_url = src.source.rstrip('/')
            if not base_url.endswith('.git'):
                base_url += '.git'

            spec = f"git+{base_url}@{self.version_spec}"
            if src.subdirectory:
                spec += f"#subdirectory={src.subdirectory}"
            return spec
        elif src.source_type == "github_ssh":
            # GitHub SSH install
            # Format: git+ssh://git@github.com/user/repo.git@ref
            ssh_url = self._normalize_ssh_url(src.source)
            return f"git+{ssh_url}@{self.version_spec}"
        elif src.source_type == "github_ssh_subdir":
            # GitHub SSH with subdirectory
            # Format: git+ssh://git@github.com/user/repo.git@ref#subdirectory=path
            ssh_url = self._normalize_ssh_url(src.source)
            spec = f"git+{ssh_url}@{self.version_spec}"
            if src.subdirectory:
                spec += f"#subdirectory={src.subdirectory}"
            return spec
        elif src.source_type == "url":
            # Direct URL (could be a tarball, wheel, etc.)
            return src.source
        else:
            raise ValueError(f"Unknown source_type: {src.source_type}")

    @staticmethod
    def _normalize_ssh_url(url: str) -> str:
        """
        Normalize SSH URL to the format pip expects.

        Handles various SSH URL formats:
        - git@github.com:user/repo.git
        - ssh://git@github.com/user/repo.git
        - git@github.com:user/repo

        Returns: ssh://git@github.com/user/repo.git
        """
        # Already in ssh:// format
        if url.startswith("ssh://"):
            if not url.endswith('.git'):
                url += '.git'
            return url

        # Convert git@github.com:user/repo.git to ssh://git@github.com/user/repo.git
        if '@' in url and ':' in url:
            # Pattern: git@github.com:user/repo.git
            match = re.match(r'^git@([^:]+):(.+?)(?:\.git)?$', url)
            if match:
                host, path = match.groups()
                return f"ssh://git@{host}/{path}.git"

        # If we can't parse it, return as-is and let pip handle it
        return url


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
