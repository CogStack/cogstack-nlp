import os
import json
import logging
import numpy
from multiprocessing import Lock
from datetime import datetime
from typing import Iterable, Optional, cast, Union, Any, TypedDict

from medcat2.utils.hasher import Hasher

import torch
from torch import nn, Tensor
from medcat2.tokenizing.tokenizers import BaseTokenizer
from medcat2.config.config_meta_cat import ConfigMetaCAT
from medcat2.components.addons.meta_cat.ml_utils import (
    predict, train_model, set_all_seeds, eval_model)
from medcat2.components.addons.meta_cat.data_utils import (
    prepare_from_json, encode_category_values, prepare_for_oversampled_data)
from medcat2.components.addons.addons import AddonComponent, register_addon
from medcat2.components.addons.meta_cat.meta_cat_tokenizers import (
    TokenizerWrapperBase)
from medcat2.storage.serialisers import serialise, deserialise
from medcat2.storage.serialisables import AbstractSerialisable
from medcat2.tokenizing.tokens import MutableDocument, MutableEntity
from medcat2.cdb import CDB
from medcat2.vocab import Vocab
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


class MetaCATAddon(AddonComponent):
    addon_type = 'meta_cat'
    output_key = 'meta_anns'
    config: ConfigMetaCAT

    def __init__(self, cnf: ConfigMetaCAT, base_tokenizer: BaseTokenizer,
                 model_load_path: Optional[str],
                 tokenizer: Optional[TokenizerWrapperBase] = None):
        self.base_tokenizer = base_tokenizer
        self._name = cnf.general.category_name
        # NOTE: if tokenizer (Optional[TokenizerWrapperBase]) is provided
        #       this is probably a new MetaCAT being created
        #       otherwise, it should be loaded off disk
        if tokenizer is None and model_load_path is None:
            tokenizer = self._init_tokenizer(
                cnf, model_load_path)
        if tokenizer is None and model_load_path is None:
            raise MisconfiguredMetaCATException(
                "When initialising a MetaCAT, neither model load path nor "
                "a tokenizer was provided. If loading off disk, the model "
                "load path would be expected; when creating a new one, the "
                "tokenizer should be provided"
            )
        self.config = cnf
        if model_load_path is None:
            self.mc = MetaCAT(tokenizer, embeddings=None, config=cnf)
        else:
            self.mc = self.load(os.path.join(model_load_path,
                                             self.get_folder_name()))
        self._init_data_paths()

    @property
    def name(self) -> Optional[str]:
        return self._name

    def _init_tokenizer(self, cnf: ConfigMetaCAT, pack_save_path: Optional[str]
                        ) -> Optional[TokenizerWrapperBase]:
        # TODO / use registry and load with that
        if pack_save_path is not None:
            model_save_path = os.path.join(
                pack_save_path, self.get_folder_name())
        else:
            raise MisconfiguredMetaCATException(
                "Failed to load MetaCAT tokenizer without model pack path. "
                "When creating a new MetaCAT, please provide a tokenizer.")
        tokenizer: Optional[TokenizerWrapperBase] = None
        if cnf.general.tokenizer_name == 'bbpe':
            from medcat2.components.addons.meta_cat.meta_cat_tokenizers import (  # noqa
                TokenizerWrapperBPE)
            tokenizer = TokenizerWrapperBPE.load(model_save_path)
        elif cnf.general.tokenizer_name == 'bert-tokenizer':
            from medcat2.components.addons.meta_cat.meta_cat_tokenizers import (  # noqa
                TokenizerWrapperBERT)
            tokenizer = TokenizerWrapperBERT.load(model_save_path,
                                                  cnf.model.model_variant)
        return tokenizer

    def __call__(self, doc: MutableDocument) -> MutableDocument:
        return self.mc(doc)

    @classmethod
    def get_init_args(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                      model_load_path: Optional[str]) -> list[Any]:
        # NOTE: cnf is silent init parameter
        return [tokenizer, model_load_path]

    @classmethod
    def get_init_kwargs(cls, tokenizer: BaseTokenizer, cdb: CDB, vocab: Vocab,
                        model_load_path: Optional[str]) -> dict[str, Any]:
        return {}

    @property
    def should_save(self) -> bool:
        return True

    def load(self, folder_path: str) -> 'MetaCAT':
        mc_path, tokenizer_folder = self._get_meta_cat_and_tokenizer_paths(
            folder_path)
        mc = cast(MetaCAT, deserialise(mc_path))
        tokenizer: Optional[TokenizerWrapperBase] = None
        if self.config.general.tokenizer_name == 'bbpe':
            from medcat2.components.addons.meta_cat.meta_cat_tokenizers import (  # noqa
                TokenizerWrapperBPE)
            tokenizer = TokenizerWrapperBPE.load(tokenizer_folder)
        elif self.config.general.tokenizer_name == 'bert-tokenizer':
            from medcat2.components.addons.meta_cat.meta_cat_tokenizers import (  # noqa
                TokenizerWrapperBERT)
            tokenizer = TokenizerWrapperBERT.load(
                tokenizer_folder, self.config.model.model_variant)
        mc.tokenizer = tokenizer
        return mc

    def _get_meta_cat_and_tokenizer_paths(self, folder_path: str
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

    def _init_data_paths(self):
        # a dictionary like {category_name: value, ...}
        self.base_tokenizer.get_entity_class().register_addon_path(
            _META_ANNS_PATH, def_val=None, force=True)
        # Used for sharing pre-processed data/tokens
        self.base_tokenizer.get_doc_class().register_addon_path(
            _SHARE_TOKENS_PATH, def_val=None, force=True)

    @property
    def include_in_output(self) -> bool:
        return True

    def get_output_key_val(self, ent: MutableEntity
                           ) -> tuple[str, dict[str, Any]]:
        # NOTE: In case of multiple MetaCATs, this will be called
        #       once for each MetaCAT and will get the same value.
        #       But it shouldn't be too much of an issue.
        return self.output_key, ent.get_addon_data(_META_ANNS_PATH)


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
        return ['base_tokenizer', 'model']

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
                 _model_state_dict: Optional[dict[str, Any]] = None) -> None:
        if config is None:
            config = ConfigMetaCAT()
        self.config = config
        set_all_seeds(config.general.seed)

        if tokenizer is not None:
            # Set it in the config
            config.general.tokenizer_name = tokenizer.name
            config.general.vocab_size = tokenizer.get_size()
            # We will also set the padding
            config.model.padding_idx = cast(int, tokenizer.get_pad_id())
        self.tokenizer = tokenizer

        self.embeddings = (torch.tensor(
            embeddings, dtype=torch.float32) if embeddings is not None
            else None)
        self.model = self.get_model(embeddings=self.embeddings)
        if _model_state_dict:
            self.model.load_state_dict(_model_state_dict)

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
            from medcat2.components.addons.meta_cat.models import LSTM
            model: nn.Module = LSTM(embeddings, config)
            logger.info("LSTM model used for classification")

        elif config.model.model_name == 'bert':
            from medcat2.components.addons.meta_cat.models import (
                BertForMetaAnnotation)
            model = BertForMetaAnnotation(config)

            if not config.model.model_freeze_layers:
                peft_config = LoraConfig(
                    task_type=TaskType.SEQ_CLS, inference_mode=False, r=8,
                    lora_alpha=16, target_modules=["query", "value"],
                    lora_dropout=0.2)

                model = get_peft_model(model, peft_config)
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
        category_name = g_config.category_name
        if category_name not in data_in:
            raise Exception(
                "The category name does not exist in this json file. "
                f"You've provided '{category_name}', while the possible "
                f"options are: {' | '.join(list(data_in.keys()))}")

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
                 category_undersample=self.config.model.category_undersample)
            g_config.category_value2id = category_value2id
        else:
            # We already have everything, just get the data
            (full_data, data_undersampled,
             category_value2id) = encode_category_values(
                 data, existing_category_value2id=category_value2id,
                 category_undersample=self.config.model.category_undersample)
            g_config.category_value2id = category_value2id
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
                logger.info(
                    "Model state loaded from dict for 2 phase learning")

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
        category_name = g_config.category_name
        if category_name not in data_in:
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
        return doc.all_ents  # TODO: is this correct?

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


# NOTE: register as soon as this is imported
register_addon(MetaCATAddon.addon_type, MetaCATAddon)
