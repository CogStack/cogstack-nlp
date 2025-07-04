import os
import json
import logging
import datasets
import torch
from spacy.tokens import Doc
from datetime import datetime
from typing import Iterable, Iterator, Optional, Dict, List, cast, Union, Tuple, Callable, Type
from spacy.tokens import Span
import inspect
from functools import partial

from medcat.cdb import CDB
from medcat.utils.meta_cat.ml_utils import set_all_seeds
from medcat.datasets import transformers_ner
from medcat.utils.postprocessing import map_ents_to_groups, make_pretty_labels, create_main_ann, LabelStyle
from medcat.utils.hasher import Hasher
from medcat.config_transformers_ner import ConfigTransformersNER
from medcat.tokenizers.transformers_ner import TransformersTokenizerNER
from medcat.utils.ner.metrics import metrics
from medcat.datasets.data_collator import CollateAndPadNER

from transformers import Trainer, AutoModelForTokenClassification, AutoTokenizer
from transformers import pipeline, TrainingArguments
from transformers.trainer_callback import TrainerCallback

# It should be safe to do this always, as all other multiprocessing
#will be finished before data comes to meta_cat
os.environ["TOKENIZERS_PARALLELISM"] = "true"
os.environ['WANDB_DISABLED'] = 'true'


logger = logging.getLogger(__name__)


class TransformersNER(object):
    """TODO: Add documentation"""

    # Custom pipeline component name
    name = 'transformers_ner'

    def __init__(self, cdb, config: Optional[ConfigTransformersNER] = None,
                 training_arguments=None) -> None:
        self.cdb = cdb
        if config is None:
            config = ConfigTransformersNER()

        self.config = config
        set_all_seeds(config.general['seed'])

        self.model = AutoModelForTokenClassification.from_pretrained(config.general['model_name'])

        # Get the tokenizer either create a new one or load existing
        if os.path.exists(os.path.join(config.general['model_name'], 'tokenizer.dat')):
            self.tokenizer = TransformersTokenizerNER.load(os.path.join(config.general['model_name'], 'tokenizer.dat'))
        else:
            hf_tokenizer = AutoTokenizer.from_pretrained(self.config.general['model_name'])
            self.tokenizer = TransformersTokenizerNER(hf_tokenizer)

        if training_arguments is None:
            self.training_arguments = TrainingArguments(
                output_dir='./results',
                logging_dir='./logs',            # directory for storing logs
                num_train_epochs=10,              # total number of training epochs
                per_device_train_batch_size=1,  # batch size per device during training
                per_device_eval_batch_size=1,   # batch size for evaluation
                weight_decay=0.14,               # strength of weight decay
                warmup_ratio=0.01,
                learning_rate=4.47e-05, # Should be smaller when finetuning an existing deid model
                eval_accumulation_steps=1,
                gradient_accumulation_steps=4, # We want to get to bs=4
                do_eval=True,
                # eval_strategy over evaluation_strategy since trf==4.46 (apperently)
                eval_strategy='epoch', # type: ignore
                logging_strategy='epoch', # type: ignore
                save_strategy='epoch', # type: ignore
                metric_for_best_model='eval_recall', # Can be changed if our preference is not recall but precision or f1
                load_best_model_at_end=True,
                remove_unused_columns=False)
        else:
            self.training_arguments = training_arguments

    def create_eval_pipeline(self):

        if self.config.general['chunking_overlap_window'] is None:
            logger.warning("Chunking overlap window attribute in the config is set to None, hence chunking is disabled. Be cautious, PII data MAY BE REVEALED. To enable chunking, set the value to 0 or above.")
        self.ner_pipe = pipeline(model=self.model, task="ner", tokenizer=self.tokenizer.hf_tokenizer,stride=self.config.general['chunking_overlap_window'])
        if not hasattr(self.ner_pipe.tokenizer, '_in_target_context_manager'):
            # NOTE: this will fix the DeID model(s) created before medcat 1.9.3
            #       though this fix may very well be unstable
            self.ner_pipe.tokenizer._in_target_context_manager = False
        if not hasattr(self.ner_pipe.tokenizer, 'split_special_tokens'):
            # NOTE: this will fix the DeID model(s) created with transformers before 4.42
            #       and allow them to run with later transformers
            self.ner_pipe.tokenizer.split_special_tokens = False
        if not hasattr(self.ner_pipe.tokenizer, 'pad_token') and hasattr(self.ner_pipe.tokenizer, '_pad_token'):
            # NOTE: This will fix the DeID model(s) created with transformers before 4.47
            #       and allow them to run with later transformmers versions
            #       In 4.47 the special tokens started to be used differently, yet our saved model
            #       is not aware of that. So we need to explicitly fix that.
            special_tokens_map = self.ner_pipe.tokenizer.__dict__.get('_special_tokens_map', {})
            for name in self.ner_pipe.tokenizer.SPECIAL_TOKENS_ATTRIBUTES:
                # previously saved in (e.g) _pad_token
                prev_val = getattr(self.ner_pipe.tokenizer, f"_{name}")
                # now saved in the special tokens map by its name
                special_tokens_map[name] = prev_val
            # the map is saved in __dict__ explicitly, and it is later used in __getattr__ of the base class.
            self.ner_pipe.tokenizer.__dict__['_special_tokens_map'] = special_tokens_map

        self.ner_pipe.device = self.model.device
        self._consecutive_identical_failures = 0
        self._last_exception: Optional[Tuple[str, Type[Exception]]] = None

    def get_hash(self) -> str:
        """A partial hash trying to catch differences between models.

        Returns:
            str: The hex hash.
        """
        hasher = Hasher()
        # Set last_train_on if None
        if self.config.general.last_train_on is None:
            self.config.general.last_train_on = datetime.now().timestamp()

        hasher.update(self.config.get_hash())
        return hasher.hexdigest()

    def _prepare_dataset(self, json_path, ignore_extra_labels, meta_requirements, file_name='data.json'):
        def merge_data_loaded(base, other):
            if not base:
                return other
            elif other is None:
                return base
            else:
                for p in other['projects']:
                    base['projects'].append(p)
            return base

        if isinstance(json_path, str):
            json_path = [json_path]

        # Merge data from all different data paths
        data_loaded: Dict = {}
        for path in json_path:
            with open(path, 'r') as f:
                data_loaded = merge_data_loaded(data_loaded, json.load(f))

        # Remove labels that did not exist in old dataset
        if ignore_extra_labels and self.tokenizer.label_map:
            logger.info("Ignoring extra labels from the data")
            for p in data_loaded['projects']:
                for d in p['documents']:
                    new_anns = []
                    for a in d['annotations']:
                        if a['cui'] in self.tokenizer.label_map:
                            new_anns.append(a)
                    d['annotations'] = new_anns
        if meta_requirements is not None:
            logger.info("Removing anns that do not meet meta requirements")
            for p in data_loaded['projects']:
                for d in p['documents']:
                    new_anns = []
                    for a in d['annotations']:
                        if all([a['meta_anns'][name]['value'] == value for name, value in meta_requirements.items()]):
                            new_anns.append(a)
                    d['annotations'] = new_anns

        # Here we have to save the data because of the data loader
        os.makedirs('results', exist_ok=True)
        out_path = os.path.join(os.getcwd(), 'results', file_name)
        json.dump(data_loaded, open(out_path, 'w'))

        return out_path

    def train(self,
              json_path: Union[str, list, None]=None,
              ignore_extra_labels=False,
              dataset=None,
              meta_requirements=None,
              train_json_path: Union[str, list, None]=None,
              test_json_path: Union[str, list, None]=None,
              trainer_callbacks: Optional[List[Callable[[Trainer], TrainerCallback]]] = None) -> Tuple:
        """Train or continue training a model give a json_path containing a MedCATtrainer export. It will
        continue training if an existing model is loaded or start new training if the model is blank/new.

        Args:
            json_path (str or list):
                Path/Paths to a MedCATtrainer export containing the meta_annotations we want to train for.
            ignore_extra_labels:
                Makes only sense when an existing deid model was loaded and from the new data we want to ignore
                labels that did not exist in the old model.
            dataset: Defaults to None. Will be split by self.config.general['test_size'] into train and test datasets.
            meta_requirements: Defaults to None
            train_json_path (str): Defaults to None. If provided, will be used as the training dataset json_path to load from
            test_json_path (str): Defaults to None. If provided, will be used as the test dataset json_path to load from
            trainer_callbacks (List[Callable[[Trainer], TrainerCallback]]]):
                A list of trainer callbacks for collecting metrics during the training at the client side. The
                transformers Trainer object will be passed in when each callback is called.

        Raises:
            ValueError: If something went wrong with model save path.

        Returns:
            Tuple: The dataframe, examples, and the dataset
        """

        if dataset is None:
            # Load the medcattrainer export
            if json_path is not None:
                json_path = self._prepare_dataset(json_path, ignore_extra_labels=ignore_extra_labels,
                                              meta_requirements=meta_requirements, file_name='data_eval.json')
            elif test_json_path is not None and train_json_path is not None:
                train_json_path = self._prepare_dataset(train_json_path, ignore_extra_labels=ignore_extra_labels,
                                                meta_requirements=meta_requirements, file_name='data_train.json')
                test_json_path = self._prepare_dataset(test_json_path, ignore_extra_labels=ignore_extra_labels,
                                                meta_requirements=meta_requirements, file_name='data_test.json')

            # NOTE: The following is for backwards comppatibility
            #       in datasets==2.20.0 `trust_remote_code=True` must be explicitly
            #       specified, otherwise an error is raised.
            #       On the other hand, the keyword argument was added in datasets==2.16.0
            #       yet we support datasets>=2.2.0.
            #       So we need to use the kwarg if applicable and omit its use otherwise.
            if func_has_kwarg(datasets.load_dataset, 'trust_remote_code'):
                ds_load_dataset = partial(datasets.load_dataset, trust_remote_code=True)
            else:
                ds_load_dataset = datasets.load_dataset

            if json_path:
                dataset = ds_load_dataset(os.path.abspath(transformers_ner.__file__),
                                        data_files={'train': json_path}, # type: ignore
                                        split='train',
                                        cache_dir='/tmp/')
                # We split before encoding so the split is document level, as encoding
                # does the document splitting into max_seq_len
                dataset = dataset.train_test_split(test_size=self.config.general['test_size']) # type: ignore
            elif train_json_path and test_json_path:
                dataset = ds_load_dataset(os.path.abspath(transformers_ner.__file__),
                                          data_files={'train': train_json_path, 'test': test_json_path}, # type: ignore
                                          cache_dir='/tmp/')
            else:
                raise ValueError("Either json_path or train_json_path and test_json_path must be provided when no dataset is provided")

        # Update labelmap in case the current dataset has more labels than what we had before
        self.tokenizer.calculate_label_map(dataset['train'])
        self.tokenizer.calculate_label_map(dataset['test'])

        if self.model.num_labels != len(self.tokenizer.label_map):
            logger.warning("The dataset contains labels we've not seen before, model is being reinitialized")
            logger.warning("Model: {} vs Dataset: {}".format(self.model.num_labels, len(self.tokenizer.label_map)))
            self.model = AutoModelForTokenClassification.from_pretrained(self.config.general['model_name'],
                                                                         num_labels=len(self.tokenizer.label_map),
                                                                         ignore_mismatched_sizes=True)
            self.tokenizer.cui2name = {k:self.cdb.get_name(k) for k in self.tokenizer.label_map.keys()}

        self.model.config.id2label = {v:k for k,v in self.tokenizer.label_map.items()}
        self.model.config.label2id = self.tokenizer.label_map


        # Encode dataset
        # Note: tokenizer.encode performs chunking
        encoded_dataset = dataset.map(
                lambda examples: self.tokenizer.encode(examples, ignore_subwords=False),
                batched=True,
                remove_columns=['ent_cuis', 'ent_ends', 'ent_starts', 'text'])

        data_collator = CollateAndPadNER(self.tokenizer.hf_tokenizer.pad_token_id) # type: ignore
        trainer = Trainer(
                model=self.model,
                args=self.training_arguments,
                train_dataset=encoded_dataset['train'],
                eval_dataset=encoded_dataset['test'],
                compute_metrics=lambda p: metrics(p, tokenizer=self.tokenizer, dataset=encoded_dataset['test'], verbose=self.config.general['verbose_metrics']),
                data_collator=data_collator, # type: ignore
                tokenizer=None)
        if trainer_callbacks:
            for callback in trainer_callbacks:
                # No idea why mypy isn't picking up the method.
                # It most certainly does exist
                trainer.add_callback(callback(trainer))  # type: ignore

        trainer.train() # type: ignore

        # Save the training time
        self.config.general.last_train_on = datetime.now().timestamp() # type: ignore

        # Save everything
        output_dir = self.training_arguments.output_dir
        if output_dir is None:
            # NOTE: this shouldn't really happen, but we'll do this for type safety
            raise ValueError("Output path should not be None!")
        self.save(save_dir_path=os.path.join(output_dir, 'final_model'))
        # Run an eval step and return metrics
        p = trainer.predict(encoded_dataset['test']) # type: ignore
        df, examples = metrics(p, return_df=True, tokenizer=self.tokenizer, dataset=encoded_dataset['test'])


        # Create the pipeline for eval
        self.create_eval_pipeline()

        return df, examples, dataset

    def eval(self, json_path: Union[str, list, None] = None, dataset=None, ignore_extra_labels=False, meta_requirements=None):
        if dataset is None:
            json_path = self._prepare_dataset(json_path, ignore_extra_labels=ignore_extra_labels,
                                              meta_requirements=meta_requirements, file_name='data_eval.json')
            # Load dataset
            dataset = datasets.load_dataset(os.path.abspath(transformers_ner.__file__),
                                            data_files={'train': json_path}, # type: ignore
                                            split='train',
                                            cache_dir='/tmp/')

        # Encode dataset
        # Note: tokenizer.encode performs chunking
        encoded_dataset = dataset.map(
                lambda examples: self.tokenizer.encode(examples, ignore_subwords=False),
                batched=True,
                remove_columns=['ent_cuis', 'ent_ends', 'ent_starts', 'text'])

        data_collator = CollateAndPadNER(self.tokenizer.hf_tokenizer.pad_token_id) # type: ignore
        # TODO: switch from trainer to model prediction
        trainer = Trainer(
                model=self.model,
                args=self.training_arguments,
                train_dataset=None,
                eval_dataset=encoded_dataset, # type: ignore
                compute_metrics=None,
                data_collator=data_collator, # type: ignore
                tokenizer=None)

        # Run an eval step and return metrics
        p = trainer.predict(encoded_dataset) # type: ignore
        df, examples = metrics(p, return_df=True, tokenizer=self.tokenizer, dataset=encoded_dataset)

        return df, examples, dataset

    def save(self, save_dir_path: str) -> None:
        """Save all components of this class to a file

        Args:
            save_dir_path(str):
                Path to the directory where everything will be saved.
        """
        # Create dirs if they do not exist
        os.makedirs(save_dir_path, exist_ok=True)

        # Save tokenizer
        self.tokenizer.save(os.path.join(save_dir_path, 'tokenizer.dat'))

        # Save config
        self.config.save(os.path.join(save_dir_path, 'cat_config.json'))

        # Save the model
        self.model.save_pretrained(save_dir_path)

        # Save the cdb
        self.cdb.save(os.path.join(save_dir_path, 'cdb.dat'))

        # This is everything we need to save from the class, we do not
        #save the class itself.

    def expand_model_with_concepts(self, cui2preferred_name: Dict[str, str], use_avg_init: bool = True) -> None:
        """Expand the model with new concepts and their preferred names, which requires subsequent retraining on the model.

        Args:
            cui2preferred_name(Dict[str, str]):
                Dictionary where each key is the literal ID of the concept to be added and each value is its preferred name.
            use_avg_init(bool):
                Whether to use the average of existing weights or biases as the initial value for the new concept. Defaults to True.
        """

        avg_weight = torch.mean(self.model.classifier.weight, dim=0, keepdim=True)
        avg_bias = torch.mean(self.model.classifier.bias, dim=0, keepdim=True)

        new_cuis = set()
        for label, preferred_name in cui2preferred_name.items():
            if label in self.model.config.label2id.keys():
                logger.warning("Concept ID '%s' already exists in the model, skipping...", label)
                continue

            sname = preferred_name.lower().replace(" ", "~")
            new_names = {
                sname: {
                    "tokens": [],
                    "snames": [sname],
                    "raw_name": preferred_name,
                    "is_upper": True
                }
            }
            self.cdb.add_names(cui=label, names=new_names, name_status="P", full_build=True)

            new_label_id = sorted(self.model.config.label2id.values())[-1] + 1
            self.model.config.label2id[label] = new_label_id
            self.model.config.id2label[new_label_id] = label
            self.tokenizer.label_map[label] = new_label_id
            self.tokenizer.cui2name = {k: self.cdb.get_name(k) for k in self.tokenizer.label_map.keys()}

            if use_avg_init:
                self.model.classifier.weight = torch.nn.Parameter(
                    torch.cat((self.model.classifier.weight, avg_weight), 0)
                )
                self.model.classifier.bias = torch.nn.Parameter(
                    torch.cat((self.model.classifier.bias, avg_bias), 0)
                )
            else:
                self.model.classifier.weight = torch.nn.Parameter(
                    torch.cat((self.model.classifier.weight, torch.randn(1, self.model.config.hidden_size)), 0)
                )
                self.model.classifier.bias = torch.nn.Parameter(
                    torch.cat((self.model.classifier.bias, torch.randn(1)), 0)
                )
            self.model.num_labels += 1
            self.model.classifier.out_features += 1

            new_cuis.add(label)

        logger.info("Model expanded with the new concept(s): %s and shall be retrained before use.", str(new_cuis))

    @classmethod
    def load(cls, save_dir_path: str, config_dict: Optional[Dict] = None) -> "TransformersNER":
        """Load a meta_cat object.

        Args:
            save_dir_path (str):
                The directory where all was saved.
            config_dict (dict):
                This can be used to overwrite saved parameters for this meta_cat
                instance. Why? It is needed in certain cases where we autodeploy stuff.

        Returns:
            meta_cat (`medcat.MetaCAT`):
                You don't say
        """

        # Load config
        config = cast(ConfigTransformersNER, ConfigTransformersNER.load(os.path.join(save_dir_path, 'cat_config.json')))
        config.general['model_name'] = save_dir_path

        # Overwrite loaded parameters with something new
        if config_dict is not None:
            config.merge_config(config_dict)

        # Load cdb
        cdb = CDB.load(os.path.join(save_dir_path, 'cdb.dat'))

        ner = cls(cdb=cdb, config=config)
        ner.create_eval_pipeline()

        return ner

    @staticmethod
    def batch_generator(stream: Iterable[Doc], batch_size_chars: int) -> Iterable[List[Doc]]:
        docs = []
        char_count = 0
        for doc in stream:
            char_count += len(doc.text)
            docs.append(doc)
            if char_count < batch_size_chars:
                continue
            yield docs
            docs = []
            char_count = 0

        # If there is anything left return that also
        if len(docs) > 0:
            yield docs

    def pipe(self, stream: Iterable[Union[Doc, None]], *args, **kwargs) -> Iterator[Doc]:
        """Process many documents at once.

        Args:
            stream (Iterable[spacy.tokens.Doc]):
                List of spacy documents.
            *args: Extra arguments (not used here).
            **kwargs: Extra keyword arguments (not used here).

        Yields:
            Doc: The same document.

        Returns:
            Iterator[Doc]: If the stream is None or empty.
        """
        # Just in case
        if stream is None or not stream:
            # return an empty generator
            return

        batch_size_chars = self.config.general['pipe_batch_size_in_chars']
        yield from self._process(stream, batch_size_chars)  # type: ignore

    def _process(self,
                 stream: Iterable[Union[Doc, None]],
                 batch_size_chars: int) -> Iterator[Optional[Doc]]:
        for docs in self.batch_generator(stream, batch_size_chars):  # type: ignore
            #all_text = [doc.text for doc in docs]
            #all_text_processed = self.tokenizer.encode_eval(all_text)
            # For now we will process the documents one by one, should be improved in the future to use batching
            for doc in docs:
                res = self.ner_pipe(doc.text, aggregation_strategy=self.config.general['ner_aggregation_strategy'])
                doc.ents = []  # type: ignore
                for r in res:
                    inds = []
                    for ind, word in enumerate(doc):
                        end_char = word.idx + len(word.text)
                        if end_char <= r['end'] and end_char > r['start']:
                            inds.append(ind)
                        # To not loop through everything
                        if end_char > r['end']:
                            break
                    if inds:
                        entity = Span(doc, min(inds), max(inds) + 1, label=r['entity_group'])
                        entity._.cui = r['entity_group']
                        entity._.context_similarity = r['score']
                        entity._.detected_name = r['word']
                        entity._.id = len(doc._.ents)
                        entity._.confidence = r['score']

                        doc._.ents.append(entity)
                create_main_ann(self.cdb, doc)
                if self.cdb.config.general['make_pretty_labels'] is not None:
                    make_pretty_labels(self.cdb, doc, LabelStyle[self.cdb.config.general['make_pretty_labels']])
                if self.cdb.config.general['map_cui_to_group'] is not None and self.cdb.addl_info.get('cui2group', {}):
                    map_ents_to_groups(self.cdb, doc)
                self._consecutive_identical_failures = 0  # success
                self._last_exception = None
            yield from docs

    # Override
    def __call__(self, doc: Doc) -> Doc:
        """Process one document, used in the spacy pipeline for sequential
        document processing.

        Args:
            doc (Doc):
                A spacy document

        Returns:
            Doc: The same spacy document.
        """

        # Just call the pipe method
        doc = next(self.pipe(iter([doc])))

        return doc


# NOTE: Only needed for datasets backwards compatibility
def func_has_kwarg(func: Callable, keyword: str):
    sig = inspect.signature(func)
    return keyword in sig.parameters
