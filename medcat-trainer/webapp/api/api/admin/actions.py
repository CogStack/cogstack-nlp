import copy
import json
import logging
from datetime import datetime
from io import StringIO
from typing import Dict, List

from background_task import background
from django.db.models import QuerySet
from django.http import HttpResponse
from rest_framework.exceptions import PermissionDenied

from api.models import AnnotatedEntity, MetaAnnotation, EntityRelation, Document, ConceptDB
from api.solr_utils import drop_collection, import_all_concepts

from medcat.cdb import CDB

logger = logging.getLogger(__name__)

_dt_fmt = '%Y-%m-%d %H:%M:%S.%f'


def reset_project(modeladmin, request, queryset):
    if not request.user.is_staff:
        raise PermissionDenied

    for project in queryset:
        # Remove all annotations and cascade to meta anns
        AnnotatedEntity.objects.filter(project=project).delete()

        # Clear validated_docuents and prepared_documents
        project.validated_documents.clear()
        project.prepared_documents.clear()



def download_without_text(modeladmin, request, queryset):
    if not request.user.is_staff:
        raise PermissionDenied

    projects = queryset
    return download_projects_without_text(projects, with_doc_name=False)


def download_without_text_with_doc_names(modeladmin, request, queryset):
    if not request.user.is_staff:
        raise PermissionDenied

    projects = queryset
    return download_projects_without_text(projects, with_doc_name=True)


def download_projects_without_text(projects, with_doc_name):

    all_projects_out = {'projects': []}
    for project in projects:
        out = {}
        out['name'] = project.name
        out['id'] = project.id
        out['cuis'] = project.cuis
        out['documents'] = []

        if project.cuis_file is not None and project.cuis_file:
            # Add cuis from json file if it exists
            cuis_from_file = ",".join(json.load(open(project.cuis_file.path)))
            all_cuis = out['cuis'] + "," + cuis_from_file if len(out['cuis']) > 0 else cuis_from_file
            out['cuis'] = all_cuis

        for doc in project.validated_documents.all():
            out_doc = {}
            out_doc['id'] = doc.id
            out_doc['last_modified'] = str(doc.last_modified)
            out_doc['annotations'] = []
            if with_doc_name:
                out_doc['name'] = doc.name

            anns = AnnotatedEntity.objects.filter(project=project, document=doc)

            for ann in anns:
                out_ann = {}
                out_ann['id'] = ann.id
                out_ann['user'] = ann.user.username
                out_ann['validated'] = ann.validated
                out_ann['correct'] = ann.correct
                out_ann['deleted'] = ann.deleted
                out_ann['alternative'] = ann.alternative
                out_ann['killed'] = ann.killed
                out_ann['irrelevant'] = ann.irrelevant
                out_ann['last_modified'] = str(ann.last_modified)
                out_ann['manually_created'] = ann.manually_created
                out_ann['acc'] = ann.acc
                out_ann['meta_anns'] = {}

                # Get MetaAnnotations
                meta_anns = MetaAnnotation.objects.filter(annotated_entity=ann)
                for meta_ann in meta_anns:
                    o_meta_ann = {}
                    o_meta_ann['name'] = meta_ann.meta_task.name
                    o_meta_ann['value'] = meta_ann.meta_task_value.name
                    o_meta_ann['acc'] = meta_ann.acc
                    o_meta_ann['validated'] = meta_ann.validated

                    # Add annotation
                    key = meta_ann.meta_task.name
                    out_ann['meta_anns'][key] = o_meta_ann

                out_doc['annotations'].append(out_ann)
            out['documents'].append(out_doc)
        all_projects_out['projects'].append(out)

    sio = StringIO()
    json.dump(all_projects_out, sio)
    sio.seek(0)

    f_name = "MedCAT_Export_No_Text_{}.json".format(datetime.now().strftime('%Y-%m-%d:%H:%M:%S'))
    response = HttpResponse(sio, content_type='text/json')
    response['Content-Disposition'] = 'attachment; filename={}'.format(f_name)
    return response


def download(modeladmin, request, queryset):
    if not request.user.is_staff:
        raise PermissionDenied
    projects = queryset
    return download_projects_with_text(projects)


def download_projects_with_text(projects: QuerySet):
    all_projects = retrieve_project_data(projects)

    sio = StringIO()
    json.dump(all_projects, sio)
    sio.seek(0)

    f_name = "MedCAT_Export_With_Text_{}.json".format(datetime.now().strftime('%Y-%m-%d:%H:%M:%S'))
    response = HttpResponse(sio, content_type='text/json')
    response['Content-Disposition'] = 'attachment; filename={}'.format(f_name)

    return response


def retrieve_project_data(projects: QuerySet) -> Dict[str, List]:
    """
    A function to convert a list of projects and:
        - their associated documents,
        - their associated annotations,
        - their associated Meta annotations and Relation Annotations
    for serialization.
    Output schema is as follows: ((optional) indicates this field isn't required for training a MedCAT model)
    {
    "projects": [
        {
            "name": "<project_name"  # name of the project
            "id": "<id>"  # the auto-generated id of the project (optional)
            "project_group_id": "<id>"  # the auto-generated id of the project - nullable
            "project_group_name": "<group_name>"   # the name of the project group if set.
            "project_status": "<project_status>"   # status - either annotating, discontinued, complete
            "project_locked": "<project_locked>"   # locked - for no further annotations
            "cuis": ["cui_1", "cui_2" ... ]  # the CUI filter for the project, includes those from file / and text-box
            "meta_anno_defs": [
                # list of meta annotation tasks configured for this project.
                {
                    "name": "Name of meta annotation task",
                    "values": [
                        "<first value>",
                        "<second value>"
                        ...
                    ],
                },
                ... more meta_annotation tasks configured for this project
            ],
            "relation_anno_defs": [
                "<name1>",
                "<name2>"
                ... more relation annotation task names configured for this project
            ]
            "documents": [
                {
                "id": "<id>"  # the auto-generated id of the document (optional)
                "name": "<name>"  # the name of the document (optional), but used in stat printing during training
                "text": "<text>"  # the text of the document
                "last_modified": "<date time>"  # the last modified-time (optional)
                "annotations": [{
                    "id": "<id>"  # the auto-generated id of the document (optional)
                    "name": "<username string>"  # the user who made the annotation (optional)
                    "cui": "<cui string>"  # the cui label for this annotation
                    "value": "<string>"  # the text span for this annotation
                    "start": <integer>  # the start index of this annotation with respect to the document text
                    "end": <integer>  # the end index of this annotation with respect to the document text
                    "validated": <boolean>  # if the annotation has been marked by a human annotator
                    "correct": <boolean>  # if the text span is correctly linked to the CUI of this annotation
                    "deleted": <boolean>  # if the text span was incorrectly linked or 'not' linked by MedCAT due to low scores
                    "alternative": <boolean>  # if the text span was incorrectly linked by MedCAT, then correctly linked by a human annotator
                    "killed":  <boolean>  # if a human annotator 'terminated' this annotation
                    "irrelevant": <boolean>  # if a human annotator has marked an annotation as irrelevant (optional)
                    "acc": <float>  # accuracy provided by MedCAT (optional)
                    "comment": "<comment string>" # the text entered by an annotator during annotation (optional)
                    "meta_anns": [
                        # list of meta annotations if applicable to project
                        {
                            "name": <string>  # Meta anno task name, i.e. temporality
                            "value": <string>  # the selected meta anno task value for, ie. "past" or "present"
                            "acc":  <float>   # default 1, (optional)
                            "validated": <boolean>  # Meta annotation has been made by a human annotator, default (true)
                        },
                        ... <more meta annotations of the same as above structure>
                    ]},
                    ... <more annotations of the same above structure>
                ]
                "relations": [
                    {
                        "start_entity": <integer>  # id of above annotation that is the start of this relation
                        "start_entity_cui": "<string>" # the cui label of the start of this relation
                        "start_entity_value": <string>  # value of the start annotation for this relation
                        "start_entity_start_idx": <integer>  # start index of text span of start of relation
                        "start_entity_end_idx": <integer>  # end index of text span of start of relation
                        "end_entity": <integer>  # id of the above annotation that is the end of this relation
                        "end_entity_cui": "<string>" # the cui label of the end of this relation
                        "end_entity_value": <string>  # value of the end annotation for this relation
                        "end_entity_start_idx": <integer>  # end index of text span of end of relation
                        "end_entity_end_idx": <integer>  # end index of text span of end of relation
                        "user": <string>  # username of annotator for relation (optional)
                        "relation": <string>  # label for this relation
                        "validated": <boolean>  # if the annotation has been validated by a human annotator, default true.
                    }
                    ... < more relations of the samve above structure>
                ]

                ... <more documents of the same above structure>
            ]
    ]
    }

    Args:
        projects (QuerySet): the projects to export data for.
    """
    all_projects = {'projects': []}
    for project in projects:
        out = {}
        out['name'] = project.name
        out['id'] = project.id
        out['cuis'] = project.cuis
        out['project_group_id'] = project.group.id if project.group else None
        out['project_group_name'] = project.group.name if project.group else None
        out['project_status'] = project.project_status
        out['project_locked'] = project.project_locked
        out['meta_anno_defs'] = [{'name': t.name, 'values': [v.name for v in t.values.all()]}
                                 for t in project.tasks.all()]
        out['relation_anno_defs'] = [r.label for r in project.relations.all()]
        out['documents'] = []

        if project.cuis_file is not None and project.cuis_file:
            # Add cuis from json file if it exists
            cuis_from_file = ",".join(json.load(open(project.cuis_file.path)))
            all_cuis = out['cuis'] + "," + cuis_from_file if len(out['cuis']) > 0 else cuis_from_file
            out['cuis'] = all_cuis

        for doc in project.validated_documents.all():
            out_doc = {}
            out_doc['id'] = doc.id
            out_doc['name'] = doc.name
            out_doc['text'] = doc.text
            out_doc['last_modified'] = doc.last_modified.strftime(_dt_fmt)
            out_doc['annotations'] = []

            anns = AnnotatedEntity.objects.filter(project=project, document=doc)

            for ann in anns:
                out_ann = {}
                out_ann['id'] = ann.id
                out_ann['user'] = ann.user.username
                out_ann['cui'] = ann.entity.label
                out_ann['value'] = ann.value
                out_ann['start'] = ann.start_ind
                out_ann['end'] = ann.end_ind
                out_ann['validated'] = ann.validated
                out_ann['correct'] = ann.correct
                out_ann['deleted'] = ann.deleted
                out_ann['alternative'] = ann.alternative
                out_ann['killed'] = ann.killed
                out_ann['irrelevant'] = ann.irrelevant
                out_ann['create_time'] = ann.create_time.strftime(_dt_fmt)
                out_ann['last_modified'] = ann.last_modified.strftime(_dt_fmt)
                out_ann['comment'] = ann.comment
                out_ann['manually_created'] = ann.manually_created
                out_ann['acc'] = ann.acc
                out_ann['meta_anns'] = {}

                # Get MetaAnnotations
                meta_anns = MetaAnnotation.objects.filter(annotated_entity=ann)
                for meta_ann in meta_anns:
                    o_meta_ann = {}
                    o_meta_ann['name'] = meta_ann.meta_task.name
                    o_meta_ann['value'] = meta_ann.meta_task_value.name
                    o_meta_ann['acc'] = meta_ann.acc
                    o_meta_ann['validated'] = meta_ann.validated

                    # Add annotation
                    key = meta_ann.meta_task.name
                    out_ann['meta_anns'][key] = o_meta_ann

                out_doc['annotations'].append(out_ann)

            # Add relations if they exist
            rels = EntityRelation.objects.filter(project=project, document=doc)
            out_rels = []
            out_rel = {}
            for rel in rels:
                out_rel['start_entity'] = rel.start_entity.id
                out_rel['start_entity_cui'] = rel.start_entity.entity.label
                out_rel['start_entity_value'] = rel.start_entity.value
                out_rel['start_entity_start_idx'] = rel.start_entity.start_ind
                out_rel['start_entity_end_idx'] = rel.start_entity.end_ind
                out_rel['end_entity'] = rel.end_entity.id
                out_rel['end_entity_cui'] = rel.end_entity.entity.label
                out_rel['end_entity_value'] = rel.end_entity.value
                out_rel['end_entity_start_idx'] = rel.end_entity.start_ind
                out_rel['end_entity_end_idx'] = rel.end_entity.end_ind
                out_rel['user'] = rel.user.username
                out_rel['relation'] = rel.relation.label
                out_rel['validated'] = rel.validated

                out_rels.append(out_rel)
                out_rel = {}
            out_doc['relations'] = out_rels

            out['documents'].append(out_doc)
        all_projects['projects'].append(out)
    return all_projects


def clone_projects(modeladmin, request, queryset):
    if not request.user.is_staff:
        raise PermissionDenied

    projects = queryset
    for project in projects:
        project_copy = copy.copy(project)
        project_copy.id = None
        project_copy.pk = None
        project_copy.name = f'{project.name} (Clone)'
        project_copy.save()

        # Add M2M fields
        for m in project.members.all():
            project_copy.members.add(m)
        for c in project.cdb_search_filter.all():
            project_copy.cdb_search_filter.add(c)
        for t in project.tasks.all():
            project_copy.tasks.add(t)

        project_copy.save()


def dataset_document_counts(dataset):
    return f'{Document.objects.filter(dataset=dataset).count()}'


@background(schedule=5)
def _reset_cdb_filters(id):
    concept_db = ConceptDB.objects.get(id=id)
    cdb = CDB.load(concept_db.cdb_file.path)
    cdb.config.components.linking.filters = {'cuis': set()}
    cdb.save(concept_db.cdb_file.path)


@background(schedule=5)
def import_concepts_from_cdb(cdb_model_id: int):
    cdb_model = ConceptDB.objects.get(id=cdb_model_id)
    cdb = CDB.load(cdb_model.cdb_file.path)
    import_all_concepts(cdb, cdb_model)


def reset_cdb_filters(modeladmin, request, queryset):
    for concept_db in queryset:
        _reset_cdb_filters(concept_db.id)


def import_concepts(modeladmin, request, queryset):
    for concept_db in queryset:
        logger.info(f'Importing concepts for collection {concept_db.name}_id_{concept_db.id}')
        import_concepts_from_cdb(concept_db.id)


def delete_indexed_concepts(modeladmin, request, queryset):
    for concept_db in queryset:
        drop_collection(concept_db)


def remove_all_documents(modeladmin, request, queryset):
    Document.objects.all().delete()
