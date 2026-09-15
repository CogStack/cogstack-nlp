import subprocess
import sys
import tempfile
import textwrap

import unittest


class EnvAtImportTimeTests(unittest.TestCase):

    def test_import_time_behavior(self):
        # Create a test script that patches before import
        test_script = textwrap.dedent("""
        import unittest.mock

        # Patch BEFORE importing medcat
        with unittest.mock.patch(
                'medcat.utils.envsnapshot.get_environment_info'
                ) as mock_get_env:
            mock_get_env.side_effect = Exception(
                "Should not be called at import time!")

            try:
                from medcat.config.config import ModelMeta
                print("SUCCESS: Import completed without "
                      "calling get_environment_info")
            except Exception as e:
                if "Should not be called at import time" in str(e):
                    print("FAILED: get_environment_info was called "
                          "during import")
                    raise
                else:
                    print(f"OTHER ERROR: {e}")
                    raise
        """)

        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False) as f:
            f.write(test_script)
            f.flush()
            result = subprocess.run(
                [sys.executable, f.name], capture_output=True, text=True)

            if result.returncode != 0:
                raise AssertionError(
                    "Import test failed:\n"
                    f"STDOUT: {result.stdout}\n"
                    f"STDERR: {result.stderr}")
            self.assertIn("SUCCESS", result.stdout)
