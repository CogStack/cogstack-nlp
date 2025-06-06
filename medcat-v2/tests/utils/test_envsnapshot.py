from medcat.utils import envsnapshot

import unittest


class DependencyGetterTests(unittest.TestCase):
    # NOTE: when installing you get 14 with medcat
    NUM_EXPECTED_DEPS_NO_SPACY = 13
    INCLUDE_EXTRAS = False

    @classmethod
    def setUpClass(cls):
        cls.dir_deps = [
            dep.lower() for dep in
            envsnapshot.get_direct_dependencies(cls.INCLUDE_EXTRAS)]
        cls.installed_deps = {
            dep.lower(): version for dep, version in
            envsnapshot.get_installed_dependencies(cls.INCLUDE_EXTRAS).items()
        }
        cls.trans_deps = envsnapshot.get_transitive_deps(
            list(cls.installed_deps.keys()))

    def test_dir_deps_have_no_version(self):
        for dep in self.dir_deps:
            with self.subTest(dep):
                self.assertNotIn("=", dep)
                self.assertNotIn("<", dep)
                self.assertNotIn(">", dep)

    def test_all_dir_deps_have_been_installed(self):
        for dep in self.dir_deps:
            with self.subTest(dep):
                self.assertIn(dep, self.installed_deps)

    def test_all_deps_add_to_correct(self):
        # NOTE: didn't account for test/dev deps
        self.assertGreaterEqual(len(self.dir_deps) + len(self.trans_deps),
                                self.NUM_EXPECTED_DEPS_NO_SPACY)


class DependencyGetterWithExtrasTests(DependencyGetterTests):
    NUM_EXPECTED_ADD_DEPS_SPACY = 34
    NUM_EXPECTED_DEPS_NO_SPACY = (
        DependencyGetterTests.NUM_EXPECTED_DEPS_NO_SPACY +
        NUM_EXPECTED_ADD_DEPS_SPACY)
    INCLUDE_EXTRAS = True


class EnvSnapshotTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.env = envsnapshot.get_environment_info()

    def test_gets_environment(self):
        self.assertIsInstance(self.env, envsnapshot.Environment)

    def test_has_deps(self):
        self.assertGreater(len(self.env.dependencies), 0)

    def test_has_trans_deps(self):
        self.assertGreater(len(self.env.transitive_deps), 0)

    def test_has_os(self):
        self.assertTrue(self.env.os)

    def test_has_arch(self):
        self.assertTrue(self.env.cpu_arcitecture)

    def test_has_py_version(self):
        self.assertTrue(self.env.python_version)

    def test_has_py3(self):
        self.assertIn("3.", self.env.python_version)
        self.assertTrue(self.env.python_version.startswith("3."))
