"""Shared helpers for backend tests.

These utilities make it easier to construct lightweight model fixtures
without triggering MedCAT model loading or expensive dataset parsing.
"""

import os
import tempfile
from contextlib import contextmanager

import pandas as pd

from django.contrib.auth.models import User

from .. import signals as api_signals
from ..models import (
    ConceptDB,
    Dataset,
    Document,
    Entity,
    ProjectAnnotateEntities,
    Vocabulary,
)


@contextmanager
def dataset_signals_disconnected():
    """Temporarily disconnect Dataset post_save / pre_save signals.

    Useful in unit tests that want to insert a Dataset row without triggering
    `dataset_from_file` which expects a CSV/XLSX on disk with the right schema.
    """
    from django.db.models.signals import post_save, pre_save

    post_save.disconnect(api_signals.save_dataset, sender=Dataset)
    pre_save.disconnect(api_signals.pre_save_dataset, sender=Dataset)
    try:
        yield
    finally:
        post_save.connect(api_signals.save_dataset, sender=Dataset)
        pre_save.connect(api_signals.pre_save_dataset, sender=Dataset)


def create_dataset(name='test-dataset', file_name='test-dataset.csv'):
    """Create a Dataset row without firing the file-parsing signals."""
    with dataset_signals_disconnected():
        ds = Dataset.objects.create(name=name, original_file=file_name)
    return ds


def make_csv_file(tmp_dir, rows=None, file_name='dataset.csv'):
    """Write a small CSV with 'name' and 'text' columns and return its path."""
    if rows is None:
        rows = [
            {'name': 'doc-a', 'text': 'Patient reports chest pain.'},
            {'name': 'doc-b', 'text': 'No fever or cough.'},
        ]
    path = os.path.join(tmp_dir, file_name)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def create_basic_project(name='test-project'):
    """Create a ProjectAnnotateEntities along with a CDB / Vocab / Dataset."""
    cdb = ConceptDB(name=f'{name}-cdb', cdb_file=f'{name}-cdb.dat')
    cdb.save(skip_load=True)
    vocab = Vocabulary(name=f'{name}-vocab', vocab_file=f'{name}-vocab.dat')
    vocab.save(skip_load=True)

    ds = create_dataset(name=f'{name}-ds', file_name=f'{name}-ds.csv')

    project = ProjectAnnotateEntities()
    project.name = name
    project.dataset = ds
    project.concept_db = cdb
    project.vocab = vocab
    project.cuis = ''
    project.save()
    return project


def create_document(project, name='doc1', text='hello world'):
    return Document.objects.create(name=name, text=text, dataset=project.dataset)


def create_user(username='testuser', password='pw', **extra):
    return User.objects.create_user(username=username, password=password, **extra)


def create_entity(label='C001'):
    return Entity.objects.create(label=label)
