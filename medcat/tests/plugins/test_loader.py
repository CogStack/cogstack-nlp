import unittest
from unittest.mock import patch, MagicMock
from importlib.metadata import EntryPoint

from medcat.plugins.loader import load_plugins, _load_plugin, ENTRY_POINT_PATH, _get_changes
from medcat.plugins.registry import plugin_registry, PluginInfo, RegisteredComponents, create_empty_reg_comps
from medcat.components.types import CoreComponentType

class TestPluginLoader(unittest.TestCase):

    def setUp(self):
        # Clear the registry before each test
        plugin_registry._plugins = {}

    @patch('medcat.plugins.loader.entry_points')
    @patch('medcat.plugins.loader.metadata')
    @patch('medcat.components.types.get_registered_components')
    @patch('medcat.components.addons.addons.get_registered_addons')
    def test_load_plugins_empty(self,
                               mock_get_registered_addons,
                               mock_get_registered_components,
                               mock_metadata,
                               mock_entry_points):
        mock_entry_points.return_value = []
        load_plugins()
        self.assertEqual(len(plugin_registry.get_all_plugins()), 0)

    @patch('medcat.plugins.loader._load_plugin')
    @patch('medcat.plugins.loader.entry_points')
    def test_load_plugins_multiple(self, mock_entry_points, mock_load_plugin):
        mock_ep1 = MagicMock(spec=EntryPoint)
        mock_ep1.name = "mock-plugin-1"
        mock_ep1.value = "mock_plugin_module1:load"
        mock_ep1.group = ENTRY_POINT_PATH

        mock_ep2 = MagicMock(spec=EntryPoint)
        mock_ep2.name = "mock-plugin-2"
        mock_ep2.value = "mock_plugin_module2:load"
        mock_ep2.group = ENTRY_POINT_PATH

        mock_entry_points.return_value = [mock_ep1, mock_ep2]
        load_plugins()

        self.assertEqual(mock_load_plugin.call_count, 2)
        mock_load_plugin.assert_any_call(mock_ep1)
        mock_load_plugin.assert_any_call(mock_ep2)

    def test_get_changes_identifies_new_components(self):
        before_comps: RegisteredComponents = {
            "core": {
                CoreComponentType.ner.name: []
            },
            "addons": []
        }

        after_comps: RegisteredComponents = {
            "core": {
                CoreComponentType.ner.name: [("mock_ner", "mock_module.MockNER.create")]
            },
            "addons": [("mock_addon", "mock_addon_module.MockAddon.create")]
        }

        newly_registered = _get_changes(before_comps, after_comps)

        self.assertIn(CoreComponentType.ner.name, newly_registered["core"])
        self.assertEqual(newly_registered["core"][CoreComponentType.ner.name],
                         [("mock_ner", "mock_module.MockNER.create")])
        self.assertEqual(newly_registered["addons"],
                         [("mock_addon", "mock_addon_module.MockAddon.create")])

    @patch('medcat.plugins.loader.metadata')
    @patch('medcat.plugins.loader.EntryPoint.load')
    @patch('medcat.plugins.loader._get_changes')
    def test_load_plugin_with_different_entrypoint_and_distribution_name(
            self,
            mock_get_changes,
            mock_ep_load,
            mock_metadata):
        mock_get_changes.return_value = {
            "core": {
                "ner": [("test_ner_comp", "test_module.TestNER.create")]
            },
            "addons": [("test_addon_comp", "test_module.TestAddon.create")]}

        # Mock EntryPoint with different name and dist.name
        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "my-plugin-entrypoint"
        mock_ep.value = "my_plugin.module:load_func"
        mock_ep.group = ENTRY_POINT_PATH
        mock_ep.dist.name = "my-plugin-package"  # Actual distribution name

        # Mock metadata to return info for the distribution name
        mock_metadata.return_value = {
            "Name": "My Awesome Plugin",
            "Version": "0.0.1",
            "Author": "Plugin Author",
            "Home-page": "http://plugin.com"
        }

        _load_plugin(mock_ep)

        # Assert metadata was called with the distribution name
        mock_metadata.assert_called_once_with("my-plugin-package")

        # Assert the plugin was registered correctly
        all_plugins = plugin_registry.get_all_plugins()
        self.assertEqual(len(all_plugins), 1)
        registered_plugin = all_plugins["My Awesome Plugin"]

        self.assertEqual(registered_plugin.name, "My Awesome Plugin")
        self.assertEqual(registered_plugin.version, "0.0.1")
        self.assertEqual(registered_plugin.author, "Plugin Author")
        self.assertEqual(registered_plugin.url, "http://plugin.com")
        self.assertIn(("test_ner_comp", "test_module.TestNER.create"),
                      registered_plugin.registered_components["core"][CoreComponentType.ner.name])
        self.assertIn(("test_addon_comp", "test_module.TestAddon.create"),
                      registered_plugin.registered_components["addons"])
