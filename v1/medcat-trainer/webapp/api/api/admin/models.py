from django.contrib import admin
from django.contrib.auth.models import User
from django.forms import fields
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from .actions import *
from ..models import *

_PROJECT_ANNO_ENTS_SETTINGS_FIELD_ORDER = (
    'concept_db', 'vocab', 'model_pack', 'cdb_search_filter', 'deid_model_annotation', 'require_entity_validation', 'train_model_on_submit',
    'add_new_entities', 'restrict_concept_lookup', 'terminate_available', 'irrelevant_available',
    'enable_entity_annotation_comments', 'tasks', 'relations'
)

_PROJECT_FIELDS_ORDER = (
    'cuis', 'cuis_file', 'annotation_classification', 'project_locked', 'project_status'
)


class ReportErrorModelAdminMixin:
    """Mixin to catch all errors in the Django Admin and map them to user-visible errors."""
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except Exception as e:
            self.message_user(request, f'Error with previous action: {e}', level=logging.ERROR)
            return HttpResponseRedirect(request.path)



dataset_document_counts.short_description = 'Document Count'


class DatasetAdmin(ReportErrorModelAdminMixin, admin.ModelAdmin):
    model = Dataset
    form = DatasetForm
    list_display = ['name', 'create_time', 'description', dataset_document_counts]


class ProjectAnnotateEntitiesAdmin(admin.ModelAdmin):
    model = ProjectAnnotateEntities
    actions = [download, download_without_text, download_without_text_with_doc_names, reset_project, clone_projects]
    list_filter = ('members', 'project_status', 'project_locked', 'annotation_classification')
    list_display = ['name']
    fields = (('group', 'name', 'description', 'annotation_guideline_link', 'members',
               'dataset', 'validated_documents', 'prepared_documents') +
              _PROJECT_FIELDS_ORDER +
              _PROJECT_ANNO_ENTS_SETTINGS_FIELD_ORDER)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'concept_db':
            kwargs['queryset'] = ConceptDB.objects.filter(use_for_training=True)
        return super(ProjectAnnotateEntitiesAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'cdb_search_filter':
            kwargs['queryset'] = ConceptDB.objects.all()
        if db_field.name in ('validated_documents', 'prepared_documents'):
            project_id = request.path.replace('/admin/api/projectannotateentities/', '').split('/')[0]
            try:
                proj = ProjectAnnotateEntities.objects.get(id=int(project_id))
                kwargs['queryset'] = Document.objects.filter(dataset=proj.dataset.id)
            except ValueError:  # a blank project has no validated_documents
                kwargs['queryset'] = Document.objects.none()
        return super(ProjectAnnotateEntitiesAdmin, self).formfield_for_manytomany(db_field, request, **kwargs)


class ProjectGroupAdmin(admin.ModelAdmin):
    model = ProjectGroup
    list_display = ('name', 'description')
    fields = (('name', 'description', 'create_associated_projects', 'annotation_guideline_link', 'administrators',
               'annotators', 'dataset') +
              _PROJECT_FIELDS_ORDER + _PROJECT_ANNO_ENTS_SETTINGS_FIELD_ORDER)

    class Meta:
        model = ProjectGroup

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        return form

    def _set_proj_from_group(self, proj: ProjectAnnotateEntities, group: ProjectGroup,
                             annotator: settings.AUTH_USER_MODEL, admins: List[User],
                             cdb_search_filters: List[ConceptDB], tasks: List[MetaTask], relations: List[Relation]):
        proj.group = group
        proj.name = f'{group.name} - {str(annotator)}'
        proj.description = group.description
        proj.dataset = group.dataset
        proj.annotation_guideline_link = group.annotation_guideline_link
        proj.create_time = group.create_time
        proj.cuis = group.cuis
        proj.cuis_file = group.cuis_file
        proj.annotation_classification = group.annotation_classification
        proj.project_locked = group.project_locked
        proj.project_status = group.project_status
        proj.concept_db = group.concept_db
        proj.vocab = group.vocab
        proj.require_entity_validation = group.require_entity_validation
        proj.train_model_on_submit = group.train_model_on_submit
        proj.add_new_entities = group.add_new_entities
        proj.restrict_concept_lookup = group.restrict_concept_lookup
        proj.terminate_available = group.terminate_available
        proj.irrelevant_available = group.irrelevant_available
        proj.enable_entity_annotation_comments = group.enable_entity_annotation_comments

        # project specific attrs / m2m fields
        proj.save()
        proj.cdb_search_filter.set(cdb_search_filters)
        proj.members.set(admins)
        proj.members.add(annotator)
        proj.tasks.set(tasks)
        proj.relations.set(relations)
        proj.save()
        return proj

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        annotators = [get_object_or_404(User, pk=id) for id in request.POST.getlist('annotators')]
        admins = [get_object_or_404(User, pk=id) for id in request.POST.getlist('administrators')]
        cdb_search_filters = [get_object_or_404(ConceptDB, pk=id) for id in request.POST.getlist('cdb_search_filter')]
        tasks = [get_object_or_404(MetaTask, pk=id) for id in request.POST.getlist('tasks')]
        relations = [get_object_or_404(Relation, pk=id) for id in request.POST.getlist('relations')]

        # create the underlying ProjectAnnotateEntities models or edit them
        if obj.create_associated_projects:
            if not change:
                # new ProjectGroup being created
                for annotator in annotators:
                    self._set_proj_from_group(ProjectAnnotateEntities(), obj, annotator,
                                              admins, cdb_search_filters, tasks, relations)
            else:
                # applying these settings to all previously created projects within this group
                projs = ProjectAnnotateEntities.objects.filter(group=obj)
                if len(projs) == len(obj.annotators.all()):
                    for proj, annotator in zip(projs, obj.annotators.all()):
                       self._set_proj_from_group(proj, obj, annotator, admins, cdb_search_filters,
                                                 tasks, relations)
                else:
                    raise ValueError("Attempting to update a ProjectGroup but one or more "
                                     "of underlying ProjectAnnotateEntities have been removed / or added "
                                     "manually. To fix, go into each project separately, or create new projects "
                                     "and link to the ProjectGroup within ProjectAnnotateEntities page.")


class AnnotatedEntityAdmin(admin.ModelAdmin):
    list_display = ('user', 'project', 'entity', 'value', 'deleted', 'validated')
    list_filter = ('user', 'project', 'deleted', 'validated')
    model = AnnotatedEntity


class ConceptDBAdmin(admin.ModelAdmin):
    model = ConceptDB
    actions = [import_concepts, delete_indexed_concepts, reset_cdb_filters]
    list_display = ('name', 'use_for_training', 'create_time', 'last_modified', 'last_modified_by')
    fields = ('name', 'cdb_file', 'use_for_training')

    def save_model(self, request, obj, form, change):
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


class VocabularyAdmin(admin.ModelAdmin):
    model = Vocabulary
    list_display = ('name', 'create_time', 'last_modified', 'last_modified_by')
    fields = ('name', 'vocab_file', 'create_time', 'last_modified', 'last_modified_by')
    
    def save_model(self, request, obj, form, change):
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


class ModelPackAdmin(admin.ModelAdmin):
    model = ModelPack
    list_display = ('name', 'model_pack', 'concept_db', 'vocab', 'metacats')
    fields = ['name', 'model_pack']

    def metacats(self, obj):
        return ", ".join(str(m_c) for m_c in obj.meta_cats.all())
    
    def save_model(self, request, obj, form, change):
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


class MetaCATModelAdmin(admin.ModelAdmin):
    model = MetaCATModel
    list_display = ('name', 'meta_cat_dir')


class MetaAnnotationAdmin(admin.ModelAdmin):
    model = MetaAnnotation
    list_display = ('annotated_entity', 'meta_task', 'meta_task_value', 'acc',
                    'predicted_meta_task_value', 'validated', 'last_modified')
    list_filter = ('meta_task', 'meta_task_value', 'predicted_meta_task_value', 'validated')


class DocumentAdmin(admin.ModelAdmin):
    model = Document
    actions = [remove_all_documents]
    list_filter = ('dataset',)
    list_display = ['name', 'create_time', 'dataset', 'last_modified']


class ExportedProjectAdmin(admin.ModelAdmin):
    model = ExportedProject


class ProjectMetricsAdmin(admin.ModelAdmin):
    model = ProjectMetrics
    list_display = ('report_name', 'report_name_generated')
    list_filter = ['projects']


