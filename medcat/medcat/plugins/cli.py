"""CLI entrypoint for MedCAT commands."""

import sys

from medcat.plugins.installer import PluginInstallationManager


# TODO: plugin listing and stuff like that


def install_plugins_command(*args: str):
    opts = [arg for arg in args if arg.startswith("--")]
    plugins = [arg for arg in args if arg not in opts]
    dry_run = "--dry-run" in opts

    manager = PluginInstallationManager()

    if not plugins:
        print("Error: No plugins specified", file=sys.stderr)
        return 1

    results = manager.install_multiple(plugins, dry_run=dry_run)

    failed = [name for name, success in results.items() if not success]

    if failed:
        print(f"Failed to install: {', '.join(failed)}", file=sys.stderr)
        return 1

    print(f"Successfully installed: {', '.join(results.keys())}")
    return 0
