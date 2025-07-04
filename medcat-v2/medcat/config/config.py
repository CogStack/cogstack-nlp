import os
from typing import (Optional, Iterator, Iterable, TypeVar, cast, Type, Any,
                    Literal)
from typing import Protocol, runtime_checkable
from typing_extensions import Self
import logging
from datetime import datetime
from contextlib import contextmanager

from pydantic import BaseModel, Field, ValidationError

from medcat import __version__ as medcat_version
from medcat.utils.defaults import workers
from medcat.utils.envsnapshot import Environment, get_environment_info
from medcat.utils.iterutils import callback_iterator
from medcat.utils.defaults import (
    avoid_legacy_conversion, doing_legacy_conversion_message,
    LegacyConversionDisabledError)
from medcat.storage.serialisables import SerialisingStrategy
from medcat.storage.serialisers import deserialise


logger = logging.getLogger(__name__)


class SerialisableBaseModel(BaseModel):
    """The base serialisable config."""

    def get_strategy(self) -> SerialisingStrategy:
        return SerialisingStrategy.SERIALISABLES_AND_DICT

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        return []

    @classmethod
    def ignore_attrs(cls) -> list[str]:
        return []

    @classmethod
    def include_properties(cls) -> list[str]:
        return []

    def merge_config(self, other: dict):
        """Merge this config with another config's (partial) model dump.

        The exepctation is that the `other` dict is a partial model dump.
        Values specified there are overwritten into the current config.
        Values not specified there are left intact.

        The `other` config can have keys/values that do not exist in the
        config or sub-config. And they will be added where possible.

        Args:
            other (dict): The model dump

        Raises:
            IncorrectConfigValues: If unable to set the attribute,
                trying to set incorrect value, or trying to set sub-config
                values in an incorrect format (non-dict).
        """
        for k, v in other.items():
            if not hasattr(self, k):
                try:
                    setattr(self, k, v)
                except (ValidationError, ValueError) as e:
                    raise IncorrectConfigValues(
                        type(self), k, type(None), v
                    ) from e
                continue
            cur_v = getattr(self, k)
            if isinstance(cur_v, SerialisableBaseModel):
                if not isinstance(v, dict):
                    raise IncorrectConfigValues(
                        type(self), k, type(cur_v), v)
                cur_v.merge_config(v)
            else:
                try:
                    setattr(self, k, v)
                except ValidationError as e:
                    raise IncorrectConfigValues(
                        type(self), k, type(cur_v), v
                    ) from e

    @classmethod
    def load(cls, path: str) -> Self:
        if os.path.isfile(path) and path.endswith(".dat"):
            if avoid_legacy_conversion():
                raise LegacyConversionDisabledError(cls.__name__)
            doing_legacy_conversion_message(logger, cls.__name__, path)
            from medcat.utils.legacy.convert_config import (
                get_config_from_old_per_cls)
            return cast(Self, get_config_from_old_per_cls(path, cls))
        obj = deserialise(path)
        if not isinstance(obj, cls):
            raise ValueError(f"The path '{path}' is not a {cls.__name__}!")
        return obj


class IncorrectConfigValues(ValueError):

    def __init__(self, cls: Type, attr_name: str,
                 exp_type: Type, got: Any):
        super().__init__(f"Incorrect attribute set for {cls}.{attr_name}. "
                         f"Expected {exp_type}, but got {type(got)}: {got}")


@runtime_checkable
class PotentiallyDirty(Protocol):
    @property
    def is_dirty(self) -> bool:
        pass

    def mark_clean(self) -> None:
        pass


class DirtiableBaseModel(SerialisableBaseModel):
    _is_dirty: bool = False

    def __setattr__(self, name: str, value: Any):
        if name != '_is_dirty' and name in self.__annotations__:
            current = getattr(self, name, None)
            if current != value:
                self._is_dirty = True
        super().__setattr__(name, value)

    @property
    def is_dirty(self) -> bool:
        if self._is_dirty:
            return True
        for pn, part in self.__dict__.items():
            if isinstance(part, PotentiallyDirty):
                if part.is_dirty:
                    return True
        return False

    def mark_clean(self):
        self._is_dirty = False
        for part in self.__dict__.values():
            if isinstance(part, PotentiallyDirty):
                part.mark_clean()


class ComponentConfig(DirtiableBaseModel):
    comp_name: str = 'default'
    """The name of the component.

    If a custom implementation is required, it needs to be registered
    using `medcat.components.types.register_core_component(
            <core component type>, <component name>, <implementing class>)
    By default, only the 'default' component is registered.
    """


class NLPConfig(SerialisableBaseModel):
    disabled_components: list = ['ner', 'parser', 'vectors', 'textcat',
                                 'entity_linker', 'sentencizer',
                                 'entity_ruler', 'merge_noun_chunks',
                                 'merge_entities', 'merge_subtokens']
    """The list of components that will be disabled for the NLP.

    NB! For these changes to take effect, the pipe would need to be recreated.
    """
    provider: str = 'regex'
    """The NLP provider.

    Currently only regex and spacy are natively supported.

    NB! For these changes to take effect, the pipe would need to be recreated.
    """
    modelname: str = 'en_core_web_md'
    """What model will be used for tokenization.

    NB! For these changes to take effect, the pipe would need to be recreated.
    """

    # NOTE: this will allow for more config entries
    #       since we don't know what other implementations may require

    class Config:
        extra = 'allow'
        validate_assignment = True


class UsageMonitor(SerialisableBaseModel):
    enabled: Literal[True, False, 'auto'] = False
    r"""Whether usage monitoring is enabled (True), disabled (False),
    or automatic ('auto').
    If set to False, no logging is performed.
    If set to True, logs are saved in the location specified by `log_folder`.
    If set to 'auto', logs will be automatically enabled or disabled based on
    environmenta variable (`MEDCAT_LOGS` - setting it to False or 0
    disabled logging) and distributed according to the OS preferred logs
    location (`MEDCAT_LOGS_LOCATION`).
    The defaults for the location are:
     - For Linux: ~/.local/share/medcat/logs/
     - For Windows: C:\Users\%USERNAME%\.cache\medcat\logs\
    """
    batch_size: int = 100
    """Number of logged events to write at once."""
    file_prefix: str = "usage_"
    """The prefix for logged files. The suffix will be the model hash."""
    log_folder: str = "."
    """The folder which contains the usage logs. In certain situations,
    it may make sense to keep this separate from the overall logs.
    NOTE: Does not take affect if `enabled` is set to 'auto'"""


class General(SerialisableBaseModel):
    """The general part of the config"""
    nlp: NLPConfig = NLPConfig()
    # checkpoint: CheckPoint = CheckPoint()
    usage_monitor: UsageMonitor = UsageMonitor()
    """Checkpointing config"""
    log_level: int = logging.INFO
    """Logging config for everything | 'tagger' can be disabled,
    but will cause a drop in performance"""
    log_format: str = '%(levelname)s:%(name)s: %(message)s'
    log_path: str = './medcat.log'
    separator: str = '~'
    """Separator that will be used to merge tokens of a name.
    Once a CDB is built this should always stay the same."""
    spell_check: bool = True
    """Should we check spelling - note that this makes things much slower,
    use only if necessary. The only thing necessary for the spell checker
    to work is vocab.dat and cdb.dat built with concepts in the respective
    language."""
    diacritics: bool = False
    """Should we process diacritics - for languages other than English,
    symbols such as 'é, ë, ö' can be relevant. Note that this makes
    spell_check slower."""
    spell_check_deep: bool = False
    """If True the spell checker will try harder to find mistakes,
    this can slow down things drastically."""
    spell_check_len_limit: int = 7
    """Spelling will not be checked for words with length less than this"""
    show_nested_entities: bool = False
    """If set to True functions like get_entities and get_json will return
    nested_entities and overlaps"""
    full_unlink: bool = False
    """When unlinking a name from a concept should we do full_unlink
    (means unlink a name from all concepts, not just the one in question)"""
    workers: int = workers()
    """Number of workers used by a parallelizable pipeline component"""
    make_pretty_labels: Optional[str] = None
    """Should the labels of entities (shown in displacy) be pretty
    or just 'concept'. Slows down the annotation pipeline
    should not be used when annotating millions of documents.
    If `None` it will be the string "concept", if `short` it will be CUI,
    if `long` it will be CUI | Name | Confidence"""
    map_cui_to_group: bool = False
    """If the cdb.addl_info['cui2group'] is provided and this option enabled,
    each CUI will be mapped to the group"""
    simple_hash: bool = False
    """Whether to use a simple hash.

    NOTE: While using a simple hash is faster at save time, it is less
    reliable due to not taking into account all the details of the changes."""

    class Config:
        extra = 'allow'


class LinkingFilters(SerialisableBaseModel):
    """These describe the linking filters used alongside the model.

    When no CUIs nor excluded CUIs are specified (the sets are empty),
    all CUIs are accepted.
    If there are CUIs specified then only those will be accepted.
    If there are excluded CUIs specified, they are excluded.

    In some cases, there are extra filters as well as MedCATtrainer (MCT)
    export filters. These are expected to follow the following:
    extra_cui_filter ⊆ MCT filter ⊆ Model/config filter

    While any other CUIs can be included in the the extra CUI filter or
    the MCT filter, they would not have any real effect.
    """
    cuis: set[str] = set()
    cuis_exclude: set[str] = set()

    def __init__(self, **data):
        if 'cuis' in data:
            cuis = data['cuis']
            if isinstance(cuis, dict) and len(cuis) == 0:
                logger.warning("Loading an old model where "
                               "config.linking.filters.cuis has been "
                               "dict to an empty dict instead of an empty "
                               "set. Converting the dict to a set in memory "
                               "as that is what is expected. Please consider "
                               "saving the model again.")
                data['cuis'] = set(cuis.keys())
        super().__init__(**data)

    def check_filters(self, cui: str) -> bool:
        """Checks is a CUI in the filters

        Args:
            cui (str): The CUI in question

        Returns:
            bool: True if the CUI is allowed
        """
        if cui in self.cuis or not self.cuis:
            return cui not in self.cuis_exclude
        else:
            return False


class Linking(ComponentConfig):
    """The linking part of the config"""
    optim: dict = {'type': 'linear', 'base_lr': 1, 'min_lr': 0.00005}
    """Linear anneal"""
    # optim: dict = {'type': 'standard', 'lr': 1}
    context_vector_sizes: dict = {'xlong': 27, 'long': 18,
                                  'medium': 9, 'short': 3}
    """Context vector sizes that will be calculated and used for linking"""
    context_vector_weights: dict = {'xlong': 0.1, 'long': 0.4,
                                    'medium': 0.4, 'short': 0.1}
    """Weight of each vector in the similarity score - make trainable at
    some point. Should add up to 1."""
    filters: LinkingFilters = LinkingFilters()
    """Filters"""
    train: bool = True
    """Should it train or not, this is set automatically ignore in 99% of
    cases and do not set manually"""
    random_replacement_unsupervised: float = 0.80
    """If <1 during unsupervised training the detected term will be randomly
    replaced with a probability of 1 - random_replacement_unsupervised
    Replaced with a synonym used for that term"""
    disamb_length_limit: int = 3
    """All concepts below this will always be disambiguated"""
    filter_before_disamb: bool = False
    """If True it will filter before doing disamb. Useful for the trainer."""
    train_count_threshold: int = 1
    """Concepts that have seen less training examples than this will not be
    used for similarity calculation and will have a similarity of -1."""
    always_calculate_similarity: bool = False
    """Do we want to calculate context similarity even for concepts that are
    not ambiguous."""
    calculate_dynamic_threshold: bool = False
    """Concepts below this similarity will be ignored. Type can be
    static/dynamic - if dynamic each CUI has a different TH
    and it is calculated as the average confidence for that
    CUI * similarity_threshold. Take care that dynamic works only
    if the cdb was trained with calculate_dynamic_threshold = True."""
    similarity_threshold_type: str = 'static'
    similarity_threshold: float = 0.25
    negative_probability: float = 0.5
    """Probability for the negative context to be added for each
    positive addition"""
    negative_ignore_punct_and_num: bool = True
    """Do we ignore punct/num when negative sampling"""
    prefer_primary_name: float = 0.35
    """If >0 concepts for which a detection is its primary name
    will be preferred by that amount (0 to 1)"""
    prefer_frequent_concepts: float = 0.35
    """If >0 concepts that are more frequent will be preferred
    by a multiply of this amount"""
    subsample_after: int = 30000
    """DISABLED in code permanetly: Subsample during unsupervised
    training if a concept has received more than"""
    devalue_linked_concepts: bool = False
    """When adding a positive example, should it also be treated as Negative
    for concepts which link to the positive one via names (ambiguous names)."""
    context_ignore_center_tokens: bool = False
    """If true when the context of a concept is calculated (embedding)
    the words making that concept are not taken into account"""
    additional: Optional[Any] = None
    """Some additional config for non-default linkers.
    E.g the 2-step linker uses this for alpha calculations
    and learning rate for type contexts.
    """

    class Config:
        extra = 'allow'


class Preprocessing(SerialisableBaseModel):
    """The preprocessing part of the config"""
    words_to_skip: set = {'nos'}
    """This words will be completely ignored from concepts and from the text
    (must be a Set)"""
    keep_punct: set = {'.', ':'}
    """All punct will be skipped by default, here you can set what
    will be kept"""
    do_not_normalize: set[str] = {'VBD', 'VBG', 'VBN', 'VBP', 'JJS', 'JJR'}
    """Should specific word types be normalized: e.g. running -> run
    Values are detailed part-of-speech tags. See:
    - https://spacy.io/usage/linguistic-features#pos-tagging
    - Label scheme section per model at https://spacy.io/models/en"""
    skip_stopwords: bool = False
    """Should stopwords be skipped/ignored when processing input"""
    min_len_normalize: int = 5
    """Nothing below this length will ever be normalized (input tokens or
    concept names), normalized means lemmatized in this case"""
    stopwords: Optional[set] = None
    """If None the default set of stowords from spacy will be used.
    This must be a Set.

    NB! For these changes to take effect, the pipe would need to be recreated.
    """
    max_document_length: int = 1000000
    """Documents longer  than this will be trimmed.

    NB! For these changes to take effect, the pipe would need to be recreated.
    """


class CDBMaker(SerialisableBaseModel):
    """The Context Database (CDB) making part of the config"""
    name_versions: list = ['LOWER', 'CLEAN']
    """Name versions to be generated."""
    multi_separator: str = '|'
    """If multiple names or type_ids for a concept present in one row of a CSV,
    they are separated by the specified character."""
    remove_parenthesis: int = 5
    """Should preferred names with parenthesis be cleaned 0 means no,
    else it means if longer than or equal
    e.g. Head (Body part) -> Head"""
    min_letters_required: int = 2
    """Minimum number of letters required in a name to be accepted
    for a concept"""


class Ner(ComponentConfig):
    """The NER part of the config"""
    min_name_len: int = 3
    """Do not detect names below this limit, skip them"""
    max_skip_tokens: int = 2
    """When checking tokens for concepts you can have skipped tokens between
    used ones (usually spaces, new lines etc). This number tells you how many
    skipped can you have."""
    check_upper_case_names: bool = False
    """Check uppercase to distinguish uppercase and lowercase words that have
    a different meaning."""
    upper_case_limit_len: int = 4
    """Any name shorter than this must be uppercase in the text to be
    considered. If it is not uppercase
    it will be skipped."""
    try_reverse_word_order: bool = False
    """Try reverse word order for short concepts (2 words max),
    e.g. heart disease -> disease heart"""
    custom_cnf: Optional[Any] = None
    """The custom config for the component."""

    class Config:
        extra = 'allow'


class AnnotationOutput(SerialisableBaseModel):
    """The annotation output part of the config"""
    context_left: int = -1
    context_right: int = -1
    lowercase_context: bool = True
    include_text_in_output: bool = False


# NOTE: this class should have an attribute for each
#       medcat.components.types.CoreComponentType
class Components(SerialisableBaseModel):
    tagging: ComponentConfig = ComponentConfig()
    token_normalizing: ComponentConfig = ComponentConfig()
    ner: Ner = Ner()
    linking: Linking = Linking()
    comp_order: list[str] = ['tagging', 'token_normalizing',
                             'ner', 'linking']
    addons: list[ComponentConfig] = []


class TrainingDescriptor(SerialisableBaseModel):
    train_time_start: datetime
    train_time_end: datetime
    project_name: Optional[str]
    num_docs: int
    num_epochs: int = 1


T = TypeVar('T')
C = TypeVar('C', bound=Iterable)


class ModelMeta(SerialisableBaseModel):
    description: str = 'N/A'
    ontology: list[str] = []
    location: str = 'N/A'
    hash: str = ''  # TODO - implement
    history: list[str] = Field(default_factory=list)
    last_saved: datetime = Field(default_factory=datetime.now)
    unsup_trained: list[TrainingDescriptor] = []  # TODO - implement
    sup_trained: list[TrainingDescriptor] = []  # TODO - implement
    medcat_version: str = ''
    saved_environ: Environment = Field(default_factory=get_environment_info)

    def mark_saved_now(self):
        self.last_saved = datetime.now()
        self.saved_environ = get_environment_info()
        self.medcat_version = medcat_version

    # NOTE: this is expected to be called when training finished
    def add_unsup_training(self, start_time: datetime, num_docs: int,
                           num_epochs: int = 1, project_name: str = 'N/A'):
        """Add unsupervised training information based on data.

        NOTE: This will mark down the time taken for training by comparing
              the start time to the current time.

        Args:
            start_time (datetime): The time at which the training was started.
            num_docs (int): The number of documents trained.
            num_epochs (int, optional): The number of epochs. Defaults to 1.
            project_name (str, optional): The project name. Defaults to 'N/A'.
        """
        self.unsup_trained.append(TrainingDescriptor(
            train_time_start=start_time, train_time_end=datetime.now(),
            project_name=project_name, num_docs=num_docs,
            num_epochs=num_epochs))

    def add_sup_training(self, start_time: datetime, num_docs: int,
                         project_name: str) -> None:
        """Add supervised training information based on data.

        NOTE: This will mark down the time taken for training by comparing
              the start time to the current time.

        NOTE: This will be called for every project being trained separately.
              So if there's a MCT export being trained with multiple projects,
              multiple different training instances will be recorded.

        Args:
            start_time (datetime): The time at which the training was started.
            num_docs (int): The number of documents that were trained.
            project_name (str): The project name.
        """
        self.sup_trained.append(TrainingDescriptor(
            train_time_start=start_time, train_time_end=datetime.now(),
            project_name=project_name, num_docs=num_docs, num_epochs=1
        ))

    @contextmanager
    def prepare_and_report_training(self,
                                    data_iterator: C,
                                    num_epochs: int,
                                    supervised: bool = False,
                                    project_name: str = 'N/A'
                                    ) -> Iterator[C]:
        """Context manager for preparing training.

        This is used so that we can get the number of items in the data
        during training.

        Args:
            data_iterator (C): The data to be trained.
            num_epochs (int): The number of epochs to be used.
            supervised (bool, optional): Whether training is supervised.
                Defaults to False.
            project_name (str, optional): The project name. Defaults to 'N/A'.

        Yields:
            Iterator[C]: The same data that was input.
        """
        _names, _counts = [], [0]  # NOTE: 0 count for fallback

        def callback(name: str, count: int) -> None:
            _names.append(name)
            _counts.append(count)
        wrapped = callback_iterator(f"TRAIN-{id(data_iterator)}",
                                    data_iterator, callback)
        start_time = datetime.now()
        try:
            yield cast(C, wrapped)
        finally:
            # even if something fails, log the count
            num_docs = _counts[1]
            if supervised:
                self.add_sup_training(start_time=start_time,
                                      num_docs=num_docs,
                                      project_name=project_name)
            else:
                self.add_unsup_training(start_time=start_time,
                                        num_docs=num_docs,
                                        num_epochs=num_epochs,
                                        project_name=project_name)
            if len(_names) != 1:
                logger.warning(
                    "Something went wrong during %ssupervised training. "
                    "The number of documents trained was unable to be "
                    "clearly obtained. Counted %d names (%s) at %s",
                    'un' if not supervised else '', len(_names), _names,
                    _counts)


class Config(SerialisableBaseModel):
    general: General = General()
    components: Components = Components()
    # linking: Linking = Linking()
    preprocessing: Preprocessing = Preprocessing()
    cdb_maker: CDBMaker = CDBMaker()
    # ner: Ner = Ner()
    annotation_output: AnnotationOutput = AnnotationOutput()
    meta: ModelMeta = Field(default_factory=ModelMeta)


def get_important_config_parameters(config: Config) -> dict[str, Any]:
    return {
        "config.ponents.ner.min_name_len": {
            'value': config.components.ner.min_name_len,
            'description': ("Minimum detection length (found terms/mentions "
                            "shorter than this will not be detected).")
            },
        "config.ponents.ner.upper_case_limit_len": {
            'value': config.components.ner.upper_case_limit_len,
            'description': ("All detected terms shorter than this value have "
                            "to be uppercase, otherwise they will be ignored.")
            },
        "config.ponents.linking.similarity_threshold": {
            'value': config.components.linking.similarity_threshold,
            'description': ("If the confidence of the model is lower than "
                            "this a detection will be ignore.")
            },
        "config.ponents.linking.filters.cuis": {
            'value': len(config.components.linking.filters.cuis),
            'description': ("Length of the CUIs filter to be included in "
                            "outputs. If this is not 0 (i.e. not empty) its "
                            "best to check what is included before using the "
                            "model")
        },
        "config.general.spell_check": {
            'value': config.general.spell_check,
            'description': "Is spell checking enabled."
            },
        "config.general.spell_check_len_limit": {
            'value': config.general.spell_check_len_limit,
            'description': "Words shorter than this will not be spell checked."
            },
    }
