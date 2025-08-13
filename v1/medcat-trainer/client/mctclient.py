from dataclasses import dataclass
import json
import os
from abc import ABC
from typing import List, Tuple, Union

import requests

import logging

logger = logging.getLogger(__name__)


@dataclass
class MCTObj(ABC):
    id: str=None

    def valid(self):
        return self.id is not None


@dataclass
class MCTDataset(MCTObj):
    """A dataset in the MedCATTrainer instance.

    Attributes:
        name (str): The name of the dataset.
        dataset_file (str): The path to the dataset file, can be a csv, or excel file, with at
            least 2 columns: 'name': unique identifier for each text, and 'text': the text to be annotated.
    """
    name: str=None
    dataset_file: str=None

    def __str__(self):
        return f'{self.id} : {self.name} \t {self.dataset_file}'


@dataclass
class MCTConceptDB(MCTObj):
    """A concept database in the MedCATTrainer instance.

    Attributes:
        name (str): The name of the concept database. Name must start with a lowercase letter and contain only alphanumeric characters and underscores.
        conceptdb_file (str): The path to the concept database file, should be a <conceptdb_name>.dat file.
        use_for_training (bool): Whether to use the concept database for training. Defaults to True as most uploaded CDBs will be used for training, unless they are used for the concept search lookup.
    """
    name: str=None
    conceptdb_file: str=None
    use_for_training: bool=True

    def __post_init__(self):
        if self.name is not None:
            if not self.name[0].islower():
                raise ValueError("Name must start with a lowercase letter")
            if not self.name.replace('_', '').replace('-', '').isalnum():
                raise ValueError("Name must contain only alphanumeric characters and underscores")

    def __str__(self):
        return f'{getattr(self, "id", "N/A")} : {self.name} \t {self.conceptdb_file}'


@dataclass
class MCTVocab(MCTObj):
    """A vocabulary in the MedCATTrainer instance.

    Attributes:
        name (str): The name of the vocabulary.
        vocab_file (str): The path to the vocabulary file, should be a <vocab_name>.dat file.
    """
    name: str=None
    vocab_file: str=None

    def __str__(self):
        return f'{self.id} : {self.vocab_file}'


@dataclass
class MCTModelPack(MCTObj):
    """A model pack in the MedCATTrainer instance.

    Attributes:
        name (str): The name of the model pack.
        model_pack_zip (str): The path to the model pack zip file, should be a <modelpack_name>.zip file.
    """
    name: str=None
    model_pack_zip: str=None

    def __str__(self):
        return f'{self.id} : {self.name} \t {self. model_pack_zip}'


@dataclass
class MCTMetaTask(MCTObj):
    """A meta task in the MedCATTrainer instance.

    Attributes:
        name (str): The name of the meta task.
    """
    name: str=None

    def __str__(self):
        return f'{self.id} : {self.name}'


@dataclass
class MCTRelTask(MCTObj):
    """A relation extraction task in the MedCATTrainer instance.

    Attributes:
        name (str): The name of the relation extraction task.
    """
    name: str=None

    def __str__(self):
        return f'{self.id} : {self.name}'


@dataclass
class MCTUser(MCTObj):
    """A user in the MedCATTrainer instance.

    Attributes:
        username (str): The username of the user.
    """
    username: str=None

    def __str__(self):
        return f'{self.id} : {self.username}'


@dataclass
class MCTProject(MCTObj):
    """A project in the MedCATTrainer instance.

    Attributes:
        name (str): The name of the project.
        description (str): The description of the project.
        cuis (str): The CUIs to be used in the project filter.
        dataset (MCTDataset): The dataset to be used in the project.
        concept_db (MCTConceptDB): The concept database to be used in the project.
        vocab (MCTVocab): The vocabulary to be used in the project.
        members (List[MCTUser]): The annotators for the project.
        meta_tasks (List[MCTMetaTask]): The meta tasks for the project.
        rel_tasks (List[MCTRelTask]): The relation extraction tasks for the project.
    """
    name: str=None
    description: str=None
    cuis: str=None
    dataset: MCTDataset=None
    concept_db: MCTConceptDB=None
    vocab: MCTVocab=None
    members: List[MCTUser]=None
    meta_tasks: List[MCTMetaTask]=None
    rel_tasks: List[MCTRelTask]=None

    def __str__(self):
        return f'{self.id} : {self.name} \t {self.description} \t {self.dataset}'



class MedCATTrainerSession:
    """Wrapper for the MedCATTrainer API.
    This class provides a wrapper around the MedCATTrainer API, allowing for easy creation of projects, datasets, users, and models.

    Attributes:
        server (str): The server to connect to can also be set by an ENVVAR MCTRAINER_SERVER. Defaults to http://localhost:8001.
        username (str): The username to connect to can also be set by an ENVVAR MCTRAINER_USERNAME.
        password (str): The password to connect to can also be set by an ENVVAR MCTRAINER_PASSWORD.

    Example:
        Create a project with a concept database, vocabulary, dataset, and user.

    >>> session = MedCATTrainerSession()
    >>> ds = session.create_dataset(name='Test DS', dataset_file='<path_to_dataset>.csv')
    >>> cdb_file = '<model_pack_path>/cdb.dat'
    >>> vocab_file = '<model_pack_path>/vocab.dat'
    >>> model_pack_zip = '<model_pack_path>.zip'
    >>> # Create a concept database and vocabulary in the MCTrainer instance. This is the NER+L model only.
    >>> cdb, vocab = session.create_medcat_model(MCTConceptDB(name='test_cdb', conceptdb_file=cdb_file),
                                             MCTVocab(name='test_vocab', vocab_file=vocab_file))
    >>> # OR Create a model pack in the MCTrainer instance, NER+L, plus any MetaCAT or RelCAT models packaged together.
    >>> session.create_medcat_model_pack(MCTModelPack(name='test_model_pack', model_pack_zip=model_pack_zip))
    >>> session.create_project(name='test-project', description='test-description', members=[MCTUser(username='test-user')], dataset=ds, concept_db=cdb, vocab=vocab)

        A common interaction would be to create a project with a new dataset but existing concept database and vocabulary or Modelpack.
    >>> projects = session.get_projects()
    >>> ds = session.create_dataset(name='New Test DS', dataset_file='/Users/tom/phd/MedCATtrainer/notebook_docs/example_data/cardio.csv')
    >>> # MCTObjects can be referenced by name or by the wrapper object.
    >>> session.create_project(name='test-project', description='test-description', members=[MCTUser(username='test-user')], dataset=ds,
    concept_db=MCTConceptDB(name='test_cdb'), vocab=MCTVocab(name='test_vocab'))

        To download annotations for a project:
    >>> projects = session.get_projects()
    >>> annotations = session.get_project_annos(projects[0])
    """

    def __init__(self, server=None, username=None, password=None):
        """Initialize the MedCATTrainerSession.

        Args:
            server (_type_, optional): _description_. Defaults to None.

        Raises:
            MCTUtilsException: _description_
        """
        self.username = username or os.getenv("MCTRAINER_USERNAME")
        self.password = password or os.getenv("MCTRAINER_PASSWORD")
        self.server = server or 'http://localhost:8001'

        payload = {"username": self.username, "password": self.password}
        resp = requests.post(f"{self.server}/api/api-token-auth/", json=payload)
        if 200 <= resp.status_code < 300:
            token = json.loads(resp.text)["token"]
            self.headers = {
                'Authorization': f'Token {token}',
            }
        else:
            raise MCTUtilsException(f'Failed to login to MedCATtrainer instance running at: {self.server}')

    def create_project(self, name: str,
                       description: str,
                       members: Union[List[MCTUser], List[str]],
                       dataset: Union[MCTDataset, str],
                       cuis: List[str]=[],
                       cuis_file: str=None,
                       concept_db: Union[MCTConceptDB, str]=None,
                       vocab: Union[MCTVocab, str]=None,
                       cdb_search_filter: Union[MCTConceptDB, str]=None,
                       modelpack: Union[MCTModelPack, str]=None,
                       meta_tasks: Union[List[MCTMetaTask], List[str]]=[],
                       rel_tasks: Union[List[MCTRelTask], List[str]]=[]):
        """Create a new project in the MedCATTrainer session.
        Users, models, datasets etc. can be referred to by either their client wrapper object or their name, and the ID will be retrieved
        then used to create the project. Most names have a unique constraint on them so for the majority of cases will not results in an error.

        Only a concept_db and vocab pair, or a modelpack needs to be specified.

        Setting a modelpack will also eventually automatically select meta tasks and rel tasks.

        Args:
            name (str): The name of the project.
            description (str): The description of the project.
            members (Union[List[MCTUser], List[str]]): The annotators for the project.
            dataset (Union[MCTDataset, str]): The dataset to be used in the project.
            cuis (List[str]): The CUIs to be used in the project filter.
            cuis_file (str): The file containing the CUIs to be used in the project filter, will be appended to the cuis list.
            concept_db (Union[MCTConceptDB, str], optional): The concept database to be used in the project. Defaults to None.
            vocab (Union[MCTVocab, str], optional): The vocabulary to be used in the project. Defaults to None.
            cdb_search_filter (Union[MCTConceptDB, str], optional): _description_. Defaults to None.
            modelpack (Union[MCTModelPack, str], optional): _description_. Defaults to None.
            meta_tasks (Union[List[MCTMetaTask], List[str]], optional): _description_. Defaults to None.
            rel_tasks (Union[List[MCTRelTask], List[str]], optional): _description_. Defaults to None.

        Raises:
            MCTUtilsException: If the project creation fails

        Returns:
            MCTProject: The created project
        """

        if all(isinstance(m, str) for m in members):
            mct_members = [u for u in self.get_users() if u.username in members]
            if len(mct_members) != len(members):
                raise MCTUtilsException(f'Not all users found in MedCATTrainer instance: {members} requested, trainer members found: {mct_members}')
            else:
                members = mct_members

        if isinstance(dataset, str):
            try:
                dataset = [d for d in self.get_datasets() if d.name == dataset].pop()
            except IndexError:
                raise MCTUtilsException(f'Dataset not found in MedCATTrainer instance: {dataset}')

        if isinstance(concept_db, str):
            try:
                concept_db = [c for c in self.get_models()[0] if c.name == concept_db].pop()
            except IndexError:
                raise MCTUtilsException(f'Concept DB not found in MedCATTrainer instance: {concept_db}')

        if isinstance(vocab, str):
            try:
                vocab = [v for v in self.get_models()[1] if v.name == vocab].pop()
            except IndexError:
                raise MCTUtilsException(f'Vocab not found in MedCATTrainer instance: {vocab}')

        if isinstance(cdb_search_filter, str):
            try:
                cdb_search_filter = [c for c in self.get_concept_dbs() if c.name == cdb_search_filter].pop()
            except IndexError:
                raise MCTUtilsException(f'Concept DB not found in MedCATTrainer instance: {cdb_search_filter}')

        if isinstance(modelpack, str):
            try:
                modelpack = [m for m in self.get_model_packs() if m.name == modelpack].pop()
            except IndexError:
                raise MCTUtilsException(f'Model pack not found in MedCATTrainer instance: {modelpack}')

        if all(isinstance(m, str) for m in meta_tasks):
            mct_meta_tasks = [m for m in self.get_meta_tasks() if m.name in meta_tasks]
            if len(mct_meta_tasks) != len(meta_tasks):
                raise MCTUtilsException(f'Not all meta tasks found in MedCATTrainer instance: {meta_tasks} requested, trainer meta tasks found: {mct_meta_tasks}')
            else:
                meta_tasks = mct_meta_tasks

        if all(isinstance(r, str) for r in rel_tasks):
            mct_rel_tasks = [r for r in self.get_rel_tasks() if r.name in rel_tasks]
            if len(mct_rel_tasks) != len(rel_tasks):
                raise MCTUtilsException(f'Not all rel tasks found in MedCATTrainer instance: {rel_tasks} requested, trainer rel tasks found: {mct_rel_tasks}')
            else:
                rel_tasks = mct_rel_tasks

        if (concept_db or vocab) and modelpack:
            raise MCTUtilsException('Cannot specify both concept_db/vocab and modelpack')

        payload = {
            'name': name,
            'description': description,
            'cuis': ','.join(cuis),
            'dataset': dataset.id,
            'members': [m.id for m in members],
            'tasks': [mt.id for mt in meta_tasks],
            'relations': [rt.id for rt in rel_tasks]
        }

        if concept_db and vocab:
            payload['concept_db'] = concept_db.id
            payload['vocab'] = vocab.id
        elif modelpack:
            payload['model_pack'] = modelpack.id

        if cdb_search_filter:
            payload['cdb_search_filter'] = [cdb_search_filter.id]

        if cuis_file:
            with open(cuis_file, 'rb') as f:
                resp = requests.post(f'{self.server}/api/project-annotate-entities/', data=payload, files={'cuis_file': f}, headers=self.headers)
        else:
            resp = requests.post(f'{self.server}/api/project-annotate-entities/', data=payload, headers=self.headers)
        if 200 <= resp.status_code < 300:
            resp_json = json.loads(resp.text)
            return MCTProject(id=resp_json['id'], name=name, description=description, cuis=cuis,
                              dataset=dataset, concept_db=concept_db, vocab=vocab, members=members,
                              meta_tasks=meta_tasks, rel_tasks=rel_tasks)
        else:
            raise MCTUtilsException(f'Failed to create project with name: {name}', resp.text)

    def create_dataset(self, name: str, dataset_file: str):
        """Create a new dataset in the MedCATTrainer session.

        Args:
            name (str): The name of the dataset.
            dataset_file (str): The path to the dataset file.

        Raises:
            MCTUtilsException: If the dataset creation fails

        Returns:
            MCTDataset: The created dataset
        """
        resp = requests.post(f'{self.server}/api/datasets/', headers=self.headers,
                             data={'name': name},
                             files={'original_file': open(dataset_file, 'rb')})
        if 200 <= resp.status_code < 300:
            resp_json = json.loads(resp.text)
            return MCTDataset(name=name, id=resp_json['id'])
        else:
            raise MCTUtilsException(f'Failed to create dataset with name: {name}', resp.text)

    def create_user(self, username: str, password):
        """Create a new user in the MedCATTrainer session.

        Args:
            username (str): The username of the new user.
            password (str): The password of the new user.

        Raises:
            MCTUtilsException: If the user creation fails

        Returns:
            MCTUser: The created user
        """
        payload = {
            'username': username,
            'password': password
        }
        resp = requests.post(f'{self.server}/api/users/', json=payload, headers=self.headers)
        if 200 <= resp.status_code < 300:
            resp_json = json.loads(resp.text)
            return MCTUser(username=username, id=resp_json['id'])
        else:
            raise MCTUtilsException(f'Failed to create new user with username: {username}', resp.text)

    def create_medcat_model(self, cdb:MCTConceptDB, vocab: MCTVocab):
        """Create a new MedCAT cdb and vocab model in the MedCATTrainer session.

        Args:
            cdb (MCTConceptDB): The concept database to be created.
            vocab (MCTVocab): The vocabulary to be created.

        Raises:
            MCTUtilsException: If the model creation fails
        """
        resp = requests.post(f'{self.server}/api/concept-dbs/', headers=self.headers,
                             data={'name': cdb.name, 'use_for_training': cdb.use_for_training},
                             files={'cdb_file': open(cdb.conceptdb_file, 'rb')})
        if 200 <= resp.status_code < 300:
            resp_json = json.loads(resp.text)
            cdb.id = resp_json['id']
        else:
            raise MCTUtilsException(f'Failed uploading MedCAT cdb model: {cdb}', resp.text)

        resp = requests.post(f'{self.server}/api/vocabs/', headers=self.headers,
                             data={'name': vocab.name},
                             files={'vocab_file': open(vocab.vocab_file, 'rb')})
        if 200 <= resp.status_code < 300:
            resp_json = json.loads(resp.text)
            vocab.id = resp_json['id']
        else:
            raise MCTUtilsException(f'Failed uploading MedCAT vocab model: {vocab}', resp.text)

        return cdb, vocab

    def create_medcat_model_pack(self, model_pack: MCTModelPack):
        """Create a new MedCAT model pack in the MedCATTrainer session.

        Args:
            model_pack (MCTModelPack): The model pack to be created.

        Raises:
            MCTUtilsException: If the model pack creation fails
        """
        resp = requests.post(f'{self.server}/api/modelpacks/', headers=self.headers,
                             data={'name': model_pack.name},
                             files={'model_pack': open(model_pack.model_pack_zip, 'rb')})
        if 200 <= resp.status_code < 300:
            resp_json = json.loads(resp.text)
            model_pack.id = resp_json['id']
        else:
            raise MCTUtilsException(f'Failed uploading model pack: {model_pack.model_pack_zip}', resp.text)

    def get_users(self) -> List[MCTUser]:
        """Get all users in the MedCATTrainer instance.

        Returns:
            List[MCTUser]: A list of all users in the MedCATTrainer instance
        """
        users = json.loads(requests.get(f'{self.server}/api/users/', headers=self.headers).text)['results']
        return [MCTUser(id=u['id'], username=u['username']) for u in users]

    def get_models(self) -> Tuple[List[str], List[str]]:
        """Get all MedCAT cdb and vocab models in the MedCATTrainer instance.

        Returns:
            Tuple[List[MCTConceptDB], List[MCTVocab]]: A tuple of lists of all MedCAT cdb and vocab models in the MedCATTrainer instance
        """
        cdbs = json.loads(requests.get(f'{self.server}/api/concept-dbs/', headers=self.headers).text)['results']
        vocabs = json.loads(requests.get(f'{self.server}/api/vocabs/', headers=self.headers).text)['results']
        mct_cdbs = [MCTConceptDB(id=cdb['id'], name=cdb['name'], conceptdb_file=cdb['cdb_file']) for cdb in cdbs]
        mct_vocabs = [MCTVocab(id=v['id'], name=v['name'], vocab_file=v['vocab_file']) for v in vocabs]
        return mct_cdbs, mct_vocabs

    def get_model_packs(self) -> List[MCTModelPack]:
        """Get all MedCAT model packs in the MedCATTrainer instance.

        Returns:
            List[MCTModelPack]: A list of all MedCAT model packs in the MedCATTrainer instance
        """
        resp = json.loads(requests.get(f'{self.server}/api/modelpacks/', headers=self.headers).text)['results']
        mct_model_packs = [MCTModelPack(id=mp['id'], name=mp['name'], model_pack_zip=mp['model_pack']) for mp in resp]
        return mct_model_packs

    def get_meta_tasks(self) -> List[MCTMetaTask]:
        """Get all MedCAT meta tasks that have been created in the MedCATTrainer instance.

        Returns:
            List[MCTMetaTask]: A list of all MedCAT meta tasks in the MedCATTrainer instance
        """
        resp = json.loads(requests.get(f'{self.server}/api/meta-tasks/', headers=self.headers).text)['results']
        mct_meta_tasks = [MCTMetaTask(name=mt['name'], id=mt['id']) for mt in resp]
        return mct_meta_tasks

    def get_rel_tasks(self) -> List[MCTRelTask]:
        """Get all MedCAT relation tasks that have been created in the MedCATTrainer instance.

        Returns:
            List[MCTRelTask]: A list of all MedCAT relation tasks in the MedCATTrainer instance
        """
        resp = json.loads(requests.get(f'{self.server}/api/relations/', headers=self.headers).text)['results']
        mct_rel_tasks = [MCTRelTask(name=rt['label'], id=rt['id']) for rt in resp]
        return mct_rel_tasks

    def get_projects(self) -> List[MCTProject]:
        """Get all MedCAT annotation projects that have been created in the MedCATTrainer instance.

        Returns:
            List[MCTProject]: A list of all MedCAT annotation projects in the MedCATTrainer instance
        """
        resp = json.loads(requests.get(f'{self.server}/api/project-annotate-entities/', headers=self.headers).text)['results']
        mct_projects = [MCTProject(id=p['id'], name=p['name'], description=p['description'], cuis=p['cuis'],
                                    dataset=MCTDataset(id=p['id']),
                                    concept_db=MCTConceptDB(id=p['concept_db']),
                                    vocab=MCTVocab(id=p['vocab']),
                                    members=[MCTUser(id=u) for u in p['members']],
                                    meta_tasks=[MCTMetaTask(id=mt) for mt in p['tasks']],
                                    rel_tasks=[MCTRelTask(id=rt) for rt in p['relations']]) for p in resp]
        return mct_projects

    def get_datasets(self) -> List[MCTDataset]:
        """Get all datasets that have been created in the MedCATTrainer instance.

        Returns:
            List[MCTDataset]: A list of all datasets in the MedCATTrainer instance
        """
        resp = json.loads(requests.get(f'{self.server}/api/datasets/', headers=self.headers).text)['results']
        mct_datasets = [MCTDataset(name=d['name'], dataset_file=d['original_file'], id=d['id']) for d in resp]
        return mct_datasets

    def get_project_annos(self, projects: List[MCTProject]):
        """Get the annotations for a list of projects. Schema is documented here: https://github.com/medcat/MedCATtrainer/blob/main/docs/api.md#download-annotations

        Args:
            projects (List[MCTProject]): A list of projects to get annotations for

        Returns:
            List[MCTProject]: A list of all projects with annotations
        """
        if any(p.id is None for p in projects):
            raise MCTUtilsException('One or more project.id are None and all are required to download annotations')

        resp = json.loads(requests.get(f'{self.server}/api/download-annos/?project_ids={",".join([str(p.id) for p in projects])}&with_text=1',
                                       headers=self.headers).text)
        return resp

    def __str__(self) -> str:
        return f'{self.server} \t {self.username} \t {self.password}'


class MCTUtilsException(Exception):
    """Base exception for MedCAT Trainer API errors"""
    def __init__(self, message, original_exception=None):
        self.message = message
        self.original_exception = original_exception
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message} \n {self.original_exception}'

