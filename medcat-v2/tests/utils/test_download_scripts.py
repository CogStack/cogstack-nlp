from medcat.utils import donwload_scripts

import unittest
import tempfile


class ScriptsDownloadTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.scripts_path = download_scripts.fetch_scripts(cls._temp_dir.name)

    def test_can_download(self):
        self.assertTrue(os.path.exists(self.scripts_path))
        self.assertTrue(os.path.isdir(self.scripts_path))
        self.assertTrue(os.listdir(self.scripts_path))

    def test_has_requirements(self):
        self.assertIn('requirements.txt', os.listdir(self.scripts_path))
