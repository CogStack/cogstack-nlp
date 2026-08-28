import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from medcat.plugins.downloadable import PluginInstallSpec, PluginSourceSpec
from medcat.plugins.installer import PipInstaller, PluginInstallationManager


class TestPipInstaller(unittest.TestCase):

    @patch("medcat.plugins.installer.subprocess.run")
    def test_install_success(self, mock_run):
        mock_run.return_value = SimpleNamespace(stdout="ok")
        installer = PipInstaller()
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="==1.0.0",
            source_spec=PluginSourceSpec(
                source="example-plugin",
                source_type="pypi",
            ),
        )

        result = installer.install(spec)

        self.assertTrue(result)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        # basic sanity checks on the constructed pip command
        self.assertIn("pip", cmd)
        self.assertIn(spec.to_pip_spec(), cmd)

    @patch("medcat.plugins.installer.subprocess.run")
    def test_install_dry_run_includes_flag(self, mock_run):
        mock_run.return_value = SimpleNamespace(stdout="ok")
        installer = PipInstaller()
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="==1.0.0",
            source_spec=PluginSourceSpec(
                source="example-plugin",
                source_type="pypi",
            ),
        )

        result = installer.install(spec, dry_run=True)

        self.assertTrue(result)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("--dry-run", cmd)

    @patch(
        "medcat.plugins.installer.subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd=["pip"], stderr="boom"
        ),
    )
    def test_install_failure_returns_false(self, mock_run):
        installer = PipInstaller()
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="==1.0.0",
            source_spec=PluginSourceSpec(
                source="example-plugin",
                source_type="pypi",
            ),
        )

        result = installer.install(spec)

        self.assertFalse(result)
        mock_run.assert_called_once()

    @patch("medcat.plugins.installer.subprocess.run")
    def test_is_available_true(self, mock_run):
        mock_run.return_value = SimpleNamespace(stdout="pip 23.0")
        installer = PipInstaller()

        self.assertTrue(installer.is_available())
        mock_run.assert_called_once()

    @patch(
        "medcat.plugins.installer.subprocess.run",
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd=["pip"], stderr="boom"
        ),
    )
    def test_is_available_false_on_error(self, mock_run):
        installer = PipInstaller()

        self.assertFalse(installer.is_available())
        mock_run.assert_called_once()

    @patch(
        "medcat.plugins.installer.subprocess.run",
        side_effect=FileNotFoundError("python not found"),
    )
    def test_is_available_false_on_missing_python(self, mock_run):
        installer = PipInstaller()

        self.assertFalse(installer.is_available())
        mock_run.assert_called_once()

    def test_get_name(self):
        installer = PipInstaller()
        self.assertEqual(installer.get_name(), "pip")


class TestPluginInstallationManager(unittest.TestCase):

    @patch("medcat.plugins.installer.get_catalog")
    def test_install_plugin_unknown_raises_value_error(self, mock_get_catalog):
        fake_catalog = MagicMock()
        fake_catalog.get_plugin.return_value = None
        fake_catalog.list_plugins.return_value = [
            SimpleNamespace(name="other-plugin", display_name="Other Plugin")
        ]
        mock_get_catalog.return_value = fake_catalog

        manager = PluginInstallationManager(installer=MagicMock())

        with self.assertRaises(ValueError) as ctx:
            manager.install_plugin("missing-plugin")

        msg = str(ctx.exception)
        self.assertIn("missing-plugin", msg)
        self.assertIn("Available plugins", msg)
        self.assertIn("other-plugin", msg)

    @patch("medcat.plugins.installer.get_catalog")
    @patch("medcat.plugins.installer.medcat")
    def test_install_plugin_no_compatible_version_raises_runtime_error(
        self,
        mock_medcat,
        mock_get_catalog,
    ):
        mock_medcat.__version__ = "2.5.0"

        plugin_info = SimpleNamespace(
            name="example-plugin",
            display_name="Example Plugin",
            description="",
            source_spec=PluginSourceSpec(
                source="https://github.com/example/example-plugin",
                source_type="github_subdir",
                subdirectory="plugins/example",
            ),
            homepage="https://example.com/example-plugin",
            compatibility=[],
            requires_auth=False,
        )
        fake_catalog = MagicMock()
        fake_catalog.get_plugin.return_value = plugin_info
        fake_catalog.get_compatible_version.return_value = None
        mock_get_catalog.return_value = fake_catalog

        manager = PluginInstallationManager(installer=MagicMock())

        with self.assertRaises(RuntimeError) as ctx:
            manager.install_plugin("example-plugin")

        msg = str(ctx.exception)
        self.assertIn("No compatible version of 'example-plugin' found", msg)
        self.assertIn("2.5.0", msg)

    @patch("medcat.plugins.installer.get_catalog")
    def test_install_plugin_uses_force_version_over_compat(self, mock_get_catalog):
        plugin_info = SimpleNamespace(
            name="example-plugin",
            display_name="Example Plugin",
            description="",
            source_spec=PluginSourceSpec(
                source="example-plugin",
                source_type="pypi",
                subdirectory=None,
            ),
            homepage="https://example.com/example-plugin",
            compatibility=[],
            requires_auth=False,
        )
        fake_catalog = MagicMock()
        fake_catalog.get_plugin.return_value = plugin_info
        fake_catalog.get_compatible_version.return_value = "==0.1.0"
        mock_get_catalog.return_value = fake_catalog

        fake_installer = MagicMock()
        fake_installer.install.return_value = True
        manager = PluginInstallationManager(installer=fake_installer)

        result = manager.install_plugin(
            "example-plugin", dry_run=True, force_version="==9.9.9"
        )

        self.assertTrue(result)
        fake_catalog.get_compatible_version.assert_not_called()
        fake_installer.install.assert_called_once()
        spec = fake_installer.install.call_args[0][0]
        self.assertIsInstance(spec, PluginInstallSpec)
        self.assertEqual(spec.version_spec, "==9.9.9")

    @patch("medcat.plugins.installer.get_catalog")
    @patch("medcat.plugins.installer.medcat")
    def test_install_plugin_uses_compatible_version_when_no_force(
        self,
        mock_medcat,
        mock_get_catalog,
    ):
        mock_medcat.__version__ = "2.5.0"

        plugin_info = SimpleNamespace(
            name="example-plugin",
            display_name="Example Plugin",
            description="",
            source_spec=PluginSourceSpec(
                source="example-plugin",
                source_type="pypi",
                subdirectory=None,
            ),
            homepage="https://example.com/example-plugin",
            compatibility=[],
            requires_auth=False,
        )
        fake_catalog = MagicMock()
        fake_catalog.get_plugin.return_value = plugin_info
        fake_catalog.get_compatible_version.return_value = "==1.2.3"
        mock_get_catalog.return_value = fake_catalog

        fake_installer = MagicMock()
        fake_installer.install.return_value = True
        manager = PluginInstallationManager(installer=fake_installer)

        result = manager.install_plugin("example-plugin", dry_run=False)

        self.assertTrue(result)
        fake_catalog.get_compatible_version.assert_called_once_with(
            "example-plugin", "2.5.0"
        )
        fake_installer.install.assert_called_once()
        spec = fake_installer.install.call_args[0][0]
        self.assertEqual(spec.version_spec, "==1.2.3")
        self.assertEqual(spec.source_spec.source, "example-plugin")
        self.assertEqual(spec.source_spec.source_type, "pypi")

    @patch("medcat.plugins.installer.get_catalog")
    def test_install_multiple_collects_results_and_handles_exceptions(
        self,
        mock_get_catalog,
    ):
        # We don't care about catalog behaviour here, only that
        # exceptions from install_plugin are converted into False.
        mock_get_catalog.return_value = MagicMock()

        manager = PluginInstallationManager(installer=MagicMock())

        with patch.object(
            manager,
            "install_plugin",
            side_effect=[True, Exception("boom"), False],
        ):
            results = manager.install_multiple(
                ["plugin-a", "plugin-b", "plugin-c"], dry_run=False
            )

        self.assertEqual(
            results,
            {
                "plugin-a": True,
                "plugin-b": False,
                "plugin-c": False,
            },
        )


if __name__ == "__main__":
    unittest.main()

