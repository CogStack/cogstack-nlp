import os
import json
import logging
import numpy
from multiprocessing import Lock
from datetime import datetime
from typing import Iterable, Optional, cast, Union, Any, TypedDict, Callable
from typing import overload, Literal

from medcat.utils.hasher import Hasher

import torch
from torch import nn, Tensor
from medcat.tokenizing.tokenizers import BaseTokenizer
from medcat.config.config import ComponentConfig
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.components.addons.meta_cat.ml_utils import (
    predict, train_model, set_all_seeds, eval_model)
from medcat.components.addons.meta_cat.data_utils import (
    prepare_from_json, encode_category_values, prepare_for_oversampled_data)
from medcat.components.addons.addons import AddonComponent
from medcat.components.addons.meta_cat.mctokenizers.tokenizers import (
    TokenizerWrapperBase, init_tokenizer, load_tokenizer)
from medcat.storage.serialisers import serialise, deserialise
from medcat.storage.serialisables import (
    AbstractSerialisable, SerialisingStrategy)
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.utils.defaults import COMPONENTS_FOLDER
from medcat.utils.defaults import (
    avoid_legacy_conversion, doing_legacy_conversion_message,
    LegacyConversionDisabledError)
from peft import get_peft_model, LoraConfig, TaskType

# It should be safe to do this always, as all other multiprocessing
# will be finished before data comes to meta_cat
os.environ["TOKENIZERS_PARALLELISM"] = "true"

logger = logging.getLogger(__name__)


_META_ANNS_PATH = 'meta_cat_meta_anns'
_SHARE_TOKENS_PATH = 'meta_cat_share_tokens'


class MedCATTrainerExportDocument(TypedDict):
    name: str
    confidence: float
    value: str


class MetaAnnotationValue(TypedDict):
    name: str
    value: str
    confidence: float


TokenizerPreprocessor = Optional[
    Callable[[Optional[TokenizerWrapperBase]], None]]


class MetaCATAddon(AddonComponent):
    DEFAULT_TOKENIZER = 'spacy'
    addon_type = 'meta_cat'
    output_key = 'meta_anns'
    config: ConfigMetaCAT

    def __init__(self, config: ConfigMetaCAT, base_tokenizer: BaseTokenizer,
                 meta_cat: Optional['MetaCAT']) -> None:
        self.config = config
        self._mc = meta_cat
        self._name = config.general.category_name
        self._init_data_paths(base_tokenizer)

    @property
    def mc(self) -> 'MetaCAT':
        if self._mc is None:
            raise ValueError("Need to have specified MetaCAT")
        return self._mc

    @classmethod
    def create_new(cls, config: ConfigMetaCAT, base_tokenizer: BaseTokenizer,
                   tknzer_preprocessor: TokenizerPreprocessor = None
                   ) -> 'MetaCATAddon':
        """Factory method to create a new MetaCATAddon instance."""
        tokenizer = init_tokenizer(config)
        if tknzer_preprocessor is not None:
            tknzer_preprocessor(tokenizer)
        meta_cat = MetaCAT(tokenizer, embeddings=None, config=config)
        return cls(config, base_tokenizer, meta_cat)

    @classmethod
    def create_new_component(
            cls, cnf: ComponentConfig, tokenizer: BaseTokenizer,
            cdb: CDB, vocab: Vocab, model_load_path: Optional[str]
            ) -> 'MetaCATAddon':
        if not isinstance(cnf, ConfigMetaCAT):
            raise ValueError(f"Incompatible config: {cnf}")
        if model_load_path is not None:
            components_folder = os.path.join(
                model_load_path, COMPONENTS_FOLDER)
            folder_name = cls.get_folder_name_for_addon_and_name(
                cls.addon_type, str(cnf.general.category_name))
            load_path = os.path.join(components_folder, folder_name)
            return cls.load_existing(cnf, tokenizer, load_path)
        # TODO: tokenizer preprocessing for (e.g) BPE tokenizer (see PR #67)
        return cls.create_new(cnf, tokenizer, None)

    @classmethod
    def load_existing(cls, cnf: ConfigMetaCAT,
                      base_tokenizer: BaseTokenizer,
                      load_path: str) -> 'MetaCATAddon':
        """Factory method to load an existing MetaCATAddon from disk."""
        meta_cat = cls(cnf, base_tokenizer, None)  # Temporary instance
        meta_cat._mc = meta_cat.load(load_path)
        return meta_cat

    @property
    def name(self) -> str:
        return str(self._name)

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        return self.mc(doc)

    def load(self, folder_path: str) -> 'MetaCAT':
        mc_path, tokenizer_folder = self._get_meta_cat_and_tokenizer_paths(
            folder_path)
        mc = cast(MetaCAT, deserialise(mc_path, save_dir_path=folder_path))
        mc.tokenizer = self._load_tokenizer(self.config, tokenizer_folder)
        return mc

    @classmethod
    def _load_tokenizer(cls, config: ConfigMetaCAT, tokenizer_folder: str
                        ) -> Optional[TokenizerWrapperBase]:
        return load_tokenizer(config, tokenizer_folder)

    @classmethod
    def _get_meta_cat_and_tokenizer_paths(cls, folder_path: str
                                          ) -> tuple[str, str]:
        return (os.path.join(folder_path, 'meta_cat'),
                os.path.join(folder_path, "tokenizer"))

    def save(self, folder_path: str) -> None:
        mc_path, tokenizer_folder = self._get_meta_cat_and_tokenizer_paths(
            folder_path)
        os.mkdir(mc_path)
        os.mkdir(tokenizer_folder)
        serialise(self.config.general.serialiser, self.mc, mc_path)
        if self.mc.tokenizer is None:
            raise MisconfiguredMetaCATException(
                "Unable to save MetaCAT without a tokenizer")
        self.mc.tokenizer.save(tokenizer_folder)
        if self.config.model.model_name == 'bert':
            model_config_save_path = os.path.join(
                folder_path, 'bert_config.json')
            self._mc.model.bert_config.to_json_file(  # type: ignore
                model_config_save_path)

    def _init_data_paths(self, base_tokenizer: BaseTokenizer):
        # a dictionary like {category_name: value, ...}
        base_tokenizer.get_entity_class().register_addon_path(
            _META_ANNS_PATH, def_val=None, force=True)
        # Used for sharing pre-processed data/tokens
        base_tokenizer.get_doc_class().register_addon_path(
            _SHARE_TOKENS_PATH, def_val=None, force=True)

    @property
    def include_in_output(self) -> bool:
        return True

    def get_output_key_val(self, ent: MutableEntity
                           ) -> tuple[str, dict[str, MetaAnnotationValue]]:
        # NOTE: In case of multiple MetaCATs, this will be called
        #       once for each MetaCAT and will get the same value.
        #       But it shouldn't be too much of an issue.
        return self.output_key, ent.get_addon_data(_META_ANNS_PATH)

    # for ManualSerialisable:

    def serialise_to(self, folder_path: str) -> None:
        os.mkdir(folder_path)
        self.save(folder_path)

    @classmethod
    def _create_throwaway_tokenizer(cls) -> BaseTokenizer:
        from medcat.tokenizing.tokenizers import create_tokenizer
        from medcat.config import Config
        logger.warning(
            "A base tokenizer was not provided during the loading of a "
            "MetaCAT. The tokenizer is used to register the required data "
            "paths for MetaCAT to function. Using the default of '%s'. If "
            "this it not the tokenizer you will end up using, MetaCAT may "
            "be unable to recover unless a) the paths are registered "
            "explicitly, or b) there are other MetaCATs created with the "
            "correct tokenizer. Do note that this will also create "
            "another instance of the tokenizer, though it should be "
            "garbage collected soon.", cls.DEFAULT_TOKENIZER
        )
        # NOTE: the use of a (mostly) default config here probably won't
        #       affect anything since the tokenizer itself won't be used
        gcnf = Config()
        gcnf.general.nlp.provider = 'spacy'
        return create_tokenizer(cls.DEFAULT_TOKENIZER, gcnf)

    @classmethod
    def deserialise_from(cls, folder_path: str, **init_kwargs
                         ) -> 'MetaCATAddon':
        if "model.dat" in os.listdir(folder_path):
            if not avoid_legacy_conversion():
                doing_legacy_conversion_message(
                    logger, cls.__name__, folder_path)
                from medcat.utils.legacy.convert_meta_cat import (
                    get_meta_cat_from_old)
                return get_meta_cat_from_old(
                    folder_path, cls._create_throwaway_tokenizer())
            raise LegacyConversionDisabledError(cls.__name__,)
        if 'cnf' in init_kwargs:
            cnf = init_kwargs['cnf']
        else:
            config_path = os.path.join(folder_path, "meta_cat", "config")
            if not os.path.exists(config_path):
                # load legacy config (assuming it exists)
                config_path += ".dat"
            logger.info(
                "Was not provide a config when loading a meta cat from '%s'. "
                "Inferring config from file at '%s'", folder_path,
                config_path)
            cnf = ConfigMetaCAT.load(config_path)
        if 'model_config' in init_kwargs:
            cnf.merge_config(init_kwargs['model_config'])
        if 'tokenizer' in init_kwargs:
            tokenizer = init_kwargs['tokenizer']
        else:
            tokenizer = cls._create_throwaway_tokenizer()
        return cls.load_existing(
            load_path=folder_path,
            cnf=cnf,
            base_tokenizer=tokenizer)

    def get_strategy(self) -> SerialisingStrategy:
        return SerialisingStrategy.MANUAL

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        return []

    @classmethod
    def ignore_attrs(cls) -> list[str]:
        return []

    @classmethod
    def include_properties(cls) -> list[str]:
        return []

    def get_hash(self) -> str:
        if self._mc:
            return self._mc.get_hash()
        else:
            return 'No-model'


def get_meta_annotations(entity: MutableEntity
                         ) -> dict[str, MetaAnnotationValue]:
    return entity.get_addon_data(_META_ANNS_PATH)


class MetaCAT(AbstractSerialisable):
    """The MetaCAT class used for training 'Meta-Annotation' models,
    i.e. annotations of clinical concept annotations. These are also
    known as properties or attributes of recognise entities sin similar
    tools such as MetaMap and cTakes.

    This is a flexible model agnostic class that can learns any
    meta-annotation task, i.e. any multi-class classification task
    for recognised terms.

    Args:
        tokenizer (TokenizerWrapperBase):
            The Huggingface tokenizer instance. This can be a pre-trained
            tokenzier instance from a BERT-style model, or trained from
            scratch for the Bi-LSTM (w. attention) model that is currentl
              used in most deployments.
        embeddings (Tensor, numpy.ndarray):
            embedding mapping (sub)word input id n-dim (sub)word embedding.
        config (ConfigMetaCAT):
            the configuration for MetaCAT. Param descriptions available in
            ConfigMetaCAT docs.
    """

    # Custom pipeline component name
    name = 'meta_cat'
    _component_lock = Lock()

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        return ['tokenizer', 'embeddings', 'config',
                '_model_state_dict']

    @classmethod
    def ignore_attrs(cls) -> list[str]:
        return ['model', 'save_dir_path']

    @classmethod
    def include_properties(cls) -> list[str]:
        return ['_model_state_dict']

    @property
    def _model_state_dict(self):
        return self.model.state_dict()

    # Override
    def __init__(self,
                 tokenizer: Optional[TokenizerWrapperBase] = None,
                 embeddings: Optional[Union[Tensor, numpy.ndarray]] = None,
                 config: Optional[ConfigMetaCAT] = None,
                 _model_state_dict: Optional[dict[str, Any]] = None,
                 save_dir_path: Optional[str] = None) -> None:
        if config is None:
            config = ConfigMetaCAT()
        self.config = config
        self.save_dir_path = save_dir_path
        set_all_seeds(config.general.seed)

        self.tokenizer = tokenizer
        if tokenizer is not None:
            self._reset_tokenizer_info()

        self.embeddings = (torch.tensor(
            embeddings, dtype=torch.float32) if embeddings is not None
            else None)
        self.model = self.get_model(embeddings=self.embeddings)
        if _model_state_dict:
            self.model.load_state_dict(_model_state_dict)

    def _reset_tokenizer_info(self):
        # Set it in the config
        self.config.general.tokenizer_name = self.tokenizer.name
        self.config.general.vocab_size = self.tokenizer.get_size()
        # We will also set the padding
        self.config.model.padding_idx = cast(int, self.tokenizer.get_pad_id())

    def get_model(self, embeddings: Optional[Tensor]) -> nn.Module:
        """Get the model

        Args:
            embeddings (Optional[Tensor]):
                The embedding densor

        Raises:
            ValueError: If the meta model is not LSTM or BERT

        Returns:
            nn.Module:
                The module
        """
        config = self.config
        if config.model.model_name == 'lstm':
            from medcat.components.addons.meta_cat.models import LSTM
            model: nn.Module = LSTM(embeddings, config)
            logger.info("LSTM model used for classification")

        elif config.model.model_name == 'bert':
            from medcat.components.addons.meta_cat.models import (
                BertForMetaAnnotation)
            model = BertForMetaAnnotation(config, self.save_dir_path)

            if not config.model.model_freeze_layers:
                peft_config = LoraConfig(
                    task_type=TaskType.SEQ_CLS, inference_mode=False, r=8,
                    lora_alpha=16, target_modules=["query", "value"],
                    lora_dropout=0.2)

                # NOTE: Not sure what changed between transformers 4.50.3 and
                # 4.50.1 that made this fail for mypy. But as best as I can
                # tell, it still works just the same
                model = get_peft_model(model, peft_config)  # type: ignore
                # model.print_trainable_parameters()

            logger.info("BERT model used for classification")

        else:
            raise ValueError("Unknown model name %s" % config.model.model_name)

        return model

    def get_hash(self) -> str:
        """A partial hash trying to catch differences between models.

        Returns:
            str: The hex hash.
        """
        hasher = Hasher()
        # Set last_train_on if None
        if self.config.train.last_train_on is None:
            self.config.train.last_train_on = datetime.now().timestamp()

        hasher.update(self.config.model_dump())
        return hasher.hexdigest()

    def train_from_json(self, json_path: Union[str, list],
                        save_dir_path: Optional[str] = None,
                        data_oversampled: Optional[list] = None,
                        overwrite: bool = False) -> dict:
        """Train or continue training a model give a json_path containing
        a MedCATtrainer export. It will continue training if an existing
        model is loaded or start new training if the model is blank/new.

        Args:
            json_path (Union[str, list]):
                Path/Paths to a MedCATtrainer export containing the
                meta_annotations we want to train for.
            save_dir_path (Optional[str]):
                In case we have aut_save_model (meaning during the
                training the best model will be saved) we need to
                set a save path. Defaults to `None`.
            data_oversampled (Optional[list]):
                In case of oversampling being performed, the data
                will be passed in the parameter allowing the
                model to be trained on original + synthetic data.
            overwrite (bool):
                Whether to allow overwriting the file if/when appropriate.

        Returns:
            dict: The resulting report.
        """

        # Load the medcattrainer export
        if isinstance(json_path, str):
            json_path = [json_path]

        def merge_data_loaded(base, other):
            if not base:
                return other
            elif other is None:
                return base
            else:
                for p in other['projects']:
                    base['projects'].append(p)
            return base

        # Merge data from all different data paths
        data_loaded: dict = {}
        for path in json_path:
            with open(path, 'r') as f:
                data_loaded = merge_data_loaded(data_loaded, json.load(f))
        return self.train_raw(data_loaded, save_dir_path,
                              data_oversampled=data_oversampled,
                              overwrite=overwrite)

    def train_raw(self, data_loaded: dict, save_dir_path: Optional[str] = None,
                  data_oversampled: Optional[list] = None,
                  overwrite: bool = False) -> dict:
        """
        Train or continue training a model given raw data. It will continue
        training if an existing model is loaded or start new training if
        the model is blank/new.

        The raw data is expected in the following format:
        {
            'projects': [  # list of projects
                {
                    'name': '<project_name>',
                    'documents': [  # list of documents
                        {
                            'name': '<document_name>',
                            'text': '<text_of_document>',
                            'annotations': [  # list of annotations
                                {
                                    # start index of the annotation
                                    'start': -1,
                                    'end': 1,    # end index of the annotation
                                    'cui': 'cui',
                                    'value': '<annotation_value>'
                                },
                                ...
                            ],
                        },
                        ...
                    ]
                },
                ...
            ]
        }

        Args:
            data_loaded (dict):
                The raw data we want to train for.
            save_dir_path (Optional[str]):
                In case we have aut_save_model (meaning during the training
                the best model will be saved) we need to set a save path.
                Defaults to `None`.
            data_oversampled (Optional[list]):
                In case of oversampling being performed, the data will be
                passed in the parameter allowing the model to be trained on
                original + synthetic data. The format of which is expected:
                [[['text','of','the','document'], [index of medical entity],
                    "label" ],
                ['text','of','the','document'], [index of medical entity],
                    "label" ]]
            overwrite (bool):
                Whether to allow overwriting the file if/when appropriate.

        Returns:
            dict: The resulting report.

        Raises:
            Exception: If no save path is specified, or category name
                not in data.
            AssertionError: If no tokeniser is set
            FileNotFoundError: If phase_number is set to 2 and model.dat
                file is not found
            KeyError: If phase_number is set to 2 and model.dat file
                contains mismatched architecture
        """
        g_config = self.config.general
        t_config = self.config.train

        # Create directories if they don't exist
        if t_config.auto_save_model:
            if save_dir_path is None:
                raise Exception("The `save_dir_path` argument is required if "
                                "`aut_save_model` is `True` in the config")
            else:
                os.makedirs(save_dir_path, exist_ok=True)

        # Prepare the data
        assert self.tokenizer is not None
        data_in = prepare_from_json(
            data_loaded, g_config.cntx_left, g_config.cntx_right,
            self.tokenizer, cui_filter=t_config.cui_filter,
            replace_center=g_config.replace_center,
            prerequisites=t_config.prerequisites, lowercase=g_config.lowercase)

        # Check is the name present
        category_name = g_config.get_applicable_category_name(
            data_in)
        if category_name is None:
            in_cat_name = g_config.category_name
            raise Exception(
                "The category name does not exist in this json file. "
                f"You've provided '{in_cat_name}', while the possible "
                f"options are: {' | '.join(list(data_in.keys()))}. "
                "Additionally, ensure the populate the "
                "'alternative_category_names' attribute to accommodate "
                "for variations.")

        data = data_in[category_name]
        if data_oversampled:
            data_sampled = prepare_for_oversampled_data(
                data_oversampled, self.tokenizer)
            data = data + data_sampled

        category_value2id = g_config.category_value2id
        if not category_value2id:
            # Encode the category values
            (full_data, data_undersampled,
             category_value2id) = encode_category_values(
                 data,
                 category_undersample=self.config.model.category_undersample,
                 alternative_class_names=g_config.alternative_class_names)
        else:
            # We already have everything, just get the data
            (full_data, data_undersampled,
             category_value2id) = encode_category_values(
                 data, existing_category_value2id=category_value2id,
                 category_undersample=self.config.model.category_undersample,
                 alternative_class_names=g_config.alternative_class_names)
            g_config.category_value2id = category_value2id
            self.config.model.nclasses = len(category_value2id)
        # Make sure the config number of classes is the same
        # as the one found in the data
        if len(category_value2id) != self.config.model.nclasses:
            logger.warning(
                "The number of classes set in the config is not the same as "
                f"the one found in the data: {self.config.model.nclasses} vs "
                f"{len(category_value2id)}")
            logger.warning("Auto-setting the nclasses value in config and "
                           "rebuilding the model.")
            self.config.model.nclasses = len(category_value2id)

        if self.config.model.phase_number == 2 and save_dir_path is not None:
            model_save_path = os.path.join(save_dir_path, 'model.dat')
            device = torch.device(g_config.device)
            try:
                self.model.load_state_dict(torch.load(
                    model_save_path, map_location=device))
                logger.info("Training model for Phase 2, with model dict "
                            "loaded from disk")
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"\nError: Model file not found at path: {model_save_path}"
                    "\nPlease run phase 1 training and then run phase 2.")

            except KeyError:
                raise KeyError(
                    "\nError: Missing key in loaded state dictionary. "
                    "\nThis might be due to a mismatch between the model "
                    "architecture and the saved state.")

            except Exception as e:
                raise Exception(
                    f"\nError: Model state cannot be loaded from dict. {e}")

        data = full_data
        if self.config.model.phase_number == 1:
            data = data_undersampled
            if not t_config.auto_save_model:
                logger.info("For phase 1, model state has to be saved. "
                            "Saving model...")
                t_config.auto_save_model = True
            logger.info("Training model for Phase 1 now...")

        report = train_model(self.model, data=data, config=self.config,
                             save_dir_path=save_dir_path)

        # If autosave, then load the best model here
        if t_config.auto_save_model:
            if save_dir_path is None:
                raise Exception("The `save_dir_path` argument is required if "
                                "`aut_save_model` is `True` in the config")
            else:
                path = os.path.join(save_dir_path, 'model.dat')
                device = torch.device(g_config.device)
                self.model.load_state_dict(torch.load(
                    path, map_location=device))

                # Save everything now
                serialise(self.config.general.serialiser, self, save_dir_path,
                          overwrite=overwrite)

        self.config.train.last_train_on = datetime.now().timestamp()
        return report

    def eval(self, json_path: str) -> dict:
        """Evaluate from json.

        Args:
            json_path (str):
                The json file ath

        Returns:
            dict:
                The resulting model dict

        Raises:
            AssertionError: If self.tokenizer
            Exception: If the category name does not exist
        """
        g_config = self.config.general
        t_config = self.config.train

        with open(json_path, 'r') as f:
            data_loaded: dict = json.load(f)

        # Prepare the data
        assert self.tokenizer is not None
        data_in = prepare_from_json(
            data_loaded, g_config.cntx_left, g_config.cntx_right,
            self.tokenizer, cui_filter=t_config.cui_filter,
            replace_center=g_config.replace_center,
            prerequisites=t_config.prerequisites, lowercase=g_config.lowercase)

        # Check is the name there
        category_name = g_config.get_applicable_category_name(data_in)
        if category_name is None:
            raise Exception(
                "The category name does not exist in this json file.")

        data = data_in[category_name]

        # We already have everything, just get the data
        category_value2id = g_config.category_value2id
        data, _, _ = encode_category_values(
            data, existing_category_value2id=category_value2id)

        # Run evaluation
        assert self.tokenizer is not None
        result = eval_model(self.model, data, config=self.config,
                            tokenizer=self.tokenizer)

        return result

    def get_ents(self, doc: MutableDocument) -> Iterable[MutableEntity]:
        # TODO - use span groups?
        return doc.ner_ents  # TODO: is this correct?

    def prepare_document(self, doc: MutableDocument, input_ids: list,
                         offset_mapping: list, lowercase: bool
                         ) -> tuple[dict, list]:
        """Prepares document.

        Args:
            doc (Doc):
                The document
            input_ids (list):
                Input ids
            offset_mapping (list):
                Offset mappings
            lowercase (bool):
                Whether to use lower case replace center

        Returns:
            tuple[dict, list]:
                Entity id to index mapping
                and
                Samples
        """
        config = self.config
        cntx_left = config.general.cntx_left
        cntx_right = config.general.cntx_right
        replace_center = config.general.replace_center

        ents = self.get_ents(doc)

        samples = []
        last_ind = 0
        # Map form entity ID to where is it in the samples array
        ent_id2ind = {}
        for ent in sorted(ents, key=lambda ent: ent.base.start_char_index):
            start = ent.base.start_char_index
            end = ent.base.end_char_index

            # Updated implementation to extract all the tokens for
            # the medical entity (rather than the one)
            ctoken_idx = []
            for ind, pair in enumerate(offset_mapping[last_ind:]):
                # Checking if we've reached at the start of the entity
                if start <= pair[0] or start <= pair[1]:
                    if end <= pair[1]:
                        ctoken_idx.append(ind)  # End reached
                        break
                    else:
                        ctoken_idx.append(ind)  # Keep going

            # Start where the last ent was found, cannot be before it as we've
            # sorted
            last_ind += ind  # If we did not start from 0 in the for loop

            _start = max(0, ctoken_idx[0] - cntx_left)
            _end = min(len(input_ids), ctoken_idx[-1] + 1 + cntx_right)

            tkns = input_ids[_start:_end]
            cpos = cntx_left + min(0, ind - cntx_left)
            cpos_new = [x - _start for x in ctoken_idx]

            if replace_center is not None:
                if lowercase:
                    replace_center = replace_center.lower()
                # We start from ind
                s_ind = ind
                e_ind = ind
                for _ind, pair in enumerate(offset_mapping[ind:]):
                    if end > pair[0] and end <= pair[1]:
                        e_ind = _ind + ind
                        break
                ln = e_ind - s_ind  # Length of the concept in tokens
                assert self.tokenizer is not None
                tkns = tkns[:cpos] + self.tokenizer(
                    replace_center)['input_ids'] + tkns[cpos + ln + 1:]
            samples.append([tkns, cpos_new])
            ent_id2ind[ent.id] = len(samples) - 1

        return ent_id2ind, samples

    @staticmethod
    def batch_generator(stream: Iterable[MutableDocument],
                        batch_size_chars: int
                        ) -> Iterable[list[MutableDocument]]:
        """Generator for batch of documents.

        Args:
            stream (Iterable[MutableDocument]):
                The document stream
            batch_size_chars (int):
                Number of characters per batch

        Yields:
            list[MutableDocument]: The batch of documents.
        """
        docs = []
        char_count = 0
        for doc in stream:
            char_count += len(doc.base.text)
            docs.append(doc)
            if char_count < batch_size_chars:
                continue
            yield docs
            docs = []
            char_count = 0

        # If there is anything left return that also
        if len(docs) > 0:
            yield docs

    def _set_meta_anns(self,
                       doc: MutableDocument,
                       id2category_value: dict
                       ) -> MutableDocument:
        config = self.config
        data: list
        if (not config.general.save_and_reuse_tokens or
                doc.get_addon_data(_SHARE_TOKENS_PATH) is None):
            if config.general.lowercase:
                all_text = doc.base.text.lower()
            else:
                all_text = doc.base.text
            assert self.tokenizer is not None
            all_text_processed = self.tokenizer(all_text)
            ent_id2ind, data = self.prepare_document(
                doc, input_ids=all_text_processed['input_ids'],
                offset_mapping=all_text_processed['offset_mapping'],
                lowercase=config.general.lowercase)
        else:
            # This means another model has already processed the data
            # and we can just use it. This is a
            # dangerous option - as it assumes the other model has the
            # same tokenizer and context size.
            data = []
            data.extend(doc.get_addon_data(_SHARE_TOKENS_PATH)[0])
        predictions, confidences = predict(
            self.model, data, config)

        ents = self.get_ents(doc)

        for ent in ents:
            ent_ind = ent_id2ind[ent.id]
            value = id2category_value[predictions[ent_ind]]
            confidence = confidences[ent_ind]
            if ent.get_addon_data(_META_ANNS_PATH) is None:
                ent.set_addon_data(_META_ANNS_PATH, {
                    config.general.category_name: {
                        'value': value,
                        'confidence': float(confidence),
                        'name': config.general.category_name
                    }
                }
                )
            else:
                ent.get_addon_data(_META_ANNS_PATH)[
                        config.general.category_name] = {
                    'value': value,
                    'confidence': float(confidence),
                    'name': config.general.category_name
                }
        return doc

    # Override
    def __call__(self, doc: MutableDocument) -> MutableDocument:
        """Process one document, used in the spacy pipeline for sequential
        document processing.

        Args:
            doc (Doc):
                A spacy document

        Returns:
            Doc: The same spacy document.
        """
        id2category_value = {
            v: k for k, v in self.config.general.category_value2id.items()}
        self._set_meta_anns(doc, id2category_value)
        return doc

    @overload
    def get_model_card(self, as_dict: Literal[True]) -> dict:
        pass

    @overload
    def get_model_card(self, as_dict: Literal[False]) -> str:
        pass

    def get_model_card(self, as_dict: bool = False) -> Union[str, dict]:
        """A minimal model card.

        Args:
            as_dict (bool):
                Return the model card as a dictionary instead of a str.
                Defaults to `False`.

        Returns:
            Union[str, dict]:
                An indented JSON object.
                OR A JSON object in dict form.
        """
        card = {
            'Category Name': self.config.general.category_name,
            'Description': self.config.general.description,
            'Classes': self.config.general.category_value2id,
            'Model': self.config.model.model_name
        }
        if as_dict:
            return card
        else:
            return json.dumps(card, indent=2, sort_keys=False)

    def __repr__(self):
        """Prints the model_card for this MetaCAT instance.

        Returns:
            the 'Model Card' for this MetaCAT instance. This includes NER+L
            config and any MetaCATs
        """
        return self.get_model_card(as_dict=False)


class MisconfiguredMetaCATException(ValueError):

    def ____(self, *args):
        super().__init__(*args)
