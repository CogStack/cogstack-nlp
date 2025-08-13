import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Dict

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q

from core.settings import MEDIA_ROOT
from .models import *
from .utils import env_str_to_bool

_MAX_DATASET_SIZE_DEFAULT = 10000
_dt_fmt = '%Y-%m-%d %H:%M:%S.%f'

logger = logging.getLogger(__name__)


def dataset_from_file(dataset: Dataset):
    if '.csv' in dataset.original_file.path:
        df = pd.read_csv(dataset.original_file.path, on_bad_lines='error')
    elif '.xlsx' in dataset.original_file.path:
        df = pd.read_excel(dataset.original_file.path)
    else:
        raise Exception("Please make sure the file is either a .csv or .xlsx format")

    df.columns = [c.lower() for c in df.columns]
    max_dataset_size = int(os.environ.get('MAX_DATASET_SIZE', _MAX_DATASET_SIZE_DEFAULT))

    if df['name'].nunique() != df.shape[0] and env_str_to_bool('UNIQUE_DOC_NAMES_IN_DATASETS', True):
        raise Exception('name column entries must be unique')

    if df.shape[0] > int(max_dataset_size):
        raise Exception(f'Attempting to upload a dataset with {df.shape[0]} rows. The Max dataset size is set to'
                        f' {max_dataset_size}, please reduce the number of rows or contact the MedCATTrainer'
                        f' administrator to increase the env var value:MAX_DATASET_SIZE')

    if 'text' not in df.columns or 'name' not in df.columns:
        raise Exception("Please make sure the uploaded file has a column with two columns:'name', 'text'. "
                        "The 'name' column are document IDs, and the 'text' column is the text you're "
                        "collecting annotations for")

    with transaction.atomic():
        for i, row in enumerate(df.iterrows()):
            row = row[1]
            document = Document()
            document.name = row['name']
            document.text = sanitise_input(row['text'])
            document.dataset = dataset
            document.save()


def sanitise_input(text: str):
    tags = [('<br>', '\n'), ('</?p>', '\n'), ('<span(?:.*?)?>', ''),
            ('</span>', ''), ('<div (?:.*?)?>', '\n'), ('</div>', '\n'),
            ('</?html>', ''), ('</?body>', ''), ('</?head>', '')]
    for tag, repl in tags:
        text = re.sub(tag, repl, text)
    return text


def delete_orphan_docs(dataset: Dataset):
    Document.objects.filter(dataset__id=dataset.id).delete()


def upload_projects_export(medcat_export: Dict):
    for proj in medcat_export['projects']:
        p = ProjectAnnotateEntities()
        p.name = proj['name'] + ' IMPORTED'
        if len(proj['cuis']) > 1000:
            # store large CUI lists in a json file.
            cuis_file_name = MEDIA_ROOT + '/' + re.sub('/|\.', '_', p.name + '_cuis_file') + '.json'
            json.dump(proj["cuis"].split(','), open(cuis_file_name, 'w'))
            p.cuis = ""
            p.cuis_file.name = cuis_file_name
        else:
            p.cuis = proj['cuis']

        # ensure current deployment has the neccessary - Entity, MetaTak, Relation, and warn on not present User objects.
        ent_labels, meta_tasks, rels, unavailable_users, available_users = set(), defaultdict(set), set(), set(), dict()
        for doc in proj['documents']:
            for anno in doc['annotations']:
                ent_labels.add(anno['cui'])
                for meta_anno in anno['meta_anns'].values():
                    meta_tasks[meta_anno['name']].add(meta_anno['value'])
                user_obj = User.objects.filter(username=anno['user']).first()
                if user_obj is None:
                    unavailable_users.add(anno['user'])
                elif anno['user'] not in available_users:
                    available_users[anno['user']] = user_obj
            for rel in doc.get('relations', []):
                rels.add(rel['relation'])
        # escape - filename
        ds_file_name = MEDIA_ROOT + '/' + re.sub('/|\.', '_', p.name + '_dataset') + '.csv'
        names = [doc['name'] for doc in proj['documents']]
        if len(set(names)) != len(names):  # ensure names are unique for docs
            names = [f'{i} - {names[i]}' for i in range(len(names))]
        pd.DataFrame({'name': names,
                      'text': [doc['text'] for doc in proj['documents']]}).to_csv(ds_file_name)
        ds_mod = Dataset()
        ds_mod.name = p.name + '_dataset'
        ds_mod.original_file.name = ds_file_name
        ds_mod.save()
        p.dataset = ds_mod
        p.save()

        # create django ORM model instances that are referenced in the upload if they don't exist.
        for u in unavailable_users:
            logger.warning(f'Username: {u} - not present in this trainer deployment.')
        for ent_lab in ent_labels:
            ent = Entity.objects.filter(label=ent_lab).first()
            if ent is None:
                ent = Entity()
                ent.label = ent_lab
                ent.save()
        for task in meta_tasks:
            if MetaTask.objects.filter(name=task).first() is None:
                m_task = MetaTask()
                m_task.name = task
                m_task.save()
                # create the MetaTask Values.
            for task_val in meta_tasks[task]:
                if MetaTaskValue.objects.filter(name=task_val).first() is None:
                    mt_value = MetaTaskValue()
                    mt_value.name = task_val
                    mt_value.save()
            m_task = MetaTask.objects.filter(name=task).first()
            curr_vals = m_task.values.all()
            task_vals = [MetaTaskValue.objects.filter(name=m_t).first() for m_t in meta_tasks[task]]
            m_task.values.set(set(list(curr_vals) + task_vals))

        for rel in rels:
            if Relation.objects.filter(label=rel).first() is None:
                r = Relation()
                r.label = rel
                r.save()

        p.validated_documents.set(list(Document.objects.filter(dataset=ds_mod)))

        for doc in proj['documents']:
            doc_mod = Document.objects.filter(Q(dataset=ds_mod) & Q(text=doc['text'])).first()
            annos = []
            for anno in doc['annotations']:
                a = AnnotatedEntity()
                a.user = available_users[anno['user']]
                a.project = p
                a.document = doc_mod
                e = Entity.objects.get(label=anno['cui'])
                a.entity = e
                a.value = anno['value']
                a.start_ind = anno['start']
                a.end_ind = anno['end']
                a.validated = anno['validated']
                a.correct = anno['correct']
                a.deleted = anno['deleted']
                a.alternative = anno['alternative']
                a.killed = anno['killed']
                a.irrelevant = anno.get('irrelevant', False)  # Added later - so False by default for compatibility
                if anno.get('last_modified') is not None:
                    try:
                        a.last_modified = datetime.strptime(anno['last_modified'], _dt_fmt)
                    except ValueError:
                        a.last_modified = datetime.now()
                if anno.get('create_time') is not None:
                    try:
                        a.create_time = datetime.strptime(anno['create_time'], _dt_fmt)
                    except ValueError:
                        a.create_time = datetime.now()
                a.comment = anno.get('comment')
                a.manually_created = anno['manually_created']

                a.acc = anno['acc']
                a.save()
                annos.append(a)
                for task_name, meta_anno in anno['meta_anns'].items():
                    m_a = MetaAnnotation()
                    m_a.annotated_entity = a
                    # there will be at least one or more of these available.
                    m_a = MetaTask.objects.filter(name=task_name).first()
                    m_a.validated = meta_anno['validated']
                    m_a.save()
                    # missing acc on the model
            anno_to_doc_ind = {a.start_ind: a for a in annos}

            for relation in doc.get('relations', []):
                er = EntityRelation()
                er.user = available_users[relation['user']]
                er.project = p
                er.document = doc_mod
                # there will be at least one or more of these available.
                er.relation = Relation.objects.filter(label=relation['relation']).first()
                er.validated = er.validated
                # link relations with start and end anno ents
                er.start_entity = anno_to_doc_ind[relation['start_entity_start_idx']]
                er.end_entity = anno_to_doc_ind[relation['end_entity_start_idx']]
                try:
                    er.create_time = datetime.strptime(relation['create_time'], _dt_fmt)
                except ValueError:
                    er.create_time = datetime.now()
                try:
                    er.last_modified = datetime.strptime(relation['last_modified_time'], _dt_fmt)
                except ValueError:
                    er.last_modified = datetime.now()
                er.save()
        logger.info(f"Finished annotation import for project {proj['name']}")
    logger.info('Finished importing all projects')
