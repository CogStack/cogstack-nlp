import unittest
from types import SimpleNamespace
from unittest.mock import patch
from copy import deepcopy

import medcat.plugins.catalog as catalog_module
from medcat.plugins.catalog import (
    NoCompatibleSpecException,
    NoSuchPluginException,
    PluginCatalog,
    PluginCompatibility,
)


class IncludedCatalogSchemaTests(unittest.TestCase):

    def test_is_correct_format(self):
        with open(catalog_module.LOCAL_CATALOG_PATH) as f:
            text = f.read()
        catalog_module.CatalogModel.model_validate_json(text)


class CatalogMergeTests(unittest.TestCase):
    v1 = "v1"
    update1 = "at noon"
    v2 = "v2"
    update2 = "at night"
    v3 = "v3"
    update3 = "next morning"
    pl1_comp1 = catalog_module.PluginCompatibility(
        plugin_version="v0.1.0", medcat_version=">=2.5")
    pl1_comp2 = catalog_module.PluginCompatibility(
        plugin_version="v0.1.1", medcat_version=">=2.6")
    pl1 = catalog_module.PluginInfo(
        name='pl1', display_name='Plugin 1',
        description="Plugin 1 ...",
        source_spec=catalog_module.PluginSourceSpec(
            source="github", source_type="github"),
        homepage="www.google.com", requires_auth=False,
        compatibility=[pl1_comp1]
    )
    pl1_alt = catalog_module.PluginInfo(
        name='pl1', display_name='Plugin 1',
        description="Plugin 1 - UPDATED ...",
        source_spec=catalog_module.PluginSourceSpec(
            source="github", source_type="github"),
        homepage="www.google.com", requires_auth=False,
        compatibility=[pl1_comp1, pl1_comp2]
    )
    pl2_comp1 = catalog_module.PluginCompatibility(
        plugin_version="v0.2.0", medcat_version=">=2.3")
    pl2 = catalog_module.PluginInfo(
        name='pl2', display_name='Plugin 2',
        description="Plugin two ...",
        source_spec=catalog_module.PluginSourceSpec(
            source="github", source_type="github"),
        homepage="www.amazon.com", requires_auth=False,
        compatibility=[pl2_comp1]
    )
    plugins1 = {
        "pl1": pl1,
    }
    plugins2 = {
        "pl2": pl2,
    }
    plugins3 = {
        "pl1": pl1_alt,
        "pl2": pl2,
    }

    def _copy_catalog(self, catalog: catalog_module.CatalogModel) -> catalog_module.CatalogModel:
        model_dump = deepcopy(catalog.model_dump())
        return catalog_module.CatalogModel.model_validate(model_dump)

    def setUp(self) -> None:
        self.catalog1 = self._copy_catalog(catalog_module.CatalogModel(
            version=self.v1, last_updated=self.update1, plugins=self.plugins1
        ))
        self.catalog2 = self._copy_catalog(catalog_module.CatalogModel(
            version=self.v2, last_updated=self.update2, plugins=self.plugins2
        ))
        self.catalog3_update = self._copy_catalog(catalog_module.CatalogModel(
            version=self.v3, last_updated=self.update3, plugins=self.plugins3
        ))
        self.merged_2_into_1_po = self._copy_catalog(self.catalog1)
        self.merged_2_into_1_po.merge(self.catalog2, prefer_other=True)
        self.merged_2_into_1_ps = self._copy_catalog(self.catalog1)
        self.merged_2_into_1_ps.merge(self.catalog2, prefer_other=False)
        self.merged_3_into_1_po = self._copy_catalog(self.catalog1)
        self.merged_3_into_1_po.merge(self.catalog3_update, prefer_other=True)
        self.merged_3_into_1_ps = self._copy_catalog(self.catalog1)
        self.merged_3_into_1_ps.merge(self.catalog3_update, prefer_other=False)

    def test_catalog_merge_updates_version(self):
        assert self.merged_2_into_1_po.version == self.v2

    def test_catalog_merge_updates_update_date(self):
        assert self.merged_2_into_1_po.last_updated == self.update2

    def test_catalog_merge_can_leave_version(self):
        assert self.merged_2_into_1_ps.version == self.v1

    def test_catalog_merge_can_leave_date(self):
        assert self.merged_2_into_1_ps.last_updated == self.update1

    def assert_has_merged(
            self, part1: catalog_module.CatalogModel, part2: catalog_module,
            merged: catalog_module.CatalogModel):
        assert len(merged.plugins) >= len(part1.plugins)
        assert len(merged.plugins) >= len(part2.plugins)
        merged_plugins = set(merged.plugins.keys())
        downstream_plugins = set(part1.plugins.keys()) | set(part2.plugins.keys())
        assert merged_plugins == downstream_plugins

    def test_merge_adds_plugins_2_to_1_other(self):
        self.assert_has_merged(self.catalog1, self.catalog2, self.merged_2_into_1_po)

    def test_merge_adds_plugins_2_to_1_self(self):
        self.assert_has_merged(self.catalog1, self.catalog2, self.merged_2_into_1_ps)

    def test_merge_adds_plugins_3_to_1_other(self):
        self.assert_has_merged(self.catalog1, self.catalog3_update, self.merged_3_into_1_po)

    def test_merge_adds_plugins_3_to_1_self(self):
        self.assert_has_merged(self.catalog1, self.catalog3_update, self.merged_3_into_1_ps)

    def test_keeps_updated_info(self):
        merged_pl = self.merged_3_into_1_po.plugins[self.pl1.name]
        cat1_pl = self.catalog1.plugins[self.pl1.name]
        cat3_pl = self.catalog3_update.plugins[self.pl1.name]
        assert merged_pl.compatibility == cat3_pl.compatibility
        assert merged_pl.compatibility != cat1_pl.compatibility
        assert merged_pl.description == cat3_pl.description
        assert merged_pl.description != cat1_pl.description

    def test_can_keep_prior_info(self):
        merged_pl = self.merged_3_into_1_ps.plugins[self.pl1.name]
        cat1_pl = self.catalog1.plugins[self.pl1.name]
        cat3_pl = self.catalog3_update.plugins[self.pl1.name]
        assert merged_pl.compatibility != cat3_pl.compatibility
        assert merged_pl.compatibility == cat1_pl.compatibility
        assert merged_pl.description != cat3_pl.description
        assert merged_pl.description == cat1_pl.description


class TestPluginCatalogParsingAndQueries(unittest.TestCase):
    EXAMPLE_PLUGIN_NAME = 'example-plugin'

    def setUp(self):
        # Avoid network access in tests by not touching the remote catalog.
        self.catalog = PluginCatalog(use_remote=False)
        # Reset any data that might have been loaded in __init__
        self.catalog._catalog.plugins.clear()

        # Populate the catalog with a simple in-memory definition
        self.catalog._parse_catalog(
            {
                "version": "0.0test",
                "last_updated": "test-time",
                "plugins": {
                    self.EXAMPLE_PLUGIN_NAME: {
                        "name": "example-plugin",
                        "display_name": "Example Plugin",
                        "description": "Test plugin",
                        "source_spec": {
                            "source": self.EXAMPLE_PLUGIN_NAME,
                            "source_type": "pypi",
                            "subdirectory": "plugins/example"
                        },
                        "homepage": "https://example.com/example-plugin",
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
        self.assertEqual(plugin.source_spec.subdirectory, "plugins/example")
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

