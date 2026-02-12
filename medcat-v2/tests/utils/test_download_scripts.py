from medcat.utils import download_scripts

import os
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

    def test_requirements_define_correct_version(self):
        cur_version = download_scripts._get_medcat_version()
        req_path = os.path.join(self.scripts_path, 'requirements.txt')
        with open(req_path) as f:
            medcat_line = [line.strip() for line in f if "medcat" in line]
        self.assertIsIn(cur_version, medcat_line)
        self.assertTrue(medcat_line.endswith(cur_version))
