import io
import json
import logging
import time
import unittest
from unittest.mock import patch
from pathlib import Path
from medcat.utils import check_for_updates


class TestVersionCheck(unittest.TestCase):

    def setUp(self):
        self.pkg = "medcat"
        self.current_version = "1.3.0"
        self.cache_path = Path("/tmp/fake_cache.json")

    def tearDown(self):
        if self.cache_path.exists():
            self.cache_path.unlink()

    # --- helpers ---
    def _make_releases(self, versions, yanked=None):
        """Return a fake releases dict."""
        yanked = yanked or {}
        return {
            v: [{"yanked": yanked.get(v, False)}]
            for v in versions
        }

    # 1. runs if cache missing
    @patch("medcat.utils.check_for_updates._do_check")
    @patch("medcat.utils.check_for_updates.urllib.request.urlopen")
    def test_runs_without_cache(self, mock_urlopen, mock_do_check):
        data = {"releases": self._make_releases(["1.3.1", "1.3.2", "1.4.0"])}
        mock_urlopen.return_value.__enter__.return_value = io.StringIO(
            json.dumps(data))
        with patch("medcat.utils.check_for_updates.DEFAULT_CACHE_PATH",
                   self.cache_path):
            check_for_updates.check_for_updates(self.pkg, self.current_version)
        mock_do_check.assert_called_once()

    # 2. runs if cache interval expired
    @patch("medcat.utils.check_for_updates._do_check")
    @patch("medcat.utils.check_for_updates.urllib.request.urlopen")
    def test_runs_if_interval_expired(self, mock_urlopen, mock_do_check):
        data = {"releases": self._make_releases(["1.3.1"])}
        mock_urlopen.return_value.__enter__.return_value = io.StringIO(
            json.dumps(data))
        # create old cache
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump({"last_check": time.time() - (
                check_for_updates.DEFAULT_CHECK_INTERVAL + 1)}, f)
        with patch("medcat.utils.check_for_updates.DEFAULT_CACHE_PATH",
                   self.cache_path):
            check_for_updates.check_for_updates(self.pkg, self.current_version)
        mock_do_check.assert_called_once()

    # 3. doesn't run if cache still valid
    @patch("medcat.utils.check_for_updates._do_check")
    def test_does_not_run_if_interval_not_expired(self, mock_do_check):
        # recent cache
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "w") as f:
            json.dump({"last_check": time.time()}, f)
        with patch("medcat.utils.check_for_updates.DEFAULT_CACHE_PATH",
                   self.cache_path):
            check_for_updates.check_for_updates(self.pkg, self.current_version)
        mock_do_check.assert_not_called()

    # 4. info for 3+ patch versions
    @patch("medcat.utils.check_for_updates.log_info")
    def test_patch_threshold_triggered(self, mock_log):
        releases = self._make_releases(["1.3.1", "1.3.2", "1.3.3", "1.3.4"])
        cnf = {
            "pkg_name": self.pkg,
            "minor_threshold": 99,
            "patch_threshold": 3,
        }
        cnf.update(enabled=True, cache_path=self.cache_path, url="",
                   timeout=0, check_interval=0)
        check_for_updates._do_check(cnf, releases, self.current_version)
        self.assertTrue(any("patch releases available" in c[0][0]
                            for c in mock_log.call_args_list))

    # 5. info for 3+ minor versions
    @patch("medcat.utils.check_for_updates.log_info")
    def test_minor_threshold_triggered(self, mock_log):
        releases = self._make_releases(["1.4.0", "1.5.0", "1.6.0", "1.7.0"])
        cnf = {
            "pkg_name": self.pkg,
            "minor_threshold": 3,
            "patch_threshold": 99,
        }
        cnf.update(enabled=True, cache_path=self.cache_path, url="",
                   timeout=0, check_interval=0)
        check_for_updates._do_check(cnf, releases, self.current_version)
        self.assertTrue(any("minor releases available" in c[0][0]
                            for c in mock_log.call_args_list))

    # 6. env variable changes log level (regular)
    @patch.dict("os.environ", {
        "MEDCAT_VERSION_UPDATE_LOG_LEVEL": "ERROR"})
    def test_env_log_level_regular(self):
        msg = "Test"
        with patch.object(check_for_updates.logger, "log") as mock_log:
            check_for_updates.log_info(msg)
        self.assertEqual(mock_log.call_args[0][0], logging.ERROR)

    # 7. env variable changes log level (yanked)
    @patch.dict("os.environ", {
        "MEDCAT_VERSION_UPDATE_YANKED_LOG_LEVEL": "CRITICAL"})
    def test_env_log_level_yanked(self):
        msg = "Yanked"
        with patch.object(check_for_updates.logger, "log") as mock_log:
            check_for_updates.log_info(msg, yanked=True)
        self.assertEqual(mock_log.call_args[0][0], logging.CRITICAL)

    # 8. yanked version triggers warning
    @patch("medcat.utils.check_for_updates.log_info")
    def test_yanked_version_logs(self, mock_log):
        releases = self._make_releases(["1.3.0"], yanked={"1.3.0": True})
        cnf = {
            "pkg_name": self.pkg,
            "minor_threshold": 99,
            "patch_threshold": 99,
        }
        cnf.update(enabled=True, cache_path=self.cache_path, url="",
                   timeout=0, check_interval=0)
        check_for_updates._do_check(cnf, releases, self.current_version)
        self.assertTrue(any("yanked version" in c[0][0]
                            for c in mock_log.call_args_list))

    # 9. invalid current version handled gracefully
    def test_invalid_current_version_does_not_raise(self):
        releases = self._make_releases(["1.2.0"])
        cnf = {
            "pkg_name": self.pkg,
            "minor_threshold": 99,
            "patch_threshold": 99,
        }
        cnf.update(enabled=True, cache_path=self.cache_path, url="",
                   timeout=0, check_interval=0)
        try:
            check_for_updates._do_check(cnf, releases, "not_a_version")
        except Exception as e:
            self.fail(f"Should not raise, but got {e!r}")
