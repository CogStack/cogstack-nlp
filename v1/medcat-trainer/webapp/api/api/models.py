import logging
import os
import shutil
from zipfile import BadZipFile

import pandas as pd
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.dispatch import receiver
from django.forms import forms, ModelForm
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.meta_cat import MetaCAT
from polymorphic.models import PolymorphicModel

from core.settings import MEDIA_ROOT

STATUS_CHOICES = [
        (0, 'Not Validated'),
        (1, 'Validated'),
        ]

BOOL_CHOICES = [
        (0, 'False'),
        (1, 'True')
        ]


cdb_name_validator = RegexValidator(r'^[a-zA-Z][a-zA-Z0-9_]*$', 'a-z for first character required. Alpahanumeric and _ thereafter are allowed for CDB names')

logger = logging.getLogger(__name__)


class ModelPack(models.Model):
    name = models.TextField(help_text='', unique=True)
    model_pack = models.FileField(help_text='Model pack zip')
    concept_db = models.ForeignKey('ConceptDB', on_delete=models.CASCADE, blank=True, null=True)
    vocab = models.ForeignKey('Vocabulary', on_delete=models.CASCADE, blank=True, null=True)
    meta_cats = models.ManyToManyField('MetaCATModel', blank=True, default=None)
    create_time = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, default=None, null=True)   

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if is_new:
            super().save(*args, **kwargs)
        
        # Process the model pack
        logger.info('Loading model pack: %s', self.model_pack)
        model_pack_name = str(self.model_pack).replace(".zip", "")
        try:
            CAT.attempt_unpack(self.model_pack.path)
        except BadZipFile as exc:
            # potential for CRC-32 errors in Trainer process - ignore and still use
            logger.warning(f'Possibly corrupt cdb.dat decompressing {self.model_pack}\nFull Exception: {exc}')
        unpacked_model_pack_path = self.model_pack.path.replace('.zip', '')
        # attempt to load cdb
        try:
            CAT.load_cdb(unpacked_model_pack_path)
            concept_db = ConceptDB()
            unpacked_file_name = self.model_pack.file.name.replace('.zip', '')
            concept_db.cdb_file.name = os.path.join(unpacked_file_name, 'cdb.dat')
            concept_db.name = f'{self.name}_CDB'
            concept_db.save(skip_load=True)
            self.concept_db = concept_db
        except Exception as exc:
            raise FileNotFoundError(f'Error loading the CDB from this model pack: {self.model_pack.path}') from exc

        # Load Vocab
        vocab_path = os.path.join(unpacked_model_pack_path, "vocab.dat")
        if os.path.exists(vocab_path):
            Vocab.load(vocab_path)
            vocab = Vocabulary()
            vocab.vocab_file.name = vocab_path.replace(f'{MEDIA_ROOT}/', '')
            vocab.save(skip_load=True)
            self.vocab = vocab
        else:
            # DeID model packs do not have a vocab.dat file
            logger.warn('Error loading the Vocab from this model pack - '
                        f'if this is a DeID model pack, this is expected: {vocab_path}')

        # load MetaCATs
        try:
            metaCATmodels = []
            # should raise an error if there already is a MetaCAT model with this definition
            for meta_cat_dir, meta_cat in CAT.load_meta_cats(unpacked_model_pack_path):
                mc_model = MetaCATModel()
                mc_model.meta_cat_dir = meta_cat_dir.replace(f'{MEDIA_ROOT}/', '')
                mc_model.name = f'{meta_cat.config.general.category_name} - {meta_cat.config.model.model_name}'
                mc_model.save(unpack_load_meta_cat_dir=False)
                mc_model.get_or_create_meta_tasks_and_values(meta_cat)
                metaCATmodels.append(mc_model)
            self.meta_cats.set(metaCATmodels)  # Use set() instead of add() for atomic operation
        except Exception as exc:
            raise MedCATLoadException(f'Failure loading MetaCAT models - {unpacked_model_pack_path}') from exc
            
        # Only save if this is an update (not a new instance)
        if not is_new:
            super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ConceptDB(models.Model):
    name = models.CharField(max_length=100, default='', blank=True, validators=[cdb_name_validator], unique=True)
    cdb_file = models.FileField()
    use_for_training = models.BooleanField(default=True)
    create_time = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, default=None, null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__cdb_field_name = None

    @classmethod
    def from_db(cls, db, field_names, values):
        inst = super().from_db(db, field_names, values)
        inst.__cdb_field_name = [v for f, v in zip(field_names, values) if f == 'cdb_file'][0]
        return inst

    def save(self, *args, skip_load=False, **kwargs):
        if self.__cdb_field_name is not None and self.__cdb_field_name != self.cdb_file.name:
            raise ValidationError('Cannot change file path of existing CDB.')
        else:
            super().save(*args, **kwargs)
        # load the CDB, and raise if this fails - must be saved first so storage handler can rename path if name clashes
        if not skip_load:
            try:
                CDB.load(self.cdb_file.path)
            except Exception as exc:
                raise MedCATLoadException(f'Failed to load Concept DB from {self.cdb_file}, '
                                          f'check if this CDB file successfully loads elsewhere') from exc


    def __str__(self):
        return self.name


class Vocabulary(models.Model):
    name = models.CharField(max_length=100, default='', blank=True)
    vocab_file = models.FileField()
    create_time = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, default=None, null=True)

    def save(self, *args, skip_load=False, **kwargs):
        super().save(*args, **kwargs)

        # load the Vocab, and raise if this fails
        if not skip_load:
            try:
                Vocab.load(self.vocab_file.path)
            except Exception as exc:
                raise MedCATLoadException(f'Failed to load Vocab from {self.vocab_file}, '
                                          f'check if this Vocab file successfully loads elsewhere') from exc

    def __str__(self):
        return str(self.vocab_file.name)


class MetaCATModel(models.Model):
    name = models.CharField(max_length=100, help_text="The task name followed by the underlying model impl", unique=True)
    meta_cat_dir = models.FilePathField(help_text='The zip or dir for a MetaCAT model, not editable, '
                                                  'is set via a model pack .zip upload',
                                        allow_folders=True, editable=False)

    def get_or_create_meta_tasks_and_values(self, meta_cat: MetaCAT):
        task = meta_cat.config.general.category_name
        mt = MetaTask.objects.filter(name=task).first()
        if not mt:
            mt = MetaTask()
            mt.name = task
            mt.prediction_model = self
            mt.save()
        else:
            mt.prediction_model = self
            mt.save()

        mt_vs = []
        for meta_task_value in meta_cat.config.general.category_value2id.keys():
            mt_v = MetaTaskValue.objects.filter(name=meta_task_value).first()
            if not mt_v:
                mt_v = MetaTaskValue()
                mt_v.name = meta_task_value
                mt_v.save()
            mt_vs.append(mt_v)
        mt.values.set(mt_vs)
        self.save()

    def save(self, *args, unpack_load_meta_cat_dir=False, **kwargs):
        if unpack_load_meta_cat_dir:
            try:
                # load the meta cat model, raise if issues
                model_files = os.path.join(MEDIA_ROOT, self.meta_cat_dir)
                shutil.unpack_archive(self.meta_cat_dir, extract_dir=model_files)
                MetaCAT.load(save_dir_path=model_files)
            except Exception as exc:
                raise MedCATLoadException(f'Failed to load MetaCAT from {self.meta_cat_dir}, '
                                          f'check if this MetaCAT dir successfully loads elsewhere') from exc
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} - {str(self.meta_cat_dir)}'


class Dataset(models.Model):
    name = models.CharField(max_length=150, unique=True)
    original_file = models.FileField()
    create_time = models.DateTimeField(auto_now_add=True)
    description = models.TextField(default="", blank=True)

    def __str__(self):
        return str(self.name)


class DatasetForm(ModelForm):
    def clean(self):
        original_file = self.cleaned_data['original_file']
        if '.csv' in original_file.name:
            df = pd.read_csv(original_file.file, on_bad_lines='error')
        elif '.xlsx' in original_file.name:
            df = pd.read_excel(original_file.file)
        else:
            raise forms.ValidationError({'original_file': 'Must be either .csv or .xlsx'})
        if 'name' not in df.columns or 'text' not in df.columns:
            raise forms.ValidationError({'original_file': 'Must contain at least a "name" and "text" column'})


class Document(models.Model):
    name = models.CharField(max_length=150)
    create_time = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    text = models.TextField(default="", blank=True)
    dataset = models.ForeignKey('Dataset', on_delete=models.CASCADE)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.name} | {self.dataset.name} | {self.dataset.id}'


class ProjectFields(models.Model):
    class Meta:
        abstract = True

    PROJECT_STATUSES = [
        ("A", "Annotating"),
        ("D", "Discontinued (Fail)"),
        ("C", "Complete"),
    ]

    name = models.CharField(max_length=150, help_text='A name of the annotation project', unique=True)
    description = models.TextField(default="", blank=True, help_text='A short description of the annotations to be '
                                                                     'collected and why')
    dataset = models.ForeignKey('Dataset', on_delete=models.CASCADE, help_text='The dataset to be annotated.')
    annotation_guideline_link = models.TextField(default="", blank=True,
                                                 help_text="link to an external document (i.e. GoogleDoc, MS Sharepoint)"
                                                           "outlining a guide for annotators to follow for this project,"
                                                           "an example is available here: https://docs.google.com/document/d/1xxelBOYbyVzJ7vLlztP2q1Kw9F5Vr1pRwblgrXPS7QM/edit?usp=sharing")
    create_time = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    cuis = models.TextField(default=None, blank=True, help_text='A list of comma seperated concept unique identifiers (CUIs) to be annotated')
    cuis_file = models.FileField(null=True, blank=True,
                                 help_text='A file containing a JSON formatted list of CUI code strings, '
                                           'i.e. ["1234567","7654321"]')
    annotation_classification = models.BooleanField(default=False, help_text="If these annotations are suitable "
                                                                             "for training a general purpose model. If"
                                                                             " in doubt uncheck this.")
    meta_cat_predictions = models.BooleanField(default=False, help_text="If MetaTasks are setup on the project and "
                                                                        "there are associated MetaCATModel instances, "
                                                                        "display these predictions in the interface to "
                                                                        "be validated / corrected")
    project_locked = models.BooleanField(default=False, help_text="Locked indicates annotation collection is complete and this dataset should "
                                                                  "not be touched any further.")
    project_status = models.CharField(max_length=1, choices=PROJECT_STATUSES, default="A",
                                      help_text="The status of the annotation collection exercise")


class Project(PolymorphicModel, ProjectFields):
    members = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                     help_text='The list users that have access to this annotation project')
    group = models.ForeignKey('ProjectGroup', on_delete=models.SET_NULL, blank=True, null=True,
                              help_text='The annotation project group that this project is part of')
    validated_documents = models.ManyToManyField(Document, default=None, blank=True,
                                                 help_text='Set automatically on each doc submission')
    prepared_documents = models.ManyToManyField(Document, default=None, blank=True,
                                                help_text='Set automatically on each prep of a document',
                                                related_name='prepared_documents')

    def __str__(self):
        return str(self.name)


class Entity(models.Model):
    label = models.CharField(max_length=300, unique=True)

    def __str__(self):
        return str(self.label)


class Relation(models.Model):
    label = models.CharField(max_length=300, unique=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return str(self.label)


class EntityRelation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='entity_relation_document')
    relation = models.ForeignKey('Relation', on_delete=models.CASCADE)
    start_entity = models.ForeignKey('AnnotatedEntity', related_name='start_entity', on_delete=models.CASCADE)
    end_entity = models.ForeignKey('AnnotatedEntity', related_name='end_entity', on_delete=models.CASCADE)
    validated = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.project.last_modified = self.last_modified
        self.project.save()

    def __str__(self):
        return f'{self.start_entity} - {self.relation} - {self.end_entity}'


class AnnotatedEntity(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey('Project', on_delete=models.CASCADE)
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='annotated_entity')
    entity = models.ForeignKey('Entity', on_delete=models.CASCADE)
    value = models.CharField(max_length=1000)
    start_ind = models.IntegerField()
    end_ind = models.IntegerField()
    acc = models.FloatField()
    comment = models.TextField(null=True, blank=True)
    validated = models.BooleanField(default=False)
    correct = models.BooleanField(default=False)
    alternative = models.BooleanField(default=False)
    manually_created = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)
    killed = models.BooleanField(default=False)
    irrelevant = models.BooleanField(default=False)
    create_time = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.project.last_modified = self.last_modified
        self.project.save()

    def __str__(self):
        return str(self.entity)


class MetaTaskValue(models.Model):
    name = models.CharField(max_length=150, unique=True)
    ordering = models.PositiveSmallIntegerField(help_text="the order in which the meta task value will appear in "
                                                          "the Trainer Annotation project screen", default=0)

    class Meta:
        ordering = ['ordering', 'name']

    def __str__(self):
        return str(self.name)


class MetaTask(models.Model):
    name = models.CharField(max_length=150, unique=True)
    values = models.ManyToManyField(MetaTaskValue, related_name='values')
    default = models.ForeignKey('MetaTaskValue', null=True, blank=True, on_delete=models.SET_NULL)
    description = models.TextField(default="", blank=True)
    ordering = models.PositiveSmallIntegerField(help_text="the order in which the meta task will appear in "
                                                          "the Trainer Annotation project screen", default=0)
    prediction_model = models.ForeignKey('MetaCATModel', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ['ordering', 'name']

    def __str__(self):
        return str(self.name)


class ProjectAnnotateEntitiesFields(models.Model):
    """
    Abstract class for all model fields for ProjectAnnotateEntities models.
    """
    class Meta:
        abstract = True

    concept_db = models.ForeignKey('ConceptDB', on_delete=models.SET_NULL, blank=True, null=True,
                                   help_text='The MedCAT CDB used to annotate / validate')
    vocab = models.ForeignKey('Vocabulary', on_delete=models.SET_NULL, blank=True, null=True,
                              help_text='The MedCAT Vocab used to annotate / validate')
    model_pack = models.ForeignKey('ModelPack', on_delete=models.SET_NULL, help_text="A MedCAT model pack. This will raise an exception if "
                                                                                     "both the CDB and Vocab and ModelPack fields are set",
                                   default=None, null=True, blank=True)
    cdb_search_filter = models.ManyToManyField('ConceptDB', blank=True, default=None,
                                               help_text='The CDB that will be used for concept lookup. '
                                                         'This specific CDB should have been "imported" '
                                                         'via the CDB admin screen',
                                               related_name='concept_source')
    require_entity_validation = models.BooleanField(default=True,
                                                    help_text='Entities appear grey and are required to be validated '
                                                              'before submission')
    train_model_on_submit = models.BooleanField(default=True, help_text='Active learning - configured CDB is trained '
                                                                        'on each submit')
    add_new_entities = models.BooleanField(default=False,
                                           help_text='Allow the creation of new terms to be added to the CDB')
    restrict_concept_lookup = models.BooleanField(default=False,
                                                  help_text='Users can only search for concept terms from the '
                                                            'list configured for the project, i.e. either from '
                                                            'the cuis or cuis_file lists. Checking this when both'
                                                            'cuis and cuis_file are empty does nothing. If "add new '
                                                            'entities" is available & added, and cuis or cuis_file'
                                                            'is non-empty the new CUI will be added.')
    terminate_available = models.BooleanField(default=True,
                                              help_text='Enable the option to terminate concepts.')
    irrelevant_available = models.BooleanField(default=False,
                                               help_text='Enable the option to add the irrelevant button.')
    deid_model_annotation = models.BooleanField(default=False,
                                                help_text='To indicate that this project is to collect De-ID Model annotations')
    enable_entity_annotation_comments = models.BooleanField(default=False,
                                                            help_text="Enable to allow annotators to leave comments"
                                                                      " for each annotation")
    tasks = models.ManyToManyField('MetaTask', blank=True, default=None,
                                   help_text='The set of MetaAnnotation tasks configured for this project, '
                                             'this will default to the set of Tasks configured in a ModelPack '
                                             'if a model pack is used for the project')
    relations = models.ManyToManyField('Relation', blank=True, default=None,
                                       help_text='Relations that will be available for this project')

    def save(self, *args, **kwargs):
        if self.model_pack is None and (self.concept_db is None or self.vocab is None):
            raise ValidationError('Must set at least the ModelPack or a Concept Database and Vocab Pair')
        if self.model_pack and (self.concept_db is not None or self.vocab is not None):
            raise ValidationError('Cannot set model pack and ConceptDB or a Vocab. You must use one or the other.')
        if self.deid_model_annotation and self.model_pack is None:
            raise ValidationError('Must set a DeID ModelPack for De-ID Model Annotation, cannot only set a cdb / vocab pair as'
                                  ' not be a DeId model')
        super().save(*args, **kwargs)


class ProjectAnnotateEntities(Project, ProjectAnnotateEntitiesFields):
    """
    Class for any single ProjectAnnotateEntities model fields that should not be inherited by ProjectGroup
    In practise its unlikely further fields are needed.
    """
    pass


class ProjectGroup(ProjectFields, ProjectAnnotateEntitiesFields):
    administrators = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                            help_text="The set of users that will have visibility of all "
                                                      "projects in this project group", related_name='administrators')
    annotators = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                        help_text="The set of users that will each be provided an annotation project",
                                        related_name='annotators')
    cdb_search_filter = models.ManyToManyField('ConceptDB', blank=True,
                                               help_text='The CDB that will be used for concept lookup. '
                                                         'This specific CDB should have been "imported" '
                                                         'via the CDB admin screen',
                                               related_name='project_group_concept_source')
    create_associated_projects = models.BooleanField(default=True,
                                                     help_text='This only functions on new Project Group entries. '
                                                               ' If creating a new Project Group and this is checked, '
                                                               'it will create a ProjectAnnotateEntities for each'
                                                               ' annotator. If unchecked it will not create associated'
                                                               ' ProjectAnnotateEntities instead, leaving the admin to '
                                                               ' manually configure groups of projects.')

    def __str__(self):
        return self.name


class MetaAnnotation(models.Model):
    annotated_entity = models.ForeignKey('AnnotatedEntity', on_delete=models.CASCADE)
    meta_task = models.ForeignKey('MetaTask', on_delete=models.CASCADE)
    meta_task_value = models.ForeignKey('MetaTaskValue', on_delete=models.CASCADE)
    acc = models.FloatField(default=1)
    predicted_meta_task_value = models.ForeignKey('MetaTaskValue', on_delete=models.CASCADE,
                                                  help_text='meta annotation predicted by a MetaAnnotationModel',
                                                  null=True, blank=True, related_name="predicted_value")
    validated = models.BooleanField(help_text='If an annotation is not ', default=False)
    last_modified = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.annotated_entity.last_modified = self.last_modified
        self.annotated_entity.save()

    def __str__(self):
        return str(self.annotated_entity)


class ExportedProject(models.Model):
    trainer_export_file = models.FileField(help_text='Previously exported MedCATtrainer .json file')

    def __str__(self):
        return self.trainer_export_file.name


class ProjectMetrics(models.Model):
    report_name_generated = models.TextField(help_text='report name that links this metrics report to a previously '
                                                       'ran bg task')
    report_name = models.TextField(help_text='A user specified report name that should be more user friendly than '
                                             'the generated one')
    report = models.FileField(help_text='the outputted metrics for configured')
    projects = models.ManyToManyField('ProjectAnnotateEntities', blank=True)

    def __str__(self):
        return f'generated report name: {self.report_name}, user specified report name:f{self.report_name}'


@receiver(models.signals.post_delete, sender=ConceptDB)
def auto_delete_cdb_file_on_delete(sender, instance, **kwargs):
    _remove_file(instance, 'cdb_file')


@receiver(models.signals.post_delete, sender=Vocabulary)
def auto_delete_vocab_file_on_delete(sender, instance, **kwargs):
    _remove_file(instance, 'vocab_file')


@receiver(models.signals.post_delete, sender=Dataset)
def auto_delete_dataset_file_on_delete(sender, instance, **kwargs):
    _remove_file(instance, 'original_file')


def _remove_file(instance, prop):
    if getattr(instance, prop):
        if os.path.isfile(getattr(instance, prop).path):
            os.remove(getattr(instance, prop).path)


class MedCATLoadException(Exception):
    def __init__(self, message):
        super().__init__(message)
