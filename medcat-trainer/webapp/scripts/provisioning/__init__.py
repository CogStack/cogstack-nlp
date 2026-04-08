"""Provisioning: YAML config for example projects to load on startup."""

from pathlib import Path

import yaml
from .model import ProvisioningConfig


def load_example_projects_config(path: str | Path) -> ProvisioningConfig:
    """Load and validate the example-projects YAML config from a file path."""
    
    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        raise ValueError(f"Empty or invalid YAML: {path}")
    return ProvisioningConfig.model_validate(data)
