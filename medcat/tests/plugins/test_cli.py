import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import MagicMock, patch

from medcat.plugins.cli import install_plugins_command


class TestInstallPluginsCommand(unittest.TestCase):

    @patch("medcat.plugins.cli.PluginInstallationManager")
    def test_no_plugins_returns_error_and_message(self, mock_manager_cls):
        # Even when no plugins are provided, the CLI constructs the manager
        mock_manager_cls.return_value = MagicMock()

        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = install_plugins_command()

        self.assertEqual(code, 1)
        self.assertIn("No plugins specified", err.getvalue())
        mock_manager_cls.assert_called_once()

    @patch("medcat.plugins.cli.PluginInstallationManager")
    def test_successful_install_prints_success_and_returns_zero(self, mock_manager_cls):
        manager = MagicMock()
        manager.install_multiple.return_value = {
            "plugin-a": True,
            "plugin-b": True,
        }
        mock_manager_cls.return_value = manager

        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = install_plugins_command("plugin-a", "plugin-b")

        self.assertEqual(code, 0)
        manager.install_multiple.assert_called_once_with(
            ["plugin-a", "plugin-b"], dry_run=False
        )
        self.assertIn(
            "Successfully installed: plugin-a, plugin-b",
            out.getvalue(),
        )
        self.assertEqual("", err.getvalue())

    @patch("medcat.plugins.cli.PluginInstallationManager")
    def test_failed_install_prints_failures_and_returns_non_zero(
        self, mock_manager_cls
    ):
        manager = MagicMock()
        manager.install_multiple.return_value = {
            "plugin-a": True,
            "plugin-b": False,
        }
        mock_manager_cls.return_value = manager

        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = install_plugins_command("plugin-a", "plugin-b")

        self.assertEqual(code, 1)
        manager.install_multiple.assert_called_once_with(
            ["plugin-a", "plugin-b"], dry_run=False
        )
        self.assertIn("Failed to install: plugin-b", err.getvalue())

    @patch("medcat.plugins.cli.PluginInstallationManager")
    def test_dry_run_flag_is_passed_to_manager(self, mock_manager_cls):
        manager = MagicMock()
        manager.install_multiple.return_value = {
            "plugin-a": True,
        }
        mock_manager_cls.return_value = manager

        out = io.StringIO()
        err = io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = install_plugins_command("--dry-run", "plugin-a")

        self.assertEqual(code, 0)
        manager.install_multiple.assert_called_once_with(
            ["plugin-a"], dry_run=True
        )
        self.assertIn("Successfully installed: plugin-a", out.getvalue())
        self.assertEqual("", err.getvalue())


if __name__ == "__main__":
    unittest.main()

