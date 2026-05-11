import os
import unittest

from mctclient import MedCATTrainerSession


class TestMCTClientIntegration(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("MCTRAINER_SERVER") and os.getenv("MCTRAINER_USERNAME") and os.getenv("MCTRAINER_PASSWORD"),
        "Integration test requires MCTRAINER_SERVER, MCTRAINER_USERNAME, MCTRAINER_PASSWORD",
    )
    def test_get_users_contains_expected_users(self):
        server = os.getenv("MCTRAINER_SERVER").rstrip("/")
        username = os.getenv("MCTRAINER_USERNAME")
        password = os.getenv("MCTRAINER_PASSWORD")
        expected_users_env = os.getenv("MCTRAINER_EXPECTED_USERS", "")

        expected_users = {username}
        if expected_users_env:
            expected_users |= {u.strip() for u in expected_users_env.split(",") if u.strip()}

        session = MedCATTrainerSession(server=server, username=username, password=password)
        users = session.get_users()

        self.assertIsInstance(users, list)
        self.assertGreater(len(users), 0, "Expected at least one user from API")

        usernames = {u.username for u in users}
        missing = expected_users - usernames
        self.assertFalse(missing, f"Expected user(s) missing from API: {sorted(missing)}")

