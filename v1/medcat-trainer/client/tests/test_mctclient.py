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

if __name__ == '__main__':
    unittest.main()