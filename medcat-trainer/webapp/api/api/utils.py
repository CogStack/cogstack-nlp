import json
import logging
import os
from typing import List

from background_task import background
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from medcat.cat import CAT
from medcat.components.ner.trf.deid import DeIdModel

from .model_cache import get_medcat
from .models import Entity, AnnotatedEntity, ProjectAnnotateEntities, \
    MetaAnnotation, MetaTask, Document

logger = logging.getLogger('trainer')


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


def add_annotations(spacy_doc, user, project, document, existing_annotations, cat):
    spacy_doc.final_ents.sort(key=lambda x: len(x.text), reverse=True)

    tkns_in = []
    ents = []
    existing_annos_intervals = [(ann.start_ind, ann.end_ind) for ann in existing_annotations]
    # all MetaTasks and associated values
    # that can be produced are expected to have available models
    try:
        metatask2obj = {task_name: MetaTask.objects.get(name=task_name)
                        for task_name in spacy_doc.final_ents[0].get_addon_data('meta_cat_meta_anns').keys()}
        metataskvals2obj = {task_name: {v.name: v for v in MetaTask.objects.get(name=task_name).values.all()}
                            for task_name in spacy_doc.final_ents[0].get_addon_data('meta_cat_meta_anns').keys()}
    except (AttributeError, IndexError):
        # IndexError: ignore if there are no annotations in this doc
        # AttributeError: ignore meta_anns that are not present - i.e. non model pack preds
        # or model pack preds with no meta_anns
        metatask2obj = {}
        metataskvals2obj = {}
        pass

    def check_ents(ent):
        return any((ea[0] < ent.start_char < ea[1]) or
                   (ea[0] < ent.end_char < ea[1]) for ea in existing_annos_intervals)

    def check_filters(cui, filters):
        if cui in filters.cuis or not filters.cuis:
            return cui not in filters.cuis_exclude
        else:
            return False

    for ent in spacy_doc.final_ents:
        if not check_ents(ent) and check_filters(ent.cui, cat.config.components.linking.filters):
            to_add = True
            for tkn in ent:
                if tkn in tkns_in:
                    to_add = False
            if to_add:
                for tkn in ent:
                    tkns_in.append(tkn)
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

            MIN_ACC = cat.config.components.linking.similarity_threshold
            if ent.context_similarity < MIN_ACC:
                ann_ent.deleted = True
                ann_ent.validated = True

            ann_ent.save()

            # check the ent._.meta_anns if it exists
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


def _remove_overlap(project, document, start, end):
    anns = AnnotatedEntity.objects.filter(project=project, document=document)

    for ann in anns:
        if (start <= ann.start_ind <= end) or (start <= ann.end_ind <= end):
            logger.debug("Removed %s ", str(ann))
            ann.delete()


def create_annotation(source_val: str, selection_occurrence_index: int, cui: str, user: User,
                      project: ProjectAnnotateEntities, document, cat: CAT):
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
        # Remove overlaps
        end = start + len(source_val)
        _remove_overlap(project, document, start, end)

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

    logger.info('Loading CAT object in bg process for project: %s', project.id)
    cat = get_medcat(project=project)

    # Set CAT filters
    cat.config.components.linking.filters.cuis = project.cuis

    for doc in docs:
        logger.info(f'Running MedCAT model for project {project.id}:{project.name} over doc: {doc.id}')
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
            # add doc to prepared_documents
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
