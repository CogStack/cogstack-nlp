import logging
import os
from smtplib import SMTPException
from tempfile import NamedTemporaryFile
from typing import Any

from background_task.models import Task, CompletedTask
from django.contrib.auth.views import PasswordResetView
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseServerError, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django_filters import rest_framework as drf

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from medcat.components.ner.trf.deid import DeIdModel
from medcat.utils.cdb_utils import ch2pt_from_pt2ch, get_all_ch, snomed_ct_concept_path
from medcat.utils.config_utils import temp_changed_config


from .admin import download_projects_with_text, download_projects_without_text, \
    import_concepts_from_cdb
from .data_utils import upload_projects_export
from .metrics import calculate_metrics
from .model_cache import get_medcat, get_medcat_from_model_pack_id, get_cached_cdb, VOCAB_MAP, clear_cached_medcat, clear_cached_medcat_by_model_pack_id, is_model_pack_loaded, CAT_MAP, CDB_MAP, is_model_loaded
from .permissions import *
from .serializers import *
from .solr_utils import collections_available, search_collection, ensure_concept_searchable
from .utils import add_annotations, remove_annotations, train_medcat, create_annotation, prep_docs

logger = logging.getLogger(__name__)

# For local testing, put envs
"""
from environs import Env
env = Env()
env.read_env("/home/ubuntu/projects/MedAnno/MedAnno/env_umls", recurse=False)
print(os.environ)
"""

logger = logging.getLogger(__name__)


# Get the basic version of MedCAT
cat = None

def index(request):
    return render(request, 'index.html')


class TextInFilter(drf.BaseInFilter, drf.CharFilter):
    pass
class NumInFilter(drf.BaseInFilter, drf.NumberFilter):
    pass


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'put']
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer

    filterset_fields = ['username']


class ProjectAnnotateEntitiesViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'put']
    queryset = ProjectAnnotateEntities.objects.all()
    serializer_class = ProjectAnnotateEntitiesSerializer
    filterset_fields = ['members', 'dataset', 'id', 'project_status', 'annotation_classification']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            projects = ProjectAnnotateEntities.objects.all()
        else:
            projects = ProjectAnnotateEntities.objects.filter(members=user.id)

        return projects


class ProjectGroupFilter(drf.FilterSet):
    id__in = NumInFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = ProjectGroup
        fields = ['id', 'name', 'description']

class ProjectGroupViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = ProjectGroup.objects.all()
    serializer_class = ProjectGroupSerializer
    filterset_fields = ['id']
    filterset_class = ProjectGroupFilter


class AnnotatedEntityFilter(drf.FilterSet):
    id__in = NumInFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = AnnotatedEntity
        fields = ['id', 'user', 'project', 'document', 'entity', 'validated',
                  'deleted']


class AnnotatedEntityViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = AnnotatedEntity.objects.all()
    serializer_class = AnnotatedEntitySerializer
    filterset_class = AnnotatedEntityFilter


class MetaTaskValueViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'head', 'post', 'put']
    queryset = MetaTaskValue.objects.all()
    serializer_class = MetaTaskValueSerializer


class MetaTaskViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'head', 'post', 'put']
    queryset = MetaTask.objects.all()
    serializer_class = MetaTaskSerializer


class MetaAnnotationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'head', 'post', 'put', 'delete']
    queryset = MetaAnnotation.objects.all()
    serializer_class = MetaAnnotationSerializer
    filterset_fields = ['id', 'annotated_entity', 'validated']


class DocumentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    filterset_fields = ['dataset']


class EntityViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head']
    queryset = Entity.objects.all()
    serializer_class = EntitySerializer


class RelationFilter(drf.FilterSet):
    id__in = NumInFilter(field_name='id', lookup_expr='in')

    class Meta:
        model = Relation
        fields = ['label']


class RelationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head']
    queryset = Relation.objects.all()
    serializer_class = RelationSerializer
    filterset_class = RelationFilter


class EntityRelationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'head', 'delete']
    queryset = EntityRelation.objects.all()
    serializer_class = EntityRelationSerializer
    filterset_fields = ['project', 'document']


class ConceptDBViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'delete']
    queryset = ConceptDB.objects.all()
    serializer_class = ConceptDBSerializer

    def perform_create(self, serializer):
        serializer.save(last_modified_by=self.request.user)


class VocabularyViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'delete']
    queryset = Vocabulary.objects.all()
    serializer_class = VocabularySerializer


class ModelPackViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'head', 'delete']
    queryset = ModelPack.objects.all()
    serializer_class = ModelPackSerializer


class DatasetViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing datasets.

    File Schema Requirements:
    - Format: .csv or .xlsx file
    - Required columns:
      * name: A unique identifier for each document
      * text: The free-text content to annotate

    Example CSV:
    name,text
    doc001,"First document text"
    doc002,"Second document text"
    """
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete']
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer


class ResetPasswordView(PasswordResetView):
    email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'
    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except SMTPException:
            return HttpResponseServerError('''SMTP settings are not configured correctly. <br>
                                           Please visit https://medcattrainer.readthedocs.io for more information to resolve this. <br>
                                           You can also ask a question at: https://discourse.cogstack.org/c/medcat/5''')

class ResetPasswordView(PasswordResetView):
    email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'
    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except SMTPException:
            return HttpResponseServerError('''SMTP settings are not configured correctly. <br>
                                           Please visit https://medcattrainer.readthedocs.io for more information to resolve this. <br>
                                           You can also ask a question at: https://discourse.cogstack.org/c/medcat/5''')

@api_view(http_method_names=['GET'])
def get_anno_tool_conf(_):
    return Response({k: v for k, v in os.environ.items()})


@api_view(http_method_names=['POST'])
def prepare_documents(request):
    # Get the user
    user = request.user
    # Get doc ids
    d_ids = request.data['document_ids']

    # Get project id
    p_id = request.data['project_id']
    project = ProjectAnnotateEntities.objects.get(id=p_id)

    # Is the entity creation forced
    force = request.data.get('force', 0)

    # Should we update
    update = request.data.get('update', 0)

    cuis = set()
    if project.cuis is not None and project.cuis:
        cuis = set([str(cui).strip() for cui in project.cuis.split(",")])
    if project.cuis_file is not None and project.cuis_file:
        # Add cuis from json file if it exists
        try:
            cuis.update(json.load(open(project.cuis_file.path)))
        except FileNotFoundError:
            return Response({'message': 'Missing CUI filter file',
                                   'description': 'Missing CUI filter file, %s, cannot be found on the filesystem, '
                                                  'but is still set on the project. To fix remove and reset the '
                                                  'cui filter file' % project.cuis_file}, status=500)
    try:
        for d_id in d_ids:
            document = Document.objects.get(id=d_id)
            if force:
                # Remove all annotations if creation is forced
                remove_annotations(document, project, partial=False)
            elif update:
                # Remove annotations that are not verified if creation is update
                remove_annotations(document, project, partial=True)

            # Get annotated entities
            anns = AnnotatedEntity.objects.filter(document=document).filter(project=project)

            is_validated = document in project.validated_documents.all()

            with transaction.atomic():
                # If the document is not already annotated, annotate it
                if (len(anns) == 0 and not is_validated) or update:
                    if project.use_model_service:
                        # Use remote model service
                        logger.info('Using remote model service for project: %s', project.id)
                        from .utils import call_remote_model_service, SimpleFilters
                        spacy_doc = call_remote_model_service(project.model_service_url, document.text)
                        filters = SimpleFilters(cuis=cuis)
                        add_annotations(spacy_doc=spacy_doc,
                                        user=user,
                                        project=project,
                                        document=document,
                                        cat=None,
                                        filters=filters,
                                        similarity_threshold=0.3,
                                        existing_annotations=anns)
                    else:
                        # Use local medcat model
                        cat = get_medcat(project=project)
                        logger.info('loaded medcat model for project: %s', project.id)

                        # Set CAT filters
                        cat.config.components.linking.filters.cuis = cuis

                        if not project.deid_model_annotation:
                            spacy_doc = cat(document.text)
                        else:
                            deid = DeIdModel(cat)
                            spacy_doc = deid(document.text)

                        add_annotations(spacy_doc=spacy_doc,
                                        user=user,
                                        project=project,
                                        document=document,
                                        cat=cat,
                                        existing_annotations=anns)

                # add doc to prepared_documents
                project.prepared_documents.add(document)
                project.save()

    except Exception as e:
        logger.warning('Error preparing documents for project %s', p_id, exc_info=e)
        return Response({'message': e.args[0] if len(e.args) > 0 else 'Internal Server Error',
                         'description': e.args[1] if len(e.args) > 1 else '',}, status=500)
    return Response({'message': 'Documents prepared successfully'})


@api_view(http_method_names=['POST'])
def prepare_documents_bg(request):
    user = request.user
    # Get project id
    p_id = request.data['project_id']
    project = ProjectAnnotateEntities.objects.get(id=p_id)
    docs = Document.objects.filter(dataset=project.dataset)

    # Get docs that have no AnnotatedEntities
    d_ids = [d.id for d in docs if len(AnnotatedEntity.objects.filter(document=d).filter(project=project)) == 0 or
             d in project.validated_documents.all()]

    # execute model infer in bg
    job = prep_docs(p_id, d_ids, user.id)
    return Response({'bg_job_id': job.id})


@api_view(http_method_names=['GET'])
def prepare_docs_bg_tasks(_):
    running_doc_prep_tasks = Task.objects.filter(queue='doc_prep')
    completed_doc_prep_tasks = CompletedTask.objects.filter(queue='doc_prep')

    def transform_task_params(task_params_str):
        task_params = json.loads(task_params_str)[0]
        return {
            'project': task_params[0],
            'user_id': task_params[2]
        }
    running_tasks = [transform_task_params(task.task_params) for task in running_doc_prep_tasks]
    complete_tasks = [transform_task_params(task.task_params) for task in completed_doc_prep_tasks]
    return Response({'running_tasks': running_tasks, 'comp_tasks': complete_tasks})


@api_view(http_method_names=['GET', 'DELETE'])
def prepare_docs_bg_task(request, proj_id):
    if request.method == 'GET':
        # state of bg running process as determined by prepared docs
        try:
            proj = ProjectAnnotateEntities.objects.get(id=proj_id)
            prepd_docs_count = proj.prepared_documents.count()
            ds_total_count = Document.objects.filter(dataset=ProjectAnnotateEntities.objects.get(id=proj_id).dataset.id).count()
            return Response({'proj_id': proj_id, 'dataset_len': ds_total_count, 'prepd_docs_len': prepd_docs_count})
        except ObjectDoesNotExist:
            return HttpResponseBadRequest('No Project found for the given ID')
    else:
        running_doc_prep_tasks = {json.loads(task.task_params)[0][0]: task.id
                                  for task in Task.objects.filter(queue='doc_prep')}
        if proj_id in running_doc_prep_tasks:
            Task.objects.filter(id=running_doc_prep_tasks[proj_id]).delete()
            return Response("Successfully stopped running response")
        else:
            return HttpResponseBadRequest('Could not find running BG Process to stop')

@api_view(http_method_names=['POST'])
def add_annotation(request):
    # Get project id
    p_id = request.data['project_id']
    d_id = request.data['document_id']
    source_val = request.data['source_value']
    sel_occur_idx = int(request.data['selection_occur_idx'])
    cui = str(request.data['cui'])

    logger.debug("Annotation being added")
    logger.debug(str(request.data))

    # Get project and the right version of cat
    user = request.user
    project = ProjectAnnotateEntities.objects.get(id=p_id)
    document = Document.objects.get(id=d_id)
    id = create_annotation(source_val=source_val,
                           selection_occurrence_index=sel_occur_idx,
                           cui=cui,
                           user=user,
                           project=project,
                           document=document)
    logger.debug('Annotation added.')
    return Response({'message': 'Annotation added successfully', 'id': id})


@api_view(http_method_names=['POST'])
def add_concept(request):
    p_id = request.data['project_id']
    d_id = request.data['document_id']
    source_val = request.data['source_value']
    sel_occur_idx = int(request.data['selection_occur_idx'])
    name = request.data['name']
    cui = request.data['cui']
    context = request.data['context']
    # TODO These aren't used, but no API in current MedCAT add_name func
    # Add these fields to the add_name func of MedCAT add_name
    desc = request.data['desc']
    type_ids = request.data['type_ids']
    s_type = request.data['type']
    synonyms = request.data['synonyms']

    user = request.user
    project = ProjectAnnotateEntities.objects.get(id=p_id)
    document = Document.objects.get(id=d_id)

    if project.use_model_service:
        # Use remote model service
        logger.error('Adding concepts is not supported for remote model service'\
                     'projects, you likely want to use a local model')
        raise NotImplementedError('Adding concepts is not supported for remote model service projects')


    cat = get_medcat(project=project)

    if cui in cat.cdb.cui2info:
        err_msg = f'Cannot add a concept "{name}" with cui:{cui}. CUI already linked to {cat.cdb.cui2info[cui]["preferred_name"]}'
        logger.error(err_msg)
        return Response({'err': err_msg}, 400)

    spacy_doc = cat(document.text)
    spacy_entity = None
    if source_val in spacy_doc.text:
        # Find all occurrences of source_val in the text
        all_occurrences_start_idxs = []
        idx = 0
        while idx != -1:
            idx = spacy_doc.text.find(source_val, idx)
            if idx != -1:
                all_occurrences_start_idxs.append(idx)
                idx += len(source_val)

        # Use selection_idx to get the correct occurrence
        if sel_occur_idx < len(all_occurrences_start_idxs):
            start = all_occurrences_start_idxs[sel_occur_idx]
            end = start + len(source_val)
            # Find tokens that overlap with the span [start, end)
            # A token overlaps if: token_start < end AND token_end > start
            spacy_entity = [tkn for tkn in spacy_doc if tkn.char_index < end and (tkn.char_index + len(tkn.text)) > start]
    # if len(spacy_entity) == 0:
    #     spacy_entity = None
    cat.trainer.add_and_train_concept(cui=cui, name=name, name_status='P', mut_doc=spacy_doc, mut_entity=spacy_entity)


    id = create_annotation(source_val=source_val,
                           selection_occurrence_index=sel_occur_idx,
                           cui=cui,
                           user=user,
                           project=project,
                           document=document)

    # ensure new concept detail is available in SOLR search service
    ensure_concept_searchable(cui, cat.cdb, project.cdb_search_filter.first())

    # add to project cuis if required.
    if (project.cuis or project.cuis_file) and project.restrict_concept_lookup:
        project.cuis = ','.join(project.cuis.split(',') + [cui])
        project.save()

    return Response({'message': 'Concept and Annotation added successfully', 'id': id})


@api_view(http_method_names=['POST'])
def import_cdb_concepts(request):
    user = request.user
    if not user.is_superuser:
        return HttpResponseBadRequest('User is not super user, and not allowed to download project outputs')
    cdb_id = request.data.get('cdb_id')
    if cdb_id is None or len(ConceptDB.objects.filter(id=cdb_id)) == 0:
        return HttpResponseBadRequest(f'No CDB found for cdb_id{cdb_id}')
    import_concepts_from_cdb(cdb_id)
    return Response({'message': 'submitted cdb import job.'})


def _submit_document(project: ProjectAnnotateEntities, document: Document):
    if project.train_model_on_submit:
        if project.use_model_service:
            # TODO: Implement this, already available in CMS / gateway instances.
            # interim model training not supported for remote model service projects
           logger.warning('Interim model training is not supported for remote model service projects')
        else:
            cat = get_medcat(project=project)
            train_medcat(cat, project, document)

    # Add cuis to filter if they did not exist
    cuis = []

    if project.cuis_file is not None and project.cuis_file:
        cuis = cuis + json.load(open(project.cuis_file.path))
    if project.cuis is not None and project.cuis:
        cuis = cuis + [str(cui).strip() for cui in project.cuis.split(",")]

    cuis = set(cuis)
    if len(cuis) > 0:  # only append to project cuis filter if there is a filter to begin with.
        anns = AnnotatedEntity.objects.filter(project=project, document=document, validated=True)
        extra_doc_cuis = [ann.entity.label for ann in anns if ann.validated and (ann.correct or ann.alternative) and
                          ann.entity.label not in cuis]
        if extra_doc_cuis:
            project.cuis += ',' + ','.join(extra_doc_cuis)
            project.save()


@api_view(http_method_names=['POST'])
def submit_document(request):
    # Get project id
    p_id = request.data['project_id']
    d_id = request.data['document_id']

    # Get project and the right version of cat
    project = ProjectAnnotateEntities.objects.get(id=p_id)
    document = Document.objects.get(id=d_id)

    try:
        _submit_document(project, document)
    except Exception:
        logger.exception("Error while submitting document")
        return HttpResponseServerError("An internal error occurred while submitting the document.")

    return Response({'message': 'Document submited successfully'})


@api_view(http_method_names=['POST'])
def save_models(request):
    # Get project id
    p_id = request.data['project_id']
    project = ProjectAnnotateEntities.objects.get(id=p_id)
    cat = get_medcat(project=project)

    cat.cdb.save(project.concept_db.cdb_file.path)

    return Response({'message': 'Models saved'})


@api_view(http_method_names=['POST'])
def get_create_entity(request):
    label = request.data['label']
    cnt = Entity.objects.filter(label=label).count()
    id = 0
    if cnt == 0:
        ent = Entity()
        ent.label = label
        ent.save()
        id = ent.id
    else:
        ent = Entity.objects.get(label=label)
        id = ent.id

    return Response({'entity_id': id})


@api_view(http_method_names=['POST'])
def create_dataset(request):
    """
    Upload a dataset and kick off document creation for each Doc. The dataset should be dict of form:
    {
        'name': ['name1', 'name2', 'name3', ... ],
        'text': ['text1...', 'text2...', 'text3...', ... ]
    }
    Args:
        request: the HTTP request
    Response:
        An HTTP resonse with the id of the created dataset
    """
    filename = f'{request.data["dataset_name"]}.csv'
    logger.debug(request.data['dataset'])
    ds = Dataset()
    ds.name = request.data['dataset_name']
    ds.description = request.data.get('description', 'n/a')
    with NamedTemporaryFile(mode='r+') as f:
        pd.DataFrame(request.data['dataset']).to_csv(f, index=False)
        ds.original_file.save(filename, f)
    logger.debug(f'Saved new dataset:{ds.original_file.path}')
    id = ds.id
    return Response({'dataset_id': id})


@api_view(http_method_names=['GET', 'POST'])
def update_meta_annotation(request):
    project_id = request.data['project_id']
    entity_id = request.data['entity_id']
    document_id = request.data['document_id']
    meta_task_id = request.data['meta_task_id']
    meta_task_value = request.data['meta_task_value']

    annotation = AnnotatedEntity.objects.filter(project= project_id, entity=entity_id, document=document_id)[0]
    annotation.correct = True
    annotation.validated = True
    logger.debug(annotation)

    annotation.save()

    meta_task = MetaTask.objects.filter(id = meta_task_id)[0]
    meta_task_value = MetaTaskValue.objects.filter(id = meta_task_value)[0]

    meta_annotation_list = MetaAnnotation.objects.filter(annotated_entity = annotation)

    logger.debug(meta_annotation_list)

    if len(meta_annotation_list) > 0:
        meta_annotation = meta_annotation_list[0]

        meta_annotation.meta_task = meta_task
        meta_annotation.meta_task_value = meta_task_value

    else:
        meta_annotation = MetaAnnotation()
        meta_annotation.annotated_entity = annotation
        meta_annotation.meta_task = meta_task
        meta_annotation.meta_task_value = meta_task_value

    logger.debug(meta_annotation)
    meta_annotation.save()

    return Response({'meta_annotation': 'added meta annotation'})


@api_view(http_method_names=['POST'])
def annotate_text(request):
    message = request.data.get('message')
    cuis = request.data.get('cuis', [])
    p_id = request.data.get('project_id')
    modelpack_id = request.data.get('modelpack_id')
    include_sub_concepts = request.data.get('include_sub_concepts', False)

    if message is None or (p_id is None and modelpack_id is None):
        return HttpResponseBadRequest('No message to annotate')

    if modelpack_id is not None:
        try:
            cat = get_medcat_from_model_pack_id(int(modelpack_id))
        except (ValueError, TypeError):
            logger.warning(f'Invalid modelpack_id received for project:{p_id}')
            return HttpResponseBadRequest('Invalid modelpack_id for project')
        except ModelPack.DoesNotExist:
            logger.warning(f'ModelPack does not exist received for project:{p_id}')
            return HttpResponseBadRequest('ModelPack does not exist for project')
    else:
        project = ProjectAnnotateEntities.objects.get(id=p_id)
        cat = get_medcat(project=project)

    # Normalise cuis to a set[str]
    if isinstance(cuis, str):
        cuis_set = {c.strip() for c in cuis.split(',') if c.strip()}
    elif isinstance(cuis, (list, tuple, set)):
        cuis_set = {str(c).strip() for c in cuis if str(c).strip()}
    else:
        cuis_set = set()

    # Expand CUIs to include sub-concepts if requested
    if include_sub_concepts and cuis_set and cat.cdb:
        expanded_cuis = set(cuis_set)
        for parent_cui in cuis_set:
            try:
                child_cuis = get_all_ch(parent_cui, cat.cdb)
                expanded_cuis.update(child_cuis)
            except Exception as e:
                logger.warning(f'Failed to get children for CUI {parent_cui}: {e}')
        cuis_set = expanded_cuis

    with temp_changed_config(cat.config.components.linking, 'filters', cuis_set):
        spacy_doc = cat(message)

    ents = []
    anno_tkns = []
    for ent in spacy_doc.linked_ents:
        cnt = Entity.objects.filter(label=ent.cui).count()
        inc_ent = all(tkn not in anno_tkns for tkn in ent)
        if inc_ent and cnt != 0:
            meta_annotations = []
            if 'meta_cat_meta_anns' in ent.get_available_addon_paths():
                meta_anns = ent.get_addon_data('meta_cat_meta_anns')
                for meta_ann_task, pred in meta_anns.items():
                    # Extract value and confidence from pred
                    # pred can be a dict, object, or string
                    if isinstance(pred, dict):
                        pred_value = pred.get('value', str(pred))
                        pred_confidence = pred.get('confidence', None)
                    elif hasattr(pred, 'value'):
                        pred_value = pred.value
                        pred_confidence = getattr(pred, 'confidence', None)
                    else:
                        pred_value = str(pred)
                        pred_confidence = None
                    meta_annotations.append({
                        'task': meta_ann_task,
                        'value': pred_value,
                        'confidence': pred_confidence
                    })
            anno_tkns.extend([tkn for tkn in ent])
            entity = Entity.objects.get(label=ent.cui)
            ents.append({
                'entity': entity.id,
                'value': ent.base.text,
                'start_ind': ent.base.start_char_index,
                'end_ind': ent.base.end_char_index,
                'acc': ent.context_similarity,
                'meta_annotations': meta_annotations
            })

    ents.sort(key=lambda e: e['start_ind'])
    out = {'message': message, 'entities': ents}
    return Response(out)


@api_view(http_method_names=['GET'])
def download_annos(request):
    user = request.user
    if not user.is_superuser:
        return HttpResponseBadRequest('User is not super user, and not allowed to download project outputs')

    p_ids = str(request.GET['project_ids']).split(',')
    with_text_flag = request.GET.get('with_text', False)

    if p_ids is None or len(p_ids) == 0:
        return HttpResponseBadRequest('No projects to download annotations')

    projects = ProjectAnnotateEntities.objects.filter(id__in=p_ids)

    with_doc_name = request.GET.get('with_doc_name', False)
    out = download_projects_with_text(projects) if with_text_flag else \
        download_projects_without_text(projects, with_doc_name)
    return out


@api_view(http_method_names=['GET'])
def behind_reverse_proxy(_):
    return Response(bool(int(os.environ.get('BEHIND_RP', False))))


@api_view(http_method_names=['GET'])
def version(_):
    return Response(os.environ.get('MCT_VERSION', ':latest'))


@api_view(http_method_names=['GET'])
def concept_search_index_available(request):
    cdb_ids = request.GET.get('cdbs', '').split(',')
    cdb_ids = [c for c in cdb_ids if len(c)]
    try:
        return collections_available(cdb_ids)
    except Exception as e:
        logger.error("Failed to search for concept_search_index. Solr Search Service not available", exc_info=e)
        return HttpResponseServerError("Solr Search Service not available check the service is up, running "
                                       "and configured correctly.")


@api_view(http_method_names=['GET'])
def search_solr(request):
    query = request.GET.get('search')
    cdbs = request.GET.get('cdbs').split(',')
    return search_collection(cdbs, query)


@api_view(http_method_names=['POST'])
def upload_deployment(request):
    deployment_export = request.data
    deployment_upload = deployment_export['exported_projects']
    cdb_id = deployment_export.get('cdb_id', None)
    vocab_id = deployment_export.get('vocab_id', None)
    modelpack_id = deployment_export.get('modelpack_id', None)
    project_name_suffix = deployment_export.get('project_name_suffix', ' IMPORTED')
    set_validated_docs = deployment_export.get('set_validated_docs', False)
    cdb_search_filter_id = deployment_export.get('cdb_search_filter', None)
    members = deployment_export.get('members', None)
    import_project_name_suffix = deployment_export.get('import_project_name_suffix', ' IMPORTED')

    if all(x is None for x in [cdb_id, vocab_id, modelpack_id]):
        return Response("No cdb, vocab, or modelpack provided", 400)

    try:
        upload_projects_export(deployment_upload,
                                cdb_id,
                                vocab_id,
                                modelpack_id,
                                project_name_suffix,
                                cdb_search_filter_id,
                                members,
                                import_project_name_suffix,
                                set_validated_docs)
        return Response("successfully uploaded", 200)
    except Exception as e:
        logger.error(f"Failed to upload projects export: {e}", exc_info=e)
        return Response(f"Failed to upload projects export: {e}", 500)


@api_view(http_method_names=['GET', 'DELETE'])
def cache_project_model(request, project_id):
    try:
        project = ProjectAnnotateEntities.objects.get(id=project_id)
        is_loaded = is_model_loaded(project)
        if request.method == 'GET':
            if not is_loaded:
                get_medcat(project)
            return Response('success', 200)
        elif request.method == 'DELETE':
            if is_loaded:
                clear_cached_medcat(project)
            return Response('success', 200)
        else:
            return Response(f'Invalid method', 404)
    except ProjectAnnotateEntities.DoesNotExist:
        return Response(f'Project with id:{project_id} does not exist', 404)
    except Exception as e:
        return Response({'message': f'{str(e)}'}, 500)


@api_view(http_method_names=['GET', 'DELETE'])
def cache_modelpack(request, modelpack_id: int):
    try:
        if request.method == 'GET':
            if not is_model_pack_loaded(modelpack_id):
                get_medcat_from_model_pack_id(modelpack_id)
            return Response('success', 200)
        elif request.method == 'DELETE':
            clear_cached_medcat_by_model_pack_id(modelpack_id)
            return Response('success', 200)
        else:
            return Response(f'Invalid method', 404)
    except ModelPack.DoesNotExist:
        return Response(f'ModelPack with id:{modelpack_id} does not exist', 404)
    except Exception as e:
        return Response({'message': f'{str(e)}'}, 500)



@api_view(http_method_names=['GET'])
def model_loaded(_):
    models_loaded = {}
    for p in ProjectAnnotateEntities.objects.all():
        models_loaded[p.id] = is_model_loaded(p)

    return Response({'model_states': models_loaded})


@api_view(http_method_names=['GET', 'POST'])
def metrics_jobs(request):
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    if request.method == 'GET':
        running_metrics_tasks_qs = Task.objects.filter(queue='metrics')
        completed_metrics_tasks = CompletedTask.objects.filter(queue='metrics')

        def serialize_task(task, state):
            return {
                'report_id': task.id,
                'report_name_generated': task.verbose_name,
                'projects': task.verbose_name.split('-')[1].split('_'),
                'created_user': task.creator.username,
                'create_time': task.run_at.strftime(dt_fmt),
                'error_msg': '\n'.join(task.last_error.split('\n')[-2:]),
                'status': state,
            }
        running_reports = [serialize_task(t, 'running') for t in running_metrics_tasks_qs]
        for r, t in zip(running_reports, running_metrics_tasks_qs):
            if t.locked_by is None and t.locked_by_pid_running() is None:
                r['status'] = 'pending'

        comp_reports = [serialize_task(t, 'complete') for t in completed_metrics_tasks]
        for comp_task, comp_rep in zip(completed_metrics_tasks, comp_reports):
            if comp_task.has_error():
                comp_rep['status'] = 'Failed'
            pm_obj = ProjectMetrics.objects.filter(report_name_generated=comp_task.verbose_name).first()
            if pm_obj is not None and pm_obj.report_name is not None:
                comp_rep['report_name'] = pm_obj.report_name
        reports = running_reports + comp_reports
        return Response({'reports': reports})
    elif request.method == 'POST':
        now = timezone.now()
        user = request.user
        p_ids = request.data.get('projectIds').split(',')
        projects = ProjectAnnotateEntities.objects.filter(id__in=p_ids)

        # provide warning of inconsistent models used or for models that are not loaded.
        p_cdbs = set(p.concept_db for p in projects)
        if len(p_cdbs) > 1:
            logger.warning('Inconsistent CDBs used in the generation of metrics - should use the same CDB for '
                           f'consistent results - found {[cdb.name for cdb in p_cdbs]} - metrics will only use the first'
                           f' CDB {projects[0].concept_db.name}')

        report_name = f'metrics-{"_".join(p_ids)}-{now.strftime(dt_fmt)}'
        submitted_job = calculate_metrics([p.id for p in projects],
                                          verbose_name=report_name,
                                          creator=user,
                                          report_name=report_name)
        return Response({'metrics_job_id': submitted_job.id, 'metrics_job_name': report_name})


@api_view(http_method_names=['DELETE'])
def remove_metrics_job(request, report_id: int):
    running_metrics_tasks_qs = {t.id: t for t in Task.objects.filter(queue='metrics')}
    completed_metrics_tasks = {t.id: t for t in CompletedTask.objects.filter(queue='metrics')}
    if report_id in running_metrics_tasks_qs:
        # remove completed task and associated report
        task = running_metrics_tasks_qs[report_id]
        if task.locked_by and task.locked_by_pid_running():
            logger.info('Will not kill running process - report ID: %s', report_id)
            return Response(503, 'Unable to remove a running metrics report job. Please wait until it '
                                 'completes then remove.')
        else:
            logger.info('Metrics job deleted - report ID: %s', report_id)
    elif report_id in completed_metrics_tasks:
        task = completed_metrics_tasks[report_id]
        try:
            pm = ProjectMetrics.objects.filter(report_name_generated=task.verbose_name).first()
            if os.path.isfile(pm.report.path):
                os.remove(pm.report.path)
            pm.delete()
        except Exception as e:
            pass
        task.delete()
        logger.info('Completed metrics job deleted - report ID: %s', report_id)
        return Response('task / report deleted', 200)


@api_view(http_method_names=['GET', 'PUT'])
def view_metrics(request, report_id):
    if request.method == 'GET':
        running_pending_report = Task.objects.filter(id=report_id, queue='metrics').first()
        completed_report = CompletedTask.objects.filter(id=report_id, queue='metrics').first()
        if running_pending_report is None and completed_report is None:
            HttpResponseBadRequest(f'Cannot find report_id:{report_id} in either pending, running or complete report lists. ')
        elif running_pending_report is not None:
            HttpResponseBadRequest(f'Cannot view a running or pending metrics report with id:{report_id}')
        pm_obj = ProjectMetrics.objects.filter(report_name_generated=completed_report.verbose_name).first()
        out = {
            'results': {
                'report_name': pm_obj.report_name,
                'report_name_generated': pm_obj.report_name_generated,
                **json.load(open(pm_obj.report.path))
            }
        }
        return Response(out)
    elif request.method == 'PUT':
        completed_report = CompletedTask.objects.filter(id=report_id, queue='metrics').first()
        pm_obj = ProjectMetrics.objects.filter(report_name_generated=completed_report.verbose_name).first()
        pm_obj.report_name = request.data.get('report_name')
        pm_obj.save()
        return Response(200)


@api_view(http_method_names=['GET'])
def cdb_cui_children(request, cdb_id):
    parent_cui = request.GET.get('parent_cui')
    cdb = get_cached_cdb(cdb_id, CDB_MAP)

    # root SNOMED CT code: 138875005
    # root UMLS code: CUI:

    if cdb.addl_info.get('pt2ch') is None:
        return HttpResponseBadRequest('Requested MedCAT CDB model does not include parent2child metadata to'
                                      ' explore a concept hierarchy')

    # currently assumes this is using the SNOMED CT terminology
    try:
        root_term = {'cui': '138875005', 'pretty_name': cdb.cui2info['138875005']['preferred_name']}
        if parent_cui is None:
            return Response({'results': [root_term]})
        else:
            child_concepts = [{'cui': cui, 'pretty_name': cdb.cui2info[cui]['preferred_name']}
                              for cui in cdb.addl_info.get('pt2ch')[parent_cui]]
            return Response({'results': child_concepts})
    except KeyError:
        return Response({'results': []})


@api_view(http_method_names=['GET'])
def cdb_concept_path(request):
    cdb_id = int(request.GET.get('cdb_id'))
    cdb = get_cached_cdb(cdb_id, CDB_MAP)
    if not cdb.addl_info.get('ch2pt'):
        cdb.addl_info['ch2pt'] = ch2pt_from_pt2ch(cdb)
    cui = request.GET.get('cui')
    # Again only SNOMED CT is supported
    # 'cui': '138875005',
    result = snomed_ct_concept_path(cui, cdb)
    return Response({'results': result})


@api_view(http_method_names=['POST'])
def generate_concept_filter_flat_json(request):
    cuis = request.data.get('cuis')
    cdb_id = request.data.get('cdb_id')
    excluded_nodes = request.data.get('excluded_nodes', [])
    if cuis is not None and cdb_id is not None:
        cdb = get_cached_cdb(cdb_id, CDB_MAP)
        # get all children from 'parent' concepts above.
        final_filter = []
        for cui in cuis:
            ch_nodes = get_all_ch(cui, cdb)
            final_filter += [n for n in ch_nodes if n not in excluded_nodes]
        final_filter = {cui:1 for cui in final_filter}.keys()
        filter_json = json.dumps(final_filter)
        response = HttpResponse(filter_json, content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=filter.json'
        return response
    return HttpResponseBadRequest('Missing either cuis or cdb_id param. Cannot generate filter.')


@api_view(http_method_names=['POST'])
def generate_concept_filter(request):
    cuis = request.data.get('cuis')
    cdb_id = request.data.get('cdb_id')
    if cuis is not None and cdb_id is not None:
        cdb = get_cached_cdb(cdb_id, CDB_MAP)
        # get all children from 'parent' concepts above.
        final_filter = {}
        for cui in cuis:
            final_filter[cui] = [{'cui': c, 'pretty_name': cdb.cui2info[cui]['preferred_name']} for c in get_all_ch(cui, cdb)
                                 if c in cdb.cui2info[cui]['preferred_name'] and c != cui]
        resp = {'filter_len': sum(len(f) for f in final_filter.values()) + len(final_filter.keys())}
        if resp['filter_len'] < 10000:
            # only send across concept filters that are small enough to render
            resp['filter'] = final_filter
        return Response(resp)
    return HttpResponseBadRequest('Missing either cuis or cdb_id param. Cannot generate filter.')


@api_view(http_method_names=['POST'])
def cuis_to_concepts(request):
    cuis = request.data.get('cuis')
    cdb_id = request.data.get('cdb_id')
    if cdb_id is not None:
        if cuis is not None:
            cdb = get_cached_cdb(cdb_id, CDB_MAP)
            concept_list = [{'cui': cui, 'name': cdb.cui2info[cui]['preferred_name']} for cui in cuis]
            resp = {'concept_list': concept_list}
            return Response(resp)
        else:
            cdb = get_cached_cdb(cdb_id, CDB_MAP)
            concept_list = [{'cui': cui, 'name': cdb.cui2info[cui]['preferred_name']} for cui in cdb.cui2info.keys()]
            resp = {'concept_list': concept_list}
            return Response(resp)
    return HttpResponseBadRequest('Missing either cuis or cdb_id param. Cannot produce concept list.')


@api_view(http_method_names=['GET'])
def project_progress(request):
    if request.GET.get('projects') is None:
        return HttpResponseBadRequest('Cannot get progress for empty projects')

    projects = [int(p) for p in request.GET.get('projects', []).split(',')]

    projects2datasets = {p.id: (p, p.dataset) for p in [ProjectAnnotateEntities.objects.filter(id=p_id).first()
                                                        for p_id in projects]}

    out = {}
    ds_doc_counts = {}
    for p, (proj, ds) in projects2datasets.items():
        val_docs = proj.validated_documents.count()
        ds_doc_count = ds_doc_counts.get(ds.id)
        if ds_doc_count is None:
            ds_doc_count = Document.objects.filter(dataset=ds).count()
            ds_doc_counts[ds.id] = ds_doc_count
        out[p] = {'validated_count': val_docs, 'dataset_count': ds_doc_count}

    return Response(out)


@api_view(http_method_names=['GET'])
@permission_classes([permissions.IsAuthenticated])
def project_admin_projects(request):
    """
    Get all projects where the user is a project admin.
    """
    user = request.user
    projects = ProjectAnnotateEntities.objects.filter(members=user.id)

    # Also include projects where user is admin of the project's group
    group_admin_projects = ProjectAnnotateEntities.objects.filter(
        group__administrators=user.id
    )
    projects = (projects | group_admin_projects).distinct()

    serializer = ProjectAnnotateEntitiesSerializer(projects, many=True)
    return Response(serializer.data)


@api_view(http_method_names=['GET', 'PUT', 'DELETE'])
@permission_classes([permissions.IsAuthenticated])
def project_admin_detail(request, project_id):
    """
    Get, update, or delete a project (only if user is project admin).
    """
    try:
        project = ProjectAnnotateEntities.objects.get(id=project_id)
    except ProjectAnnotateEntities.DoesNotExist:
        return Response({'error': 'Project not found'}, status=404)

    # Check if user is project admin
    from .permissions import is_project_admin
    if not is_project_admin(request.user, project):
        return Response({'error': 'You do not have permission to access this project'}, status=403)

    if request.method == 'GET':
        serializer = ProjectAnnotateEntitiesSerializer(project)
        return Response(serializer.data)

    elif request.method == 'PUT':
        # Handle both JSON and FormData
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)

        # Extract many-to-many fields - handle both JSON (list) and FormData (getlist)
        cdb_search_filter_ids = []
        try:
            cdb_search_filter_ids = [int(x) for x in request.data['cdb_search_filter'] if x]
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing cdb_search_filter: {e}")
            cdb_search_filter_ids = []

        members_ids = []
        try:
            members_ids = [int(x) for x in request.data['members'] if x]
        except (ValueError, TypeError) as e:
            logger.warning(f"Error parsing members: {e}")
            members_ids = []

        # Set many-to-many fields to the extracted IDs (or empty list)
        # This satisfies serializer validation, then we'll set them properly after save
        data['members'] = members_ids if members_ids else []
        data['cdb_search_filter'] = cdb_search_filter_ids if cdb_search_filter_ids else []

        # Convert string booleans to actual booleans
        boolean_fields = ['project_locked', 'annotation_classification', 'require_entity_validation',
                         'train_model_on_submit', 'add_new_entities', 'restrict_concept_lookup',
                         'terminate_available', 'irrelevant_available', 'enable_entity_annotation_comments',
                         'use_model_service']
        for field in boolean_fields:
            if field in data:
                if isinstance(data[field], str):
                    data[field] = data[field].lower() in ('true', '1', 'yes', 'on')

        serializer = ProjectAnnotateEntitiesSerializer(project, data=data, partial=True)
        if serializer.is_valid():
            try:
                project = serializer.save()
                # Handle many-to-many fields manually after saving
                project.cdb_search_filter.set(cdb_search_filter_ids)
                project.members.set(members_ids)
                return Response(ProjectAnnotateEntitiesSerializer(project).data)
            except Exception as e:
                logger.error(f"Error saving project {project_id}: {e}", exc_info=e)
                return Response({'error': f'Failed to save project'}, status=400)
        else:
            logger.warning(f"Validation errors for project {project_id}: {serializer.errors}")
            return Response(serializer.errors, status=400)

    elif request.method == 'DELETE':
        project.delete()
        return Response({'message': 'Project deleted successfully'}, status=200)


@api_view(http_method_names=['POST'])
@permission_classes([permissions.IsAuthenticated])
def project_admin_create(request):
    """
    Create a new project (user must be authenticated).
    """
    # Handle both JSON and FormData
    # Extract many-to-many fields - handle both JSON (list) and FormData (getlist)
    cdb_search_filter_ids = []
    try:
        if isinstance(request.data.get('cdb_search_filter'), list):
            # JSON request - already a list
            cdb_search_filter_ids = [int(x) for x in request.data['cdb_search_filter'] if x]
        elif hasattr(request.data, 'getlist'):
            # FormData request - use getlist()
            cdb_filter_list = request.data.getlist('cdb_search_filter')
            if cdb_filter_list:
                cdb_search_filter_ids = [int(x) for x in cdb_filter_list if x and str(x).strip()]
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing cdb_search_filter: {e}")
        cdb_search_filter_ids = []

    members_ids = []
    try:
        if isinstance(request.data.get('members'), list):
            # JSON request - already a list
            members_ids = [int(x) for x in request.data['members'] if x]
        elif hasattr(request.data, 'getlist'):
            # FormData request - use getlist()
            members_list = request.data.getlist('members')
            if members_list:
                members_ids = [int(x) for x in members_list if x and str(x).strip()]
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing members: {e}")
        members_ids = []

    # Build data dict - use the actual member IDs we extracted, or empty list if none
    # The serializer will validate with these, then we'll set them properly after save
    if hasattr(request.data, 'copy'):
        data = request.data.copy()
    else:
        data = dict(request.data)

    # Set many-to-many fields to the extracted IDs (or empty list)
    # This satisfies serializer validation, then we'll set them properly after save
    data['members'] = members_ids if members_ids else []
    data['cdb_search_filter'] = cdb_search_filter_ids if cdb_search_filter_ids else []

    serializer = ProjectAnnotateEntitiesSerializer(data=data)
    if serializer.is_valid():
        project = serializer.save()
        # Handle many-to-many fields manually after saving
        project.cdb_search_filter.set(cdb_search_filter_ids)
        project.members.set(members_ids)
        # Add the creator as a member if not already included
        if request.user not in project.members.all():
            project.members.add(request.user)
        return Response(ProjectAnnotateEntitiesSerializer(project).data, status=201)
    return Response(serializer.errors, status=400)


@api_view(http_method_names=['POST'])
@permission_classes([permissions.IsAuthenticated])
def project_admin_clone(request, project_id):
    """
    Clone a project (user must be authenticated and have permission).
    """
    import copy
    try:
        project = ProjectAnnotateEntities.objects.get(id=project_id)
    except ProjectAnnotateEntities.DoesNotExist:
        return Response({'error': 'Project not found'}, status=404)

    # Check if user is project admin
    from .permissions import is_project_admin
    if not is_project_admin(request.user, project):
        return Response({'error': 'You do not have permission to clone this project'}, status=403)

    try:
        # Get custom name from request, or use default
        custom_name = request.data.get('name', None) if hasattr(request.data, 'get') else None
        if not custom_name:
            custom_name = f'{project.name} (Clone)'

        # Create a copy of the project
        project_copy = copy.copy(project)
        project_copy.id = None
        project_copy.pk = None
        project_copy.name = custom_name
        project_copy.save()

        # Copy many-to-many fields
        for m in project.members.all():
            project_copy.members.add(m)
        for c in project.cdb_search_filter.all():
            project_copy.cdb_search_filter.add(c)
        for t in project.tasks.all():
            project_copy.tasks.add(t)

        project_copy.save()
        serializer = ProjectAnnotateEntitiesSerializer(project_copy)
        return Response(serializer.data, status=201)
    except Exception as e:
        logger.error(f"Failed to clone project: {e}", exc_info=e)
        return Response({'error': f'Failed to clone project:'}, status=500)


@api_view(http_method_names=['POST'])
@permission_classes([permissions.IsAuthenticated])
def project_admin_reset(request, project_id):
    """
    Reset a project (clear all annotations) - only if user is project admin.
    This is equivalent to the reset_project admin action.
    """
    try:
        project = ProjectAnnotateEntities.objects.get(id=project_id)
    except ProjectAnnotateEntities.DoesNotExist:
        return Response({'error': 'Project not found'}, status=404)

    # Check if user is project admin
    from .permissions import is_project_admin
    if not is_project_admin(request.user, project):
        return Response({'error': 'You do not have permission to reset this project'}, status=403)

    # Remove all annotations and cascade to meta anns
    AnnotatedEntity.objects.filter(project=project).delete()

    # Clear validated_documents and prepared_documents
    project.validated_documents.clear()
    project.prepared_documents.clear()

    return Response({'message': 'Project reset successfully'}, status=200)
