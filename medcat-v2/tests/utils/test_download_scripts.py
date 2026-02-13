from medcat.utils import download_scripts

import os
import unittest
import unittest.mock
import tempfile


class ScriptsDownloadTest(unittest.TestCase):
    use_version = "2.5"

    @classmethod
    def setUpClass(cls):
        cls._temp_dir = tempfile.TemporaryDirectory()
        with unittest.mock.patch(
                "medcat.utils.download_scripts._get_medcat_version"
                ) as mock_get_version:
            mock_get_version.return_value = cls.use_version
            cls.scripts_path = download_scripts.fetch_scripts(cls._temp_dir.name)

    def test_can_download(self):
        self.assertTrue(os.path.exists(self.scripts_path))
        self.assertTrue(os.path.isdir(self.scripts_path))
        self.assertTrue(os.listdir(self.scripts_path))

    def test_has_requirements(self):
        self.assertIn('requirements.txt', os.listdir(self.scripts_path))

    def test_requirements_define_correct_version(self):
        req_path = os.path.join(self.scripts_path, 'requirements.txt')
        with open(req_path) as f:
            medcat_line = [line.strip() for line in f if "medcat" in line][0]
        self.assertIn(self.use_version, medcat_line)
        self.assertTrue(medcat_line.endswith(self.use_version))
