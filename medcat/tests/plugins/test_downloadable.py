import unittest

from medcat.plugins.downloadable import PluginInstallSpec, PluginSourceSpec


class TestPluginInstallSpec(unittest.TestCase):

    def test_to_pip_spec_pypi(self):
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="==1.2.3",
            source_spec=PluginSourceSpec(
                source="example-plugin",
                source_type="pypi",
            ),
        )

        self.assertEqual(spec.to_pip_spec(), "example-plugin==1.2.3")

    def test_to_pip_spec_github(self):
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="v1.0.0",
            source_spec=PluginSourceSpec(
                source="https://github.com/example/example-plugin",
                source_type="github",
            ),
        )

        self.assertEqual(
            spec.to_pip_spec(),
            "git+https://github.com/example/example-plugin@v1.0.0",
        )

    def test_to_pip_spec_github_subdir_adds_git_and_subdir(self):
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="main",
            source_spec=PluginSourceSpec(
                source="https://github.com/example/example-plugin",
                source_type="github_subdir",
                subdirectory="plugins/example",
            ),
        )

        self.assertEqual(
            spec.to_pip_spec(),
            "git+https://github.com/example/example-plugin.git"
            "@main#subdirectory=plugins/example",
        )

    def test_to_pip_spec_github_subdir_without_subdir(self):
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="main",
            source_spec=PluginSourceSpec(
                source="https://github.com/example/example-plugin",
                source_type="github_subdir",
            ),
        )

        self.assertEqual(
            spec.to_pip_spec(),
            "git+https://github.com/example/example-plugin.git@main",
        )

    def test_to_pip_spec_url_source_type(self):
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="",  # ignored for url
            source_spec=PluginSourceSpec(
                source="https://example.com/example-plugin-1.0.0.whl",
                source_type="url",
            ),
        )

        self.assertEqual(
            spec.to_pip_spec(),
            "https://example.com/example-plugin-1.0.0.whl",
        )

    def test_to_pip_spec_unknown_source_type_raises(self):
        spec = PluginInstallSpec(
            name="example-plugin",
            version_spec="==1.0.0",
            source_spec=PluginSourceSpec(
                source="example-plugin",
                source_type="unknown-source",
            ),
        )

        with self.assertRaises(ValueError):
            spec.to_pip_spec()


if __name__ == "__main__":
    unittest.main()

