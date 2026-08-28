"""Helpers for creating annotation projects from a ProjectGroup.

Django admin and the REST serializer both use these so a new group with
``create_associated_projects=True`` yields one ProjectAnnotateEntities per annotator.
"""
from typing import Iterable, List, Optional, Sequence

from django.contrib.auth.models import User

from .models import ConceptDB, MetaTask, ProjectAnnotateEntities, ProjectGroup, Relation

_PROJECT_COPY_FIELDS = (
    'description',
    'dataset',
    'annotation_guideline_link',
    'create_time',
    'cuis',
    'cuis_file',
    'annotation_classification',
    'project_locked',
    'project_status',
    'concept_db',
    'vocab',
    'model_pack',
    'deid_model_annotation',
    'use_model_service',
    'model_service_url',
    'require_entity_validation',
    'train_model_on_submit',
    'add_new_entities',
    'restrict_concept_lookup',
    'terminate_available',
    'irrelevant_available',
    'enable_entity_annotation_comments',
)

GROUP_PROJECTS_OUT_OF_SYNC_MESSAGE = (
    "Attempting to update a ProjectGroup but one or more "
    "of underlying ProjectAnnotateEntities have been removed / or added "
    "manually. To fix, go into each project separately, or create new projects "
    "and link to the ProjectGroup within ProjectAnnotateEntities page."
)


def populate_project_from_group(
    proj: ProjectAnnotateEntities,
    group: ProjectGroup,
    annotator: User,
    admins: Sequence[User],
    cdb_search_filters: Sequence[ConceptDB],
    tasks: Sequence[MetaTask],
    relations: Sequence[Relation],
) -> ProjectAnnotateEntities:
    """Copy group settings onto a ProjectAnnotateEntities and assign members."""
    proj.group = group
    proj.name = f'{group.name} - {str(annotator)}'
    for field in _PROJECT_COPY_FIELDS:
        setattr(proj, field, getattr(group, field))

    proj.save()
    proj.cdb_search_filter.set(cdb_search_filters)
    proj.members.set(admins)
    proj.members.add(annotator)
    proj.tasks.set(tasks)
    proj.relations.set(relations)
    proj.save()
    return proj


def create_projects_for_group(
    group: ProjectGroup,
    annotators: Optional[Iterable[User]] = None,
    admins: Optional[Iterable[User]] = None,
    cdb_search_filters: Optional[Iterable[ConceptDB]] = None,
    tasks: Optional[Iterable[MetaTask]] = None,
    relations: Optional[Iterable[Relation]] = None,
) -> List[ProjectAnnotateEntities]:
    """Create one annotation project per annotator from a newly saved group."""
    annotators = list(annotators if annotators is not None else group.annotators.all())
    admins = list(admins if admins is not None else group.administrators.all())
    cdb_search_filters = list(
        cdb_search_filters if cdb_search_filters is not None else group.cdb_search_filter.all()
    )
    tasks = list(tasks if tasks is not None else group.tasks.all())
    relations = list(relations if relations is not None else group.relations.all())

    created = []
    for annotator in annotators:
        created.append(
            populate_project_from_group(
                ProjectAnnotateEntities(),
                group,
                annotator,
                admins,
                cdb_search_filters,
                tasks,
                relations,
            )
        )
    return created


def update_projects_for_group(
    group: ProjectGroup,
    annotators: Sequence[User],
    admins: Sequence[User],
    cdb_search_filters: Sequence[ConceptDB],
    tasks: Sequence[MetaTask],
    relations: Sequence[Relation],
) -> List[ProjectAnnotateEntities]:
    """Re-apply group settings to existing associated projects.

    Raises ValueError if the number of associated projects does not match annotators.
    """
    projs = list(ProjectAnnotateEntities.objects.filter(group=group))
    if len(projs) != len(annotators):
        raise ValueError(GROUP_PROJECTS_OUT_OF_SYNC_MESSAGE)
    updated = []
    for proj, annotator in zip(projs, annotators):
        updated.append(
            populate_project_from_group(
                proj, group, annotator, admins, cdb_search_filters, tasks, relations
            )
        )
    return updated
