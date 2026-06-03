"""Integration tests for api.views using DRF's APIClient.

These tests focus on endpoints that don't require MedCAT to be loaded.
"""

import json
import os
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ..models import (
    AnnotatedEntity,
    ConceptDB,
    Document,
    Entity,
    ProjectAnnotateEntities,
    Vocabulary,
)
from ._helpers import (
    create_basic_project,
    create_dataset,
    create_document,
    create_entity,
    create_user,
)


def _auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class AuthenticationRequiredTests(TestCase):
    def test_anonymous_users_cannot_list_projects(self):
        client = APIClient()
        resp = client.get('/api/project-annotate-entities/')
        # 401 (Unauthorized) or 403 (Forbidden) acceptable
        self.assertIn(resp.status_code, (401, 403))

    def test_anonymous_users_cannot_list_users(self):
        client = APIClient()
        resp = client.get('/api/users/')
        self.assertIn(resp.status_code, (401, 403))


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class SimpleInfoEndpointsTests(TestCase):
    def setUp(self):
        self.user = create_user(username='infouser')
        self.client = _auth_client(self.user)

    def test_version_returns_env_value(self):
        old = os.environ.get('MCT_VERSION')
        os.environ['MCT_VERSION'] = 'v9.9.9-test'
        try:
            resp = self.client.get('/api/version/')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.data, 'v9.9.9-test')
        finally:
            if old is None:
                os.environ.pop('MCT_VERSION', None)
            else:
                os.environ['MCT_VERSION'] = old

    def test_behind_reverse_proxy_returns_value(self):
        old = os.environ.get('BEHIND_RP')
        os.environ['BEHIND_RP'] = '1'
        try:
            resp = self.client.get('/api/behind-rp/')
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.data)
        finally:
            if old is None:
                os.environ.pop('BEHIND_RP', None)
            else:
                os.environ['BEHIND_RP'] = old

    def test_anno_tool_conf_returns_environment_dict(self):
        resp = self.client.get('/api/anno-conf/')
        self.assertEqual(resp.status_code, 200)
        # Just make sure it returns a dict-like JSON object
        self.assertIsInstance(resp.json(), dict)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class UserViewSetTests(TestCase):
    def setUp(self):
        self.user = create_user(username='listuser', password='pw')
        self.other = create_user(username='otheruser', password='pw')

    def test_authenticated_user_can_list_users(self):
        client = _auth_client(self.user)
        resp = client.get('/api/users/')
        self.assertEqual(resp.status_code, 200)
        usernames = [u['username'] for u in resp.json()['results']]
        self.assertIn('listuser', usernames)
        self.assertIn('otheruser', usernames)

    def test_filter_by_username(self):
        client = _auth_client(self.user)
        resp = client.get('/api/users/?username=otheruser')
        self.assertEqual(resp.status_code, 200)
        results = resp.json()['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['username'], 'otheruser')


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class ProjectAnnotateEntitiesViewSetTests(TestCase):
    def setUp(self):
        self.member = create_user(username='m1', password='pw')
        self.outsider = create_user(username='o1', password='pw')
        self.superuser = User.objects.create_superuser(
            username='su1', password='pw', email='su1@x',
        )
        self.project = create_basic_project(name='pl-proj')
        self.project.members.add(self.member)

    def test_member_sees_only_their_projects(self):
        client = _auth_client(self.member)
        resp = client.get('/api/project-annotate-entities/')
        self.assertEqual(resp.status_code, 200)
        names = [p['name'] for p in resp.json()['results']]
        self.assertIn('pl-proj', names)

    def test_outsider_sees_no_projects(self):
        client = _auth_client(self.outsider)
        resp = client.get('/api/project-annotate-entities/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['results'], [])

    def test_superuser_sees_all_projects(self):
        client = _auth_client(self.superuser)
        resp = client.get('/api/project-annotate-entities/')
        self.assertEqual(resp.status_code, 200)
        names = [p['name'] for p in resp.json()['results']]
        self.assertIn('pl-proj', names)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class GetCreateEntityTests(TestCase):
    def setUp(self):
        self.user = create_user(username='entuser')
        self.client = _auth_client(self.user)

    def test_creates_entity_when_label_does_not_exist(self):
        self.assertFalse(Entity.objects.filter(label='C-NEW').exists())
        resp = self.client.post('/api/get-create-entity/', {'label': 'C-NEW'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Entity.objects.filter(label='C-NEW').exists())
        self.assertIn('entity_id', resp.json())

    def test_returns_existing_entity_id_when_label_exists(self):
        ent = create_entity(label='C-EXIST')
        resp = self.client.post('/api/get-create-entity/', {'label': 'C-EXIST'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['entity_id'], ent.id)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class ProjectProgressTests(TestCase):
    def setUp(self):
        self.user = create_user(username='ppuser')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='pp-proj')

        # Create 3 documents but no annotations
        for i in range(3):
            create_document(self.project, name=f'doc-{i}', text=f'text {i}')

    def test_returns_progress_for_project(self):
        resp = self.client.get(f'/api/project-progress/?projects={self.project.id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        # JSON dict keys are strings
        key = str(self.project.id)
        self.assertIn(key, data)
        self.assertEqual(data[key]['validated_count'], 0)
        self.assertEqual(data[key]['dataset_count'], 3)

    def test_returns_400_when_no_projects_param(self):
        resp = self.client.get('/api/project-progress/')
        self.assertEqual(resp.status_code, 400)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class PrepareDocsBgTaskTests(TestCase):
    def setUp(self):
        self.user = create_user(username='bguser')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='bg-proj')
        for i in range(2):
            create_document(self.project, name=f'd-{i}', text=f't-{i}')

    def test_returns_400_for_unknown_project(self):
        resp = self.client.get('/api/prep-docs-bg-tasks/999999/')
        self.assertEqual(resp.status_code, 400)

    def test_returns_doc_counts_for_known_project(self):
        resp = self.client.get(f'/api/prep-docs-bg-tasks/{self.project.id}/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['dataset_len'], 2)
        self.assertEqual(data['prepd_docs_len'], 0)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class ProjectAdminProjectsTests(TestCase):
    def setUp(self):
        self.member = create_user(username='admin-mem')
        self.outsider = create_user(username='admin-out')
        self.project = create_basic_project(name='admin-proj')
        self.project.members.add(self.member)

    def test_member_can_list_admin_projects(self):
        client = _auth_client(self.member)
        resp = client.get('/api/project-admin/projects/')
        self.assertEqual(resp.status_code, 200)
        names = [p['name'] for p in resp.json()]
        self.assertIn('admin-proj', names)

    def test_outsider_has_no_admin_projects(self):
        client = _auth_client(self.outsider)
        resp = client.get('/api/project-admin/projects/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class ProjectAdminDetailTests(TestCase):
    def setUp(self):
        self.member = create_user(username='detail-mem')
        self.outsider = create_user(username='detail-out')
        self.project = create_basic_project(name='detail-proj')
        self.project.members.add(self.member)

    def test_member_can_access_project_detail(self):
        client = _auth_client(self.member)
        resp = client.get(f'/api/project-admin/projects/{self.project.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['name'], 'detail-proj')

    def test_outsider_gets_403(self):
        client = _auth_client(self.outsider)
        resp = client.get(f'/api/project-admin/projects/{self.project.id}/')
        self.assertEqual(resp.status_code, 403)

    def test_returns_404_for_unknown_project(self):
        client = _auth_client(self.member)
        resp = client.get('/api/project-admin/projects/9999999/')
        self.assertEqual(resp.status_code, 404)

    def test_member_can_delete_project(self):
        client = _auth_client(self.member)
        resp = client.delete(f'/api/project-admin/projects/{self.project.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            ProjectAnnotateEntities.objects.filter(id=self.project.id).exists()
        )

    def test_outsider_cannot_delete(self):
        client = _auth_client(self.outsider)
        resp = client.delete(f'/api/project-admin/projects/{self.project.id}/')
        self.assertEqual(resp.status_code, 403)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class ProjectAdminResetTests(TestCase):
    def setUp(self):
        self.member = create_user(username='reset-mem')
        self.outsider = create_user(username='reset-out')
        self.project = create_basic_project(name='reset-proj')
        self.project.members.add(self.member)

        doc = create_document(self.project, name='doc', text='hello')
        ent = create_entity(label='C-RESET')
        AnnotatedEntity.objects.create(
            user=self.member, project=self.project, document=doc, entity=ent,
            value='hello', start_ind=0, end_ind=5, acc=1.0, validated=True,
        )
        self.project.validated_documents.add(doc)

    def test_member_resets_annotations(self):
        self.assertEqual(
            AnnotatedEntity.objects.filter(project=self.project).count(), 1
        )
        client = _auth_client(self.member)
        resp = client.post(f'/api/project-admin/projects/{self.project.id}/reset/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            AnnotatedEntity.objects.filter(project=self.project).count(), 0
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.validated_documents.count(), 0)

    def test_outsider_cannot_reset(self):
        client = _auth_client(self.outsider)
        resp = client.post(f'/api/project-admin/projects/{self.project.id}/reset/')
        self.assertEqual(resp.status_code, 403)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class ProjectAdminCloneTests(TestCase):
    def setUp(self):
        self.member = create_user(username='clone-mem')
        self.outsider = create_user(username='clone-out')
        self.project = create_basic_project(name='clone-proj')
        self.project.members.add(self.member)

    def test_clone_returns_new_project(self):
        client = _auth_client(self.member)
        resp = client.post(
            f'/api/project-admin/projects/{self.project.id}/clone/',
            {'name': 'my-clone'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201, msg=resp.content)
        self.assertEqual(resp.json()['name'], 'my-clone')
        self.assertTrue(ProjectAnnotateEntities.objects.filter(name='my-clone').exists())

    def test_clone_default_name_when_unspecified(self):
        client = _auth_client(self.member)
        resp = client.post(
            f'/api/project-admin/projects/{self.project.id}/clone/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['name'], 'clone-proj (Clone)')

    def test_clone_returns_404_for_unknown_project(self):
        client = _auth_client(self.member)
        resp = client.post('/api/project-admin/projects/99999/clone/', {}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_outsider_cannot_clone(self):
        client = _auth_client(self.outsider)
        resp = client.post(
            f'/api/project-admin/projects/{self.project.id}/clone/',
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class ModelLoadedTests(TestCase):
    def setUp(self):
        self.user = create_user(username='ml-user')
        self.client = _auth_client(self.user)
        self.project = create_basic_project(name='ml-proj')

    def test_returns_model_states_for_all_projects(self):
        resp = self.client.get('/api/model-loaded/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('model_states', data)
        self.assertIn(str(self.project.id), {str(k) for k in data['model_states']})


@override_settings(MEDIA_ROOT='/tmp/mct-tests-views')
class DownloadAnnosTests(TestCase):
    def setUp(self):
        self.regular = create_user(username='reg')
        self.superuser = User.objects.create_superuser(username='dl-su', password='pw', email='dl@x')

    def test_non_superuser_cannot_download(self):
        client = _auth_client(self.regular)
        resp = client.get('/api/download-annos/?project_ids=1')
        self.assertEqual(resp.status_code, 400)

    def test_superuser_can_download_for_existing_project(self):
        project = create_basic_project(name='dl-proj')
        client = _auth_client(self.superuser)
        resp = client.get(f'/api/download-annos/?project_ids={project.id}&with_text=true')
        self.assertEqual(resp.status_code, 200)
        # Response is a streaming JSON document
        self.assertIn('Content-Disposition', resp)
