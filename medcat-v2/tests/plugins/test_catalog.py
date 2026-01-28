import unittest
from types import SimpleNamespace
from unittest.mock import patch

import medcat.plugins.catalog as catalog_module
from medcat.plugins.catalog import (
    NoCompatibleSpecException,
    NoSuchPluginException,
    PluginCatalog,
)


class TestPluginCatalogParsingAndQueries(unittest.TestCase):
    EXAMPLE_PLUGIN_NAME = 'example-plugin'

    def setUp(self):
        # Avoid network access in tests by not touching the remote catalog.
        self.catalog = PluginCatalog(use_remote=False)
        # Reset any data that might have been loaded in __init__
        self.catalog._catalog = {}

        # Populate the catalog with a simple in-memory definition
        self.catalog._parse_catalog(
            {
                "plugins": {
                    self.EXAMPLE_PLUGIN_NAME: {
                        "display_name": "Example Plugin",
                        "description": "Test plugin",
                        "source": self.EXAMPLE_PLUGIN_NAME,
                        "source_type": "pypi",
                        "homepage": "https://example.com/example-plugin",
                        "subdirectory": "plugins/example",
                        "requires_auth": True,
                        "compatibility": [
                            {
                                "medcat_version": ">=1.0.0,<2.0.0",
                                "plugin_version": "==1.2.3",
                            },
                            {
                                "medcat_version": ">=2.0.0",
                                "plugin_version": "==2.0.0",
                            },
                        ],
                    }
                }
            }
        )

    def test_get_plugin_and_is_curated(self):
        plugin = self.catalog.get_plugin(self.EXAMPLE_PLUGIN_NAME)
        self.assertIsNotNone(plugin)
        self.assertTrue(self.catalog.is_curated(self.EXAMPLE_PLUGIN_NAME))
        self.assertEqual(plugin.display_name, "Example Plugin")
        self.assertEqual(plugin.subdirectory, "plugins/example")
        self.assertTrue(plugin.requires_auth)

    def test_list_plugins_returns_all(self):
        plugins = self.catalog.list_plugins()
        self.assertEqual(len(plugins), 1)
        self.assertEqual(plugins[0].name, self.EXAMPLE_PLUGIN_NAME)

    def test_get_compatible_version_success_first_spec(self):
        version = self.catalog.get_compatible_version(self.EXAMPLE_PLUGIN_NAME, "1.5.0")
        self.assertEqual(version, "==1.2.3")

    def test_get_compatible_version_success_second_spec(self):
        version = self.catalog.get_compatible_version(self.EXAMPLE_PLUGIN_NAME, "2.1.0")
        self.assertEqual(version, "==2.0.0")

    def test_get_compatible_version_no_such_plugin_raises(self):
        with self.assertRaises(NoSuchPluginException):
            self.catalog.get_compatible_version("missing-plugin", "1.0.0")

    def test_get_compatible_version_no_compatible_spec_raises(self):
        with self.assertRaises(NoCompatibleSpecException):
            self.catalog.get_compatible_version("example-plugin", "0.5.0")


class TestGetCatalogSingleton(unittest.TestCase):

    def tearDown(self):
        # Reset the module-level singleton between tests
        catalog_module._catalog = None

    @patch.object(catalog_module, "PluginCatalog")
    def test_get_catalog_returns_singleton(self, mock_catalog_cls):
        fake_instance = SimpleNamespace()
        mock_catalog_cls.return_value = fake_instance

        first = catalog_module.get_catalog()
        second = catalog_module.get_catalog()

        self.assertIs(first, second)
        mock_catalog_cls.assert_called_once()


if __name__ == "__main__":
    unittest.main()

