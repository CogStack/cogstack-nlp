"""Unit tests for api.oidc_utils."""

from django.contrib.auth import get_user_model
from django.test import TestCase

from ..oidc_utils import get_user_by_email


class GetUserByEmailTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def test_creates_new_user_from_full_claims(self):
        claims = {
            'preferred_username': 'jdoe',
            'email': 'jdoe@example.com',
            'given_name': 'John',
            'family_name': 'Doe',
        }
        user = get_user_by_email(request=None, id_token=claims)
        self.assertEqual(user.username, 'jdoe')
        self.assertEqual(user.email, 'jdoe@example.com')
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_assigns_superuser_when_role_present(self):
        claims = {
            'preferred_username': 'admin',
            'email': 'admin@example.com',
            'roles': ['medcattrainer_superuser'],
        }
        user = get_user_by_email(request=None, id_token=claims)
        self.assertTrue(user.is_superuser)
        self.assertFalse(user.is_staff)

    def test_assigns_staff_when_role_present(self):
        claims = {
            'preferred_username': 'staffuser',
            'email': 'staff@example.com',
            'roles': ['medcattrainer_staff'],
        }
        user = get_user_by_email(request=None, id_token=claims)
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_falls_back_to_sub_when_username_missing(self):
        claims = {'sub': 'unique-sub-id', 'email': 'a@b.com'}
        user = get_user_by_email(request=None, id_token=claims)
        self.assertEqual(user.username, 'unique-sub-id')

    def test_falls_back_to_client_id_when_no_username_or_sub(self):
        claims = {'client_id': 'svc-client', 'email': 'svc@example.com'}
        user = get_user_by_email(request=None, id_token=claims)
        self.assertEqual(user.username, 'svc-client')

    def test_falls_back_to_random_username_when_nothing_provided(self):
        # No username, no sub, no client_id - should still create a user with a random username
        user = get_user_by_email(request=None, id_token={'email': 'nouser@example.com'})
        self.assertTrue(user.username.startswith('oidc-'))
        self.assertEqual(user.email, 'nouser@example.com')

    def test_email_falls_back_to_username_when_missing(self):
        claims = {'preferred_username': 'just-username'}
        user = get_user_by_email(request=None, id_token=claims)
        self.assertEqual(user.email, 'just-username')

    def test_returns_existing_user_when_email_matches(self):
        existing = self.User.objects.create_user(
            username='oldname', email='dup@example.com', password='x')

        claims = {'preferred_username': 'newname', 'email': 'dup@example.com'}
        returned = get_user_by_email(request=None, id_token=claims)

        self.assertEqual(returned.id, existing.id)
        # Existing user should have updated profile fields
        returned.refresh_from_db()
        self.assertEqual(returned.username, 'newname')

    def test_role_updates_existing_user(self):
        existing = self.User.objects.create_user(
            username='roleuser', email='role@example.com', password='x')
        self.assertFalse(existing.is_superuser)

        get_user_by_email(request=None, id_token={
            'preferred_username': 'roleuser',
            'email': 'role@example.com',
            'roles': ['medcattrainer_superuser', 'medcattrainer_staff'],
        })
        existing.refresh_from_db()
        self.assertTrue(existing.is_superuser)
        self.assertTrue(existing.is_staff)
