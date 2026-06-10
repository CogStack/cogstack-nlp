import json
from pathlib import Path
from unittest.mock import MagicMock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from api.extensions import (
    annotation_created,
    clear_permission_hooks,
    clear_registries,
    dispatch,
    get_features,
    get_menu_extensions,
    get_permission_hooks,
    get_routes,
    register_feature,
    register_menu_extension,
    register_permission_hook,
    register_route,
)
from api.permissions import is_project_admin


SCHEMA_PATH = Path(__file__).resolve().parent / 'fixtures' / 'bootstrap_schema.json'


class ExtensionsRegistryTests(TestCase):
    def tearDown(self):
        clear_registries()
        clear_permission_hooks()

    def test_menu_extension_requires_id_and_label(self):
        with self.assertRaises(ValueError):
            register_menu_extension({'id': 'x'})
        register_menu_extension({'id': 'nav', 'label': 'Enterprise'})
        items = get_menu_extensions()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['id'], 'nav')

    def test_route_requires_path_and_component(self):
        with self.assertRaises(ValueError):
            register_route({'path': '/ee'})
        register_route({'path': '/ee/adj', 'component': 'Adjudication'})
        routes = get_routes()
        self.assertEqual(routes[0]['path'], '/ee/adj')

    def test_features_are_sorted(self):
        register_feature('workflow')
        register_feature('adjudication')
        self.assertEqual(get_features(), ['adjudication', 'workflow'])


class UrlValidationTests(TestCase):
    def tearDown(self):
        clear_registries()

    def test_menu_extension_allows_relative_and_http_urls(self):
        register_menu_extension({'id': 'a', 'label': 'A', 'route': '/ee/adj'})
        register_menu_extension({'id': 'b', 'label': 'B', 'href': 'https://example.org'})
        register_menu_extension({'id': 'c', 'label': 'C', 'href': '#frag'})
        self.assertEqual(len(get_menu_extensions()), 3)

    def test_menu_extension_rejects_javascript_href(self):
        with self.assertRaises(ValueError):
            register_menu_extension({'id': 'x', 'label': 'X', 'href': 'javascript:alert(1)'})

    def test_menu_extension_rejects_obfuscated_scheme(self):
        # Browsers ignore embedded control chars/whitespace inside a scheme.
        with self.assertRaises(ValueError):
            register_menu_extension({'id': 'x', 'label': 'X', 'href': 'java\tscript:alert(1)'})

    def test_menu_extension_rejects_data_and_protocol_relative(self):
        with self.assertRaises(ValueError):
            register_menu_extension({'id': 'd', 'label': 'D', 'href': 'data:text/html,<script>1</script>'})
        with self.assertRaises(ValueError):
            register_menu_extension({'id': 'p', 'label': 'P', 'href': '//evil.example'})

    def test_route_rejects_disallowed_scheme(self):
        with self.assertRaises(ValueError):
            register_route({'path': 'javascript:alert(1)', 'component': 'X'})

    def test_no_invalid_entry_is_stored(self):
        try:
            register_menu_extension({'id': 'x', 'label': 'X', 'href': 'javascript:alert(1)'})
        except ValueError:
            pass
        self.assertEqual(get_menu_extensions(), [])


class DispatchIsolationTests(TestCase):
    def test_dispatch_isolates_receiver_exceptions(self):
        calls = []

        def bad_receiver(sender, **kwargs):
            raise RuntimeError('boom')

        def good_receiver(sender, **kwargs):
            calls.append(kwargs.get('annotation'))

        annotation_created.connect(bad_receiver, weak=False)
        annotation_created.connect(good_receiver, weak=False)
        try:
            # Must not raise even though one receiver blows up.
            dispatch(annotation_created, sender=object, annotation='ann')
        finally:
            annotation_created.disconnect(bad_receiver)
            annotation_created.disconnect(good_receiver)

        # The healthy receiver still ran.
        self.assertEqual(calls, ['ann'])


class PermissionHookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='annotator', password='pass')
        self.other = User.objects.create_user(username='other', password='pass')
        self.project = MagicMock()
        self.project.members.filter.return_value.exists.return_value = False
        self.project.group = None

    def tearDown(self):
        clear_permission_hooks()

    def test_hook_can_grant_project_admin(self):
        def grant_other(user, project):
            if user.id == self.other.id:
                return True
            return None

        self.assertFalse(is_project_admin(self.other, self.project))
        register_permission_hook('is_project_admin', grant_other)
        self.assertTrue(is_project_admin(self.other, self.project))

    def test_hook_cannot_deny_member(self):
        self.project.members.filter.return_value.exists.return_value = True

        def deny_all(user, project):
            return False

        register_permission_hook('is_project_admin', deny_all)
        self.assertTrue(is_project_admin(self.user, self.project))

    def test_abstaining_hook(self):
        register_permission_hook('is_project_admin', lambda u, p: None)
        self.assertEqual(len(list(get_permission_hooks('is_project_admin'))), 1)
        self.assertFalse(is_project_admin(self.user, self.project))


class BootstrapEndpointTests(TestCase):
    def setUp(self):
        clear_registries()
        self.user = User.objects.create_user(username='bootstrap', password='pass')
        self.token = Token.objects.create(user=self.user)
        self.client = APIClient()

    def tearDown(self):
        clear_registries()

    def test_bootstrap_requires_auth(self):
        response = self.client.get('/api/bootstrap/')
        self.assertEqual(response.status_code, 401)

    def test_bootstrap_payload_shape(self):
        register_feature('adjudication')
        register_menu_extension({'id': 'adj', 'label': 'Adjudication', 'route': '/ee/adj'})
        register_route({'path': '/ee/adj', 'component': 'Adjudication'})

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get('/api/bootstrap/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(set(data.keys()), {'features', 'menu_extensions', 'routes'})
        self.assertIsInstance(data['features'], list)
        self.assertIsInstance(data['menu_extensions'], list)
        self.assertIsInstance(data['routes'], list)
        self.assertIn('adjudication', data['features'])
        self.assertEqual(data['menu_extensions'][0]['id'], 'adj')
        self.assertEqual(data['routes'][0]['path'], '/ee/adj')

    def test_bootstrap_matches_json_schema(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest('jsonschema not installed')

        schema = json.loads(SCHEMA_PATH.read_text())
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get('/api/bootstrap/')
        jsonschema.validate(instance=response.json(), schema=schema)
