import json
import unittest
from unittest.mock import patch, MagicMock
from mctclient import (
    MedCATTrainerSession, MCTDataset, MCTConceptDB, MCTVocab, MCTModelPack, MCTMetaTask, MCTRelTask, MCTUser, MCTProject
)

class TestMCTClient(unittest.TestCase):

    @patch('mctclient.requests.post')
    @patch('mctclient.requests.get')
    def test_session_get_projects(self, mock_get, mock_post):
        # Mock authentication
        mock_post.return_value = MagicMock(status_code=200, text='{"token": "abc"}')
        # Mock get_projects with a real project structure
        mock_project = {
            "id": 1,
            "name": "Test Project",
            "description": "A test project",
            "cuis": "C001,C002",
            "create_time": "2021-01-01T00:00:00Z",
            "last_modified": "2021-01-01T00:00:00Z",
            "annotation_classification": False,
            "project_locked": False,
            "project_status": "Active",
            "deid_model_annotation": False,
            "validated_documents": [1000, 1010],
            "dataset": 10,
            "concept_db": 20,
            "vocab": 30,
            "members": [100, 101],
            "tasks": [200],
            "relations": [300]
        }
        mock_get.return_value = MagicMock(
            status_code=200,
            text=json.dumps({"results": [mock_project]})
        )
        session = MedCATTrainerSession(server='http://localhost', username='u', password='p')
        projects = session.get_projects()
        self.assertIsInstance(projects, list)
        self.assertEqual(len(projects), 1)
        project = projects[0]
        self.assertIsInstance(project, MCTProject)
        self.assertEqual(project.name, "Test Project")
        self.assertEqual(project.description, "A test project")
        self.assertEqual(project.cuis, "C001,C002")
        self.assertIsInstance(project.dataset, MCTDataset)
        self.assertIsInstance(project.concept_db, MCTConceptDB)
        self.assertIsInstance(project.vocab, MCTVocab)
        self.assertTrue(all(isinstance(m, MCTUser) for m in project.members))
        self.assertTrue(all(isinstance(mt, MCTMetaTask) for mt in project.meta_tasks))
        self.assertTrue(all(isinstance(rt, MCTRelTask) for rt in project.rel_tasks))

    @patch('mctclient.requests.post')
    def test_create_project(self, mock_post):
        # Mock authentication
        def post_side_effect(url, *args, **kwargs):
            if url.endswith('/api/api-token-auth/'):
                return MagicMock(status_code=200, text='{"token": "abc"}')
            elif url.endswith('/api/project-annotate-entities/'):
                # Return a response with all fields needed for MCTProject
                return MagicMock(
                    status_code=200,
                    text=json.dumps({
                        'id': '3',
                        'name': 'My Project',
                        'description': 'desc',
                        'cuis': 'C001,C002',
                        'dataset': '2',
                        'concept_db': '20',
                        'vocab': '30',
                        'members': ['1'],
                        'tasks': ['200'],
                        'relations': ['300']
                    }),
                    json=lambda: {
                        'id': '3',
                        'name': 'My Project',
                        'description': 'desc',
                        'cuis': 'C001,C002',
                        'dataset': '2',
                        'concept_db': '20',
                        'vocab': '30',
                        'members': ['1'],
                        'tasks': ['200'],
                        'relations': ['300']
                    }
                )
            else:
                return MagicMock(status_code=404, text='')

        mock_post.side_effect = post_side_effect

        session = MedCATTrainerSession(server='http://localhost', username='u', password='p')
        user = MCTUser(id='1', username='testuser')
        dataset = MCTDataset(id='2', name='TestDS', dataset_file='file.csv')
        concept_db = MCTConceptDB(id='20', name='testCDB', conceptdb_file='cdb.dat')
        vocab = MCTVocab(id='30', name='testVocab', vocab_file='vocab.dat')
        meta_task = MCTMetaTask(id='200', name='TestMetaTask')
        rel_task = MCTRelTask(id='300', name='TestRelTask')

        project = session.create_project(
            name='My Project',
            description='desc',
            cuis='C001,C002',
            members=[user],
            dataset=dataset,
            concept_db=concept_db,
            vocab=vocab,
            meta_tasks=[meta_task],
            rel_tasks=[rel_task]
        )
        self.assertIsInstance(project, MCTProject)
        self.assertEqual(project.name, 'My Project')
        self.assertEqual(project.description, 'desc')
        self.assertEqual(project.cuis, 'C001,C002')
        self.assertIsInstance(project.dataset, MCTDataset)
        self.assertIsInstance(project.concept_db, MCTConceptDB)
        self.assertIsInstance(project.vocab, MCTVocab)
        self.assertEqual(project.members, [user])
        self.assertEqual(project.meta_tasks, [meta_task])
        self.assertEqual(project.rel_tasks, [rel_task])

    @patch('mctclient.requests.post')
    @patch('mctclient.requests.get')
    def test_upload_projects_export_with_cdb_vocab_objects(self, mock_get, mock_post):
        """Test upload_projects_export with cdb and vocab objects"""
        # Mock authentication and upload responses
        mock_upload_response = {"status": "success", "uploaded_projects": 2}

        def post_side_effect(url, *args, **kwargs):
            if url.endswith('/api/api-token-auth/'):
                return MagicMock(status_code=200, text='{"token": "abc"}')
            elif url.endswith('/api/upload-deployment/'):
                return MagicMock(
                    status_code=200,
                    json=lambda: mock_upload_response
                )
            else:
                return MagicMock(status_code=404, text='')

        mock_post.side_effect = post_side_effect

        session = MedCATTrainerSession(server='http://localhost', username='u', password='p')
        cdb = MCTConceptDB(id='20', name='testCDB', conceptdb_file='cdb.dat')
        vocab = MCTVocab(id='30', name='testVocab', vocab_file='vocab.dat')

        projects = [{"id": 1, "name": "Project 1"}, {"id": 2, "name": "Project 2"}]

        result = session.upload_projects_export(projects, cdb=cdb, vocab=vocab)

        # Verify the API call was made correctly
        mock_post.assert_called_with(
            f'{session.server}/api/upload-deployment/',
            headers=session.headers,
            json={
                'exported_projects': projects,
                'cdb_id': '20',
                'vocab_id': '30'
            }
        )
        self.assertEqual(result, mock_upload_response)

    @patch('mctclient.requests.post')
    @patch('mctclient.requests.get')
    def test_upload_projects_export_with_cdb_vocab_strings(self, mock_get, mock_post):
        """Test upload_projects_export with cdb and vocab as strings"""
        # Mock get_concept_dbs and get_vocabs responses
        def get_side_effect(url, *args, **kwargs):
            if url.endswith('/api/concept-dbs/'):
                return MagicMock(
                    status_code=200,
                    text=json.dumps({"results": [{"id": "20", "name": "testCDB", "cdb_file": "cdb.dat"}]})
                )
            elif url.endswith('/api/vocabs/'):
                return MagicMock(
                    status_code=200,
                    text=json.dumps({"results": [{"id": "30", "name": "testVocab", "vocab_file": "vocab.dat"}]})
                )
            else:
                return MagicMock(status_code=404, text='')

        mock_get.side_effect = get_side_effect

        # Mock authentication and upload responses
        mock_upload_response = {"status": "success", "uploaded_projects": 1}

        def post_side_effect(url, *args, **kwargs):
            if url.endswith('/api/api-token-auth/'):
                return MagicMock(status_code=200, text='{"token": "abc"}')
            elif url.endswith('/api/upload-deployment/'):
                return MagicMock(
                    status_code=200,
                    json=lambda: mock_upload_response
                )
            else:
                return MagicMock(status_code=404, text='')

        mock_post.side_effect = post_side_effect

        session = MedCATTrainerSession(server='http://localhost', username='u', password='p')
        projects = [{"id": 1, "name": "Project 1"}]

        result = session.upload_projects_export(projects, cdb="testCDB", vocab="testVocab")

        # Verify the API call was made correctly
        mock_post.assert_called_with(
            f'{session.server}/api/upload-deployment/',
            headers=session.headers,
            json={
                'exported_projects': projects,
                'cdb_id': '20',
                'vocab_id': '30'
            }
        )
        self.assertEqual(result, mock_upload_response)

    @patch('mctclient.requests.post')
    @patch('mctclient.requests.get')
    def test_upload_projects_export_with_modelpack_object(self, mock_get, mock_post):
        """Test upload_projects_export with modelpack object"""
        # Mock authentication and upload responses
        mock_upload_response = {"status": "success", "uploaded_projects": 1}

        def post_side_effect(url, *args, **kwargs):
            if url.endswith('/api/api-token-auth/'):
                return MagicMock(status_code=200, text='{"token": "abc"}')
            elif url.endswith('/api/upload-deployment/'):
                return MagicMock(
                    status_code=200,
                    json=lambda: mock_upload_response
                )
            else:
                return MagicMock(status_code=404, text='')

        mock_post.side_effect = post_side_effect

        session = MedCATTrainerSession(server='http://localhost', username='u', password='p')
        modelpack = MCTModelPack(id='40', name='testModelPack', model_pack_zip='model.zip')

        projects = [{"id": 1, "name": "Project 1"}]

        result = session.upload_projects_export(projects, modelpack=modelpack)

        # Verify the API call was made correctly
        mock_post.assert_called_with(
            f'{session.server}/api/upload-deployment/',
            headers=session.headers,
            json={
                'exported_projects': projects,
                'modelpack_id': '40'
            }
        )
        self.assertEqual(result, mock_upload_response)

    @patch('mctclient.requests.post')
    @patch('mctclient.requests.get')
    def test_upload_projects_export_with_modelpack_string(self, mock_get, mock_post):
        """Test upload_projects_export with modelpack as string"""
        # Mock get_model_packs response
        def get_side_effect(url, *args, **kwargs):
            if url.endswith('/api/modelpacks/'):
                return MagicMock(
                    status_code=200,
                    text=json.dumps({"results": [{"id": "40", "name": "testModelPack", "model_pack": "model.zip"}]})
                )
            else:
                return MagicMock(status_code=404, text='')

        mock_get.side_effect = get_side_effect

        # Mock authentication and upload responses
        mock_upload_response = {"status": "success", "uploaded_projects": 1}

        def post_side_effect(url, *args, **kwargs):
            if url.endswith('/api/api-token-auth/'):
                return MagicMock(status_code=200, text='{"token": "abc"}')
            elif url.endswith('/api/upload-deployment/'):
                return MagicMock(
                    status_code=200,
                    json=lambda: mock_upload_response
                )
            else:
                return MagicMock(status_code=404, text='')

        mock_post.side_effect = post_side_effect

        session = MedCATTrainerSession(server='http://localhost', username='u', password='p')
        projects = [{"id": 1, "name": "Project 1"}]

        result = session.upload_projects_export(projects, modelpack="testModelPack")

        # Verify the API call was made correctly
        mock_post.assert_called_with(
            f'{session.server}/api/upload-deployment/',
            headers=session.headers,
            json={
                'exported_projects': projects,
                'modelpack_id': '40'
            }
        )
        self.assertEqual(result, mock_upload_response)

    @patch('mctclient.requests.post')
    def test_upload_projects_export_no_cdb_vocab_modelpack(self, mock_post):
        """Test upload_projects_export raises exception when no cdb/vocab/modelpack provided"""
        # Mock authentication
        def post_side_effect(url, *args, **kwargs):
            if url.endswith('/api/api-token-auth/'):
                return MagicMock(status_code=200, text='{"token": "abc"}')
            else:
                return MagicMock(status_code=404, text='')

        mock_post.side_effect = post_side_effect

        session = MedCATTrainerSession(server='http://localhost', username='u', password='p')
        projects = [{"id": 1, "name": "Project 1"}]

        with self.assertRaises(Exception) as context:
            session.upload_projects_export(projects)

        self.assertIn('No cdb, vocab, or modelpack provided', str(context.exception))

    @patch('mctclient.requests.post')
    def test_upload_projects_export_api_failure(self, mock_post):
        """Test upload_projects_export handles API failure"""
        # Mock authentication and failed upload response
        def post_side_effect(url, *args, **kwargs):
            if url.endswith('/api/api-token-auth/'):
                return MagicMock(status_code=200, text='{"token": "abc"}')
            elif url.endswith('/api/upload-deployment/'):
                return MagicMock(
                    status_code=400,
                    text='{"error": "Bad request"}'
                )
            else:
                return MagicMock(status_code=404, text='')

        mock_post.side_effect = post_side_effect

        session = MedCATTrainerSession(server='http://localhost', username='u', password='p')
        cdb = MCTConceptDB(id='20', name='testCDB', conceptdb_file='cdb.dat')
        vocab = MCTVocab(id='30', name='testVocab', vocab_file='vocab.dat')
        projects = [{"id": 1, "name": "Project 1"}]

        with self.assertRaises(Exception) as context:
            session.upload_projects_export(projects, cdb=cdb, vocab=vocab)

        self.assertIn('Failed to upload projects export', str(context.exception))

if __name__ == '__main__':
    unittest.main()