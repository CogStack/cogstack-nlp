from medcat.utils import import_utils

import unittest
import unittest.mock


class ImportUtilsTests(unittest.TestCase):

    @unittest.mock.patch(
            "medcat.utils.import_utils.get_installed_extra_dependencies")
    @unittest.mock.patch("medcat.utils.import_utils.get_required_extra_deps")
    def test_raises_upon_partial(
            self,
            mock_get_required_extra_deps,
            mock_get_installed_extra_dependencies):
        mock_get_installed_extra_dependencies.return_value = {"A", "B"}
        mock_get_required_extra_deps.return_value = {"A", "B", "C"}
        with self.assertRaises(import_utils.MissingDependenciesError):
            import_utils.ensure_optional_extras_installed("medcat", "WHATEVER")

    @unittest.mock.patch(
            "medcat.utils.import_utils.get_installed_extra_dependencies")
    @unittest.mock.patch("medcat.utils.import_utils.get_required_extra_deps")
    def test_raises_upon_none(
            self,
            mock_get_required_extra_deps,
            mock_get_installed_extra_dependencies):
        mock_get_installed_extra_dependencies.return_value = set()
        mock_get_required_extra_deps.return_value = {"A", "B", "C"}
        with self.assertRaises(import_utils.MissingDependenciesError):
            import_utils.ensure_optional_extras_installed("medcat", "WHATEVER")

    @unittest.mock.patch(
            "medcat.utils.import_utils.get_installed_extra_dependencies")
    @unittest.mock.patch("medcat.utils.import_utils.get_required_extra_deps")
    def test_no_raises_upon_all_deps(
            self,
            mock_get_required_extra_deps,
            mock_get_installed_extra_dependencies):
        mock_get_installed_extra_dependencies.return_value = {"A", "B", "C"}
        mock_get_required_extra_deps.return_value = {"A", "B", "C"}
        # NOTE: just no raise
        import_utils.ensure_optional_extras_installed("medcat", "WHATEVER")
