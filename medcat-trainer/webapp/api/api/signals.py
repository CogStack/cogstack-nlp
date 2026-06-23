import json
import logging
import os
import shutil

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models.fields.files import FileField
from django.db.models.signals import post_save, post_delete, pre_save, m2m_changed, pre_delete
from django.dispatch import receiver

from api.data_utils import dataset_from_file, delete_orphan_docs, upload_projects_export
from api.extensions import (
    annotation_created,
    annotation_deleted,
    annotation_updated,
    dispatch,
    project_group_created,
    project_group_updated,
)
from api.models import (
    AnnotatedEntity,
    Dataset,
    ExportedProject,
    MetaTask,
    ModelPack,
    ProjectAnnotateEntities,
    ProjectAnnotateEntitiesFields,
    ProjectFields,
    ProjectGroup,
)
from core.settings import MEDIA_ROOT


logger = logging.getLogger(__name__)


@receiver(post_save, sender=Dataset)
def save_dataset(sender, instance, **kwargs):
    dataset_from_file(instance)


@receiver(pre_save, sender=Dataset)
def pre_save_dataset(sender, instance, **kwargs):
    if instance.id:
        delete_orphan_docs(instance)
        remove_dataset_file(sender, instance, **kwargs)


@receiver(post_delete, sender=Dataset)
def remove_dataset_file(sender, instance, **kwargs):
    """
    Removes corresponding file from Dataset.original_file FileField.
    """
    if instance.original_file:
        if os.path.isfile(instance.original_file.path):
            os.remove(instance.original_file.path)


@receiver(post_save, sender=ExportedProject)
def save_exported_projects(sender, instance, **kwargs):
    if not instance.trainer_export_file.path.endswith('.json'):
        raise Exception("Please make sure the file is a .json file")
    cdb = instance.cdb_id
    vocab = instance.vocab_id
    modelpack = instance.modelpack_id

    cdb = None if cdb is None else cdb.id
    vocab = None if vocab is None else vocab.id
    modelpack = None if modelpack is None else modelpack.id

    upload_projects_export(
        json.load(open(instance.trainer_export_file.path)),
        cdb_id=cdb,
        vocab_id=vocab,
        modelpack_id=modelpack)


@receiver(pre_delete, sender=ModelPack)
def remove_model_pack_meta_cat_models(sender, instance, **kwargs):
    if len(instance.meta_cats.all()) > 0:
        for m_c in instance.meta_cats.all():
            m_c.delete(using=None, keep_parents=False)


@receiver(post_delete, sender=ModelPack)
def remove_model_pack_assets(sender, instance, **kwargs):
    try:
        if instance.concept_db:
            instance.concept_db.delete(using=None, keep_parents=False)
    except ObjectDoesNotExist:
        pass  # if a ConceptDB of a model pack is removed, this will cascade ModelPack removal.
    try:
        if instance.vocab:
            instance.vocab.delete(using=None, keep_parents=False)
    except ObjectDoesNotExist:
        pass  # if a vocab of a model pack is removed, this will cascade ModelPack removal.

    try:
        # rm the model pack unzipped dir & model pack zip
        shutil.rmtree(instance.model_pack.path.replace(".zip", ""))
        os.remove(instance.model_pack.path)
    except FileNotFoundError:
        logger.warning("Failure removing Model pack dir or zip. Not found. Likely already deleted")


def project_tasks_changed(sender, instance, action, **kwargs):
    # post_remove or post_add actions, overwrite to model_pack supplied MetaCAT tasks.
    if (action.startswith('post') and isinstance(instance, ProjectAnnotateEntitiesFields) and
            instance.model_pack is not None):
        # NOTE: This part deals with two different sources of information:
        #       1. sometimes the model pack associated with the project can have meta-cats for meta-annotations
        #       2. sometimes the project itself defines meta-tasks for the annotator to use
        #
        #       Currently the proccess here defaults to useing model-pack defined meta-tasks (if present),
        #       while allowing for the project-defined ones otherwise.

        # Find automated tasks from the model pack
        db_tasks = [
            MetaTask.objects.filter(prediction_model_id=meta_cat.id).first()
            for meta_cat in instance.model_pack.meta_cats.all()
        ]
        # Filter out None values
        automated_tasks = [t for t in db_tasks if t is not None]

        # Only overwrite if the model pack actually brought automated tasks to the table.
        # This preserves manual workflows when training from scratch.
        if automated_tasks:
            # Disconnect the signal temporarily to prevent infinite recursion loops
            m2m_changed.disconnect(project_tasks_changed, sender=ProjectAnnotateEntitiesFields.tasks.through)
            try:
                instance.tasks.set(automated_tasks)
            finally:
                # Always reconnect the signal
                m2m_changed.connect(project_tasks_changed, sender=ProjectAnnotateEntitiesFields.tasks.through)


m2m_changed.connect(project_tasks_changed, sender=ProjectAnnotateEntitiesFields.tasks.through)


# ---------------------------------------------------------------------------
# Bridges from Django ORM signals to api.extensions semantic signals.
# These are part of the stable plugin contract (api/extensions.py).
# Keep these handlers cheap and side-effect-free.
# ---------------------------------------------------------------------------

@receiver(post_save, sender=AnnotatedEntity)
def _emit_annotation_saved(sender, instance, created, **kwargs):
    sig = annotation_created if created else annotation_updated
    dispatch(
        sig,
        sender=AnnotatedEntity,
        annotation=instance,
        project=getattr(instance, 'project', None),
        document=getattr(instance, 'document', None),
        user=getattr(instance, 'user', None),
    )


@receiver(post_delete, sender=AnnotatedEntity)
def _emit_annotation_deleted(sender, instance, **kwargs):
    dispatch(
        annotation_deleted,
        sender=AnnotatedEntity,
        annotation=instance,
        project=getattr(instance, 'project', None),
        document=getattr(instance, 'document', None),
    )


@receiver(post_save, sender=ProjectGroup)
def _emit_project_group_saved(sender, instance, created, **kwargs):
    sig = project_group_created if created else project_group_updated
    dispatch(sig, sender=ProjectGroup, project_group=instance)
