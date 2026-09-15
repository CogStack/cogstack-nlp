"""Unit tests for Django SECRET_KEY resolution."""

from unittest import TestCase

from django.conf import settings

from core.settings import NON_PROD_DEFAULT_SECRET_KEY, resolve_secret_key


class ResolveSecretKeyTests(TestCase):
    """SECRET_KEY must come from the environment when set, not the hardcoded default."""

    def test_prod_uses_provided_secret_key(self):
        self.assertEqual(
            resolve_secret_key('prod', 'env-provided-secret'),
            'env-provided-secret',
        )

    def test_prod_without_secret_key_exits(self):
        with self.assertRaises(SystemExit) as ctx:
            resolve_secret_key('prod', None)
        self.assertIn('No SECRET_KEY environment variable found', str(ctx.exception))

    def test_non_prod_defaults_when_secret_key_missing(self):
        self.assertEqual(
            resolve_secret_key('non-prod', None),
            NON_PROD_DEFAULT_SECRET_KEY,
        )

    def test_non_prod_uses_provided_secret_key(self):
        self.assertEqual(
            resolve_secret_key('non-prod', 'non-prod-env-secret'),
            'non-prod-env-secret',
        )


class CookieNameTests(TestCase):
    def test_session_and_csrf_cookies_are_namespaced(self):
        self.assertTrue(settings.SESSION_COOKIE_NAME.startswith('mct_'))
        self.assertTrue(settings.CSRF_COOKIE_NAME.startswith('mct_'))
        self.assertNotEqual(settings.SESSION_COOKIE_NAME, 'sessionid')
        self.assertNotEqual(settings.CSRF_COOKIE_NAME, 'csrftoken')
