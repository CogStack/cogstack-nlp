import json
import logging
import os
from typing import List

import requests
from background_task import background
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.components.ner.trf.deid import DeIdModel
from medcat.tokenizing.tokens import UnregisteredDataPathException

from .model_cache import get_medcat
from .models import Entity, AnnotatedEntity, ProjectAnnotateEntities, \
    MetaAnnotation, MetaTask, Document

logger = logging.getLogger('trainer')


class RemoteEntity:
    """A simple class to mimic spaCy entity structure for remote API responses."""
    def __init__(self, entity_data, text):
        self.cui = entity_data.get('cui', '')
        self.start_char_index = entity_data.get('start', 0)
        self.end_char_index = entity_data.get('end', 0)
        self.text = entity_data.get('detected_name') or entity_data.get('source_value', '')
        self.context_similarity = entity_data.get('context_similarity', entity_data.get('acc', 0.0))
        self._meta_anns = entity_data.get('meta_anns', {})
        self._text = text

    def get_addon_data(self, key):
        """Mimic get_addon_data for meta_cat_meta_anns."""
        if key == 'meta_cat_meta_anns':
            return self._meta_anns
        return {}


class RemoteSpacyDoc:
    """A simple class to mimic spaCy document structure for remote API responses."""
    def __init__(self, linked_ents):
        self.linked_ents = linked_ents


def call_remote_model_service(service_url, text):
    """
    Call the remote MedCAT service API to process text.

    Args:
        service_url: Base URL of the remote service (e.g., http://medcat-service:8000)
        text: Text to process

    Returns:
        RemoteSpacyDoc object with linked_ents
    """
    # Ensure service_url doesn't end with /
    service_url = service_url.rstrip('/')
    api_url = f"{service_url}/api/process"

    payload = {
        "text": text
    }

    try:
        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        # Extract entities from the response
        entities_data = result.get('entities', {})
        linked_ents = []

        for _, entity_data in entities_data.items():
            linked_ents.append(RemoteEntity(entity_data, text))

        return RemoteSpacyDoc(linked_ents)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling remote model service at {api_url}: {e}")
        raise Exception(f"Failed to call remote model service: {str(e)}") from e
    except Exception as e:
        logger.error(f"Error processing remote model service response: {e}")
        raise Exception(f"Failed to process remote model service response: {str(e)}") from e


def remove_annotations(document, project, partial=False):
    try:
        if partial:
            # Removes only the ones that are not validated
            AnnotatedEntity.objects.filter(project=project,
                                           document=document,
                                           validated=False).delete()
            logger.debug(f"Unvalidated Annotations removed for:{document.id}")
        else:
            # Removes everything
            AnnotatedEntity.objects.filter(project=project, document=document).delete()
            logger.debug(f"All Annotations removed for:{document.id}")
    except Exception as e:
        logger.debug(f"Something went wrong: {e}")


class SimpleFilters:
    """Simple filter object for remote service when cat is not available."""
    def __init__(self, cuis=None, cuis_exclude=None):
        self.cuis = cuis or set()
        self.cuis_exclude = cuis_exclude or set()


def add_annotations(spacy_doc, user, project, document, existing_annotations, cat=None, filters=None, similarity_threshold=0.3):
    """
    Add annotations from spacy_doc to the database.

    Args:
        spacy_doc: spaCy document with linked_ents or RemoteSpacyDoc
        user: User object
        project: ProjectAnnotateEntities object
        document: Document object
        existing_annotations: List of existing AnnotatedEntity objects
        cat: CAT object (optional, required if filters not provided)
        filters: SimpleFilters object (optional, used when cat is None)
        similarity_threshold: float (optional, default 0.3, used when cat is None)
    """
    spacy_doc.linked_ents.sort(key=lambda x: len(x.text), reverse=True)

    tkns_in = []
    ents = []
    existing_annos_intervals = [(ann.start_ind, ann.end_ind) for ann in existing_annotations]
    # all MetaTasks and associated values
    # that can be produced are expected to have available models
    try:
        metatask2obj = {task_name: MetaTask.objects.get(name=task_name)
                        for task_name in spacy_doc.linked_ents[0].get_addon_data('meta_cat_meta_anns').keys()}
        metataskvals2obj = {task_name: {v.name: v for v in MetaTask.objects.get(name=task_name).values.all()}
                            for task_name in spacy_doc.linked_ents[0].get_addon_data('meta_cat_meta_anns').keys()}
    except (AttributeError, IndexError, UnregisteredDataPathException):
        # IndexError: ignore if there are no annotations in this doc
        # AttributeError: ignore meta_anns that are not present - i.e. non model pack preds
        # or model pack preds with no meta_anns
        metatask2obj = {}
        metataskvals2obj = {}
        pass

    # Get filters and similarity threshold
    if cat is not None:
        filters_obj = cat.config.components.linking.filters
        MIN_ACC = cat.config.components.linking.similarity_threshold
    else:
        filters_obj = filters or SimpleFilters()
        MIN_ACC = similarity_threshold

    def check_filters(cui, filters):
        if cui in filters.cuis or not filters.cuis:
            return cui not in filters.cuis_exclude
        else:
            return False

    for ent in spacy_doc.linked_ents:
        if check_filters(ent.cui, filters_obj):
            ents.append(ent)

    logger.debug('Found %s annotations to store', len(ents))
    for ent in ents:
        logger.debug('Processing annotation ent %s of %s', ents.index(ent), len(ents))
        label = ent.cui

        if not Entity.objects.filter(label=label).exists():
            # Create the entity
            entity = Entity()
            entity.label = label
            entity.save()
        else:
            entity = Entity.objects.get(label=label)

        ann_ent = AnnotatedEntity.objects.filter(project=project,
                                                  document=document,
                                                  entity=entity,
                                                  start_ind=ent.start_char_index,
                                                  end_ind=ent.end_char_index).first()
        if ann_ent is None:
            # If this entity doesn't exist already
            ann_ent = AnnotatedEntity()
            ann_ent.user = user
            ann_ent.project = project
            ann_ent.document = document
            ann_ent.entity = entity
            ann_ent.value = ent.text
            ann_ent.start_ind = ent.start_char_index
            ann_ent.end_ind = ent.end_char_index
            ann_ent.acc = ent.context_similarity

            if ent.context_similarity < MIN_ACC:
                ann_ent.deleted = True
                ann_ent.validated = True

            ann_ent.save()

            # TODO: Fix before v2 release.
            # check the ent.get_addon_data('meta_cat_meta_anns') if it exists
            # if hasattr(ent, 'get_addon_data') and \
            #            len(metatask2obj) > 0 and
            #            len(metataskvals2obj) > 0:
            #     logger.debug('Found %s meta annos on ent', len(ent._.meta_anns.items()))
            #     for meta_ann_task, pred in ent._.meta_anns.items():
            #         meta_anno_obj = MetaAnnotation()
            #         meta_anno_obj.predicted_meta_task_value = metataskvals2obj[meta_ann_task][pred['value']]
            #         meta_anno_obj.meta_task = metatask2obj[meta_ann_task]
            #         meta_anno_obj.annotated_entity = ann_ent
            #         meta_anno_obj.meta_task_value = metataskvals2obj[meta_ann_task][pred['value']]
            #         meta_anno_obj.acc = pred['confidence']
            #         meta_anno_obj.save()
            #         logger.debug('Successfully saved %s', meta_anno_obj)


def clear_cdb_cnf_addons(cdb: CDB, cdb_id: str | int):
    # NOTE: when loading a CDB separately, we don't necessarily want to
    #       load / create addons like MetaCAT as well
    logger.info('Clearing addons for CDB upon load: %s', cdb_id)
    cdb.config.components.addons.clear()


def get_create_cdb_infos(cdb, concept, cui, cui_info_prop, code_prop, desc_prop, model_clazz):
    codes = [c[code_prop] for c in cdb.cui2info.get(cui, {}).get(cui_info_prop, []) if code_prop in c]
    existing_codes = model_clazz.objects.filter(code__in=codes)
    codes_to_create = set(codes) - set([c.code for c in existing_codes])
    for code in codes_to_create:
        new_code = model_clazz()
        new_code.code = code
        descs = [c[desc_prop] for c in cdb.cui2info[cui][cui_info_prop]
                 if c[code_prop] == code]
        if len(descs) > 0:
            new_code.desc = [c[desc_prop] for c in cdb.cui2info[cui][cui_info_prop]
                             if c[code_prop] == code][0]
            new_code.cdb = concept.cdb
            new_code.save()
    return model_clazz.objects.filter(code__in=codes)


def create_annotation(source_val: str, selection_occurrence_index: int, cui: str, user: User,
                      project: ProjectAnnotateEntities, document: Document):
    text = document.text
    id = None

    all_occurrences_start_idxs = []
    idx = 0
    while idx != -1:
        idx = text.find(source_val, idx)
        if idx != -1:
            all_occurrences_start_idxs.append(idx)
            idx += len(source_val)

    start = all_occurrences_start_idxs[selection_occurrence_index]

    if start is not None and len(source_val) > 0 and len(cui) > 0:
        # Allow overlapping annotations - removed overlap constraint
        end = start + len(source_val)

        cnt = Entity.objects.filter(label=cui).count()
        if cnt == 0:
            # Create the entity
            entity = Entity()
            entity.label = cui
            entity.save()
        else:
            entity = Entity.objects.get(label=cui)

        ann_ent = AnnotatedEntity()
        ann_ent.user = user
        ann_ent.project = project
        ann_ent.document = document
        ann_ent.entity = entity
        ann_ent.value = source_val
        ann_ent.start_ind = start
        ann_ent.end_ind = end
        ann_ent.acc = 1
        ann_ent.validated = True
        ann_ent.manually_created = True
        ann_ent.correct = True
        ann_ent.save()
        id = ann_ent.id

    return id


def train_medcat(cat, project, document):
    # Get all annotations
    anns = AnnotatedEntity.objects.filter(project=project, document=document, validated=True, killed=False)
    text = document.text
    spacy_doc = cat(text)

    if len(anns) > 0 and text is not None and len(text) > 5:
        for ann in anns:
            cui = ann.entity.label
            # Indices for this annotation
            spacy_entity = [tkn for tkn in spacy_doc if tkn.char_index == ann.start_ind]
            # This will add the concept if it doesn't exist and if it
            # does just link the new name to the concept, if the namee is
            # already linked then it will just train.
            manually_created = False
            if ann.manually_created or ann.alternative:
                manually_created = True

            cat.trainer.add_and_train_concept(
                cui=cui,
                name=ann.value,
                mut_doc=spacy_doc,
                mut_entity=spacy_entity,
                negative=ann.deleted,
                devalue_others=manually_created
            )

    # Completely remove concept names that the user killed
    killed_anns = AnnotatedEntity.objects.filter(project=project, document=document, killed=True)
    for ann in killed_anns:
        cui = ann.entity.label
        name = ann.value
        cat.trainer.unlink_concept_name(cui=cui, name=name)

    # Add irrelevant cuis to cui_exclude
    irrelevant_anns = AnnotatedEntity.objects.filter(project=project, document=document, irrelevant=True)
    for ann in irrelevant_anns:
        cui = ann.entity.label
        if 'cuis_exclude' not in cat.config.components.linking.filters:
            cat.config.components.linking.filters['cuis_exclude'] = set()
        cat.config.components.linking.filters.get('cuis_exclude').update([cui])


@background(schedule=1, queue='doc_prep')
def prep_docs(project_id: List[int], doc_ids: List[int], user_id: int):
    user = User.objects.get(id=user_id)
    project = ProjectAnnotateEntities.objects.get(id=project_id)
    docs = Document.objects.filter(id__in=doc_ids)

    # Get CUI filters
    cuis = set()
    if project.cuis is not None and project.cuis:
        cuis = set([str(cui).strip() for cui in project.cuis.split(",")])
    if project.cuis_file is not None and project.cuis_file:
        try:
            cuis.update(json.load(open(project.cuis_file.path)))
        except FileNotFoundError:
            logger.warning('Missing CUI filter file for project %s', project.id)

    if project.use_model_service:
        # Use remote model service
        logger.info('Using remote model service in bg process for project: %s', project.id)
        filters = SimpleFilters(cuis=cuis)
        for doc in docs:
            logger.info('Running remote MedCAT service for project %s:%s over doc: %s', project.id, project.name, doc.id)
            spacy_doc = call_remote_model_service(project.model_service_url, doc.text)
            anns = AnnotatedEntity.objects.filter(document=doc).filter(project=project)
            with transaction.atomic():
                add_annotations(spacy_doc=spacy_doc,
                                user=user,
                                project=project,
                                document=doc,
                                cat=None,
                                filters=filters,
                                similarity_threshold=0.3,
                                existing_annotations=anns)
            project.prepared_documents.add(doc)
    else:
        # Use local medcat model
        logger.info('Loading CAT object in bg process for project: %s', project.id)
        cat = get_medcat(project=project)

        # Set CAT filters
        cat.config.components.linking.filters.cuis = cuis

        for doc in docs:
            logger.info('Running MedCAT model for project %s:%s over doc: %s', project.id, project.name, doc.id)
            if not project.deid_model_annotation:
                spacy_doc = cat(doc.text)
            else:
                deid = DeIdModel(cat)
                spacy_doc = deid(doc.text)
            anns = AnnotatedEntity.objects.filter(document=doc).filter(project=project)
            with transaction.atomic():
                add_annotations(spacy_doc=spacy_doc,
                                user=user,
                                project=project,
                                document=doc,
                                cat=cat,
                                existing_annotations=anns)
            project.prepared_documents.add(doc)
    project.save()
    logger.info('Prepared all docs for project: %s, docs processed: %s',
                project.id, project.prepared_documents)


@receiver(post_save, sender=ProjectAnnotateEntities)
def save_project_anno(sender, instance, **kwargs):
    if instance.cuis_file:
        post_save.disconnect(save_project_anno, sender=ProjectAnnotateEntities)
        cuis_from_file = json.load(open(instance.cuis_file.path))
        cui_list = [c.strip() for c in instance.cuis.split(',')]
        instance.cuis = ','.join(set(cui_list) - set(cuis_from_file))
        instance.save()
        post_save.connect(save_project_anno, sender=ProjectAnnotateEntities)



def env_str_to_bool(var: str, default: bool):
    val = os.environ.get(var, default)
    if isinstance(val, str):
        if val.lower() in ('1', 'true', 't', 'y'):
            return True
        elif val.lower() in ('0', 'false', 'f', 'n'):
            return False
    return val
