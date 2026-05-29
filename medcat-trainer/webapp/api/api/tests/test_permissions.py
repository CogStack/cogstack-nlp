"""Unit tests for api.permissions."""

from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, override_settings

from ..models import (
    ConceptDB,
    ProjectAnnotateEntities,
    ProjectGroup,
    Vocabulary,
)
from ..permissions import IsReadOnly, is_project_admin
from ._helpers import create_dataset


@override_settings(MEDIA_ROOT='/tmp/mct-tests-perms')
class IsReadOnlyTests(TestCase):
    def setUp(self):
        self.permission = IsReadOnly()
        self.factory = RequestFactory()

    def test_allows_safe_methods(self):
        for method in ('GET', 'HEAD', 'OPTIONS'):
            request = self.factory.generic(method, '/api/x/')
            self.assertTrue(
                self.permission.has_permission(request, view=MagicMock()),
                f'Expected {method} to be allowed',
            )

    def test_denies_unsafe_methods(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            request = self.factory.generic(method, '/api/x/')
            self.assertFalse(
                self.permission.has_permission(request, view=MagicMock()),
                f'Expected {method} to be denied',
            )


@override_settings(MEDIA_ROOT='/tmp/mct-tests-perms')
class IsProjectAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(username='su', password='pw', email='su@x')
        cls.staff = User.objects.create_user(username='st', password='pw', is_staff=True)
        cls.member = User.objects.create_user(username='m1', password='pw')
        cls.group_admin = User.objects.create_user(username='ga', password='pw')
        cls.outsider = User.objects.create_user(username='out', password='pw')

        cdb = ConceptDB(name='perm_cdb', cdb_file='perm_cdb.dat')
        cdb.save(skip_load=True)
        vocab = Vocabulary(name='perm_vocab', vocab_file='perm_vocab.dat')
        vocab.save(skip_load=True)
        dataset = create_dataset(name='perm_ds', file_name='perm_ds.csv')

        cls.group = ProjectGroup.objects.create(
            name='grp1',
            dataset=dataset,
            concept_db=cdb,
            vocab=vocab,
            cuis='',
        )
        cls.group.administrators.add(cls.group_admin)

        cls.project_no_group = ProjectAnnotateEntities()
        cls.project_no_group.name = 'p-no-group'
        cls.project_no_group.dataset = dataset
        cls.project_no_group.concept_db = cdb
        cls.project_no_group.vocab = vocab
        cls.project_no_group.cuis = ''
        cls.project_no_group.save()
        cls.project_no_group.members.add(cls.member)

        cls.project_with_group = ProjectAnnotateEntities()
        cls.project_with_group.name = 'p-grouped'
        cls.project_with_group.dataset = dataset
        cls.project_with_group.concept_db = cdb
        cls.project_with_group.vocab = vocab
        cls.project_with_group.group = cls.group
        cls.project_with_group.cuis = ''
        cls.project_with_group.save()

    def test_superuser_is_always_admin(self):
        self.assertTrue(is_project_admin(self.superuser, self.project_no_group))

    def test_staff_user_is_always_admin(self):
        self.assertTrue(is_project_admin(self.staff, self.project_no_group))

    def test_member_user_is_admin(self):
        self.assertTrue(is_project_admin(self.member, self.project_no_group))

    def test_group_admin_is_admin_of_group_project(self):
        self.assertTrue(is_project_admin(self.group_admin, self.project_with_group))

    def test_group_admin_is_not_admin_of_unrelated_project(self):
        self.assertFalse(is_project_admin(self.group_admin, self.project_no_group))

    def test_outsider_is_not_admin(self):
        self.assertFalse(is_project_admin(self.outsider, self.project_no_group))
        self.assertFalse(is_project_admin(self.outsider, self.project_with_group))
