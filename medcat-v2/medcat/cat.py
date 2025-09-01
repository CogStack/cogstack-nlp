from typing import Optional, Union, Any, overload, Literal, Iterable, Iterator
from typing import cast, Type, TypeVar
import os
import json
from datetime import date
from concurrent.futures import ProcessPoolExecutor, as_completed, Future
import itertools
from contextlib import contextmanager

import shutil
import zipfile
import logging

from medcat.utils.defaults import DEFAULT_PACK_NAME, COMPONENTS_FOLDER
from medcat.cdb import CDB
from medcat.vocab import Vocab
from medcat.config.config import Config, get_important_config_parameters
from medcat.trainer import Trainer
from medcat.storage.serialisers import serialise, AvailableSerialisers
from medcat.storage.serialisers import deserialise
from medcat.storage.serialisables import AbstractSerialisable
from medcat.storage.mp_ents_save import BatchAnnotationSaver
from medcat.utils.fileutils import ensure_folder_if_parent
from medcat.utils.hasher import Hasher
from medcat.pipeline import Pipeline
from medcat.tokenizing.tokens import MutableDocument, MutableEntity
from medcat.tokenizing.tokenizers import SaveableTokenizer, TOKENIZER_PREFIX
from medcat.data.entities import Entity, Entities, OnlyCUIEntities
from medcat.data.model_card import ModelCard
from medcat.components.types import AbstractCoreComponent, HashableComponet
from medcat.components.addons.addons import AddonComponent
from medcat.utils.legacy.identifier import is_legacy_model_pack
from medcat.utils.defaults import avoid_legacy_conversion
from medcat.utils.defaults import doing_legacy_conversion_message
from medcat.utils.defaults import LegacyConversionDisabledError
from medcat.utils.usage_monitoring import UsageMonitor, _NoDelUM
from medcat.utils.import_utils import MissingDependenciesError


logger = logging.getLogger(__name__)


AddonType = TypeVar("AddonType", bound="AddonComponent")


class CAT(AbstractSerialisable):
    """This is a collection of serialisable model parts.
    """
    FORCE_SPAWN_MP = True

    def __init__(self,
                 cdb: CDB,
                 vocab: Union[Vocab, None] = None,
                 config: Optional[Config] = None,
                 model_load_path: Optional[str] = None,
                 config_dict: Optional[dict] = None,
                 addon_config_dict: Optional[dict[str, dict]] = None,
                 ) -> None:
        self.cdb = cdb
        self.vocab = vocab
        # ensure  config
        if config is None and self.cdb.config is None:
            raise ValueError("Need to specify a config for either CDB or CAT")
        elif config is None:
            config = cdb.config
        elif config is not None:
            self.cdb.config = config
        self.config = config
        if config_dict:
            self.config.merge_config(config_dict)

        self._trainer: Optional[Trainer] = None
        self._pipeline = self._recreate_pipe(model_load_path, addon_config_dict)
        self.usage_monitor = UsageMonitor(
            self._get_hash, self.config.general.usage_monitor)

    def _recreate_pipe(self, model_load_path: Optional[str] = None,
                       addon_config_dict: Optional[dict[str, dict]] = None,
                       ) -> Pipeline:
        if hasattr(self, "_pipeline"):
            old_pipe = self._pipeline
        else:
            old_pipe = None
        self._pipeline = Pipeline(self.cdb, self.vocab, model_load_path,
                                  old_pipe=old_pipe,
                                  addon_config_dict=addon_config_dict)
        return self._pipeline

    @property
    def pipe(self) -> Pipeline:
        return self._pipeline

    @classmethod
    def get_init_attrs(cls) -> list[str]:
        return ['cdb', 'vocab']

    @classmethod
    def ignore_attrs(cls) -> list[str]:
        return [
            '_trainer',  # recreate if nededed
            '_pipeline',  # need to recreate regardless
            'config',  # will be loaded along with CDB
            'usage_monitor',  # will be created at startup
        ]

    def __call__(self, text: str) -> Optional[MutableDocument]:
        doc = self._pipeline.get_doc(text)
        if self.usage_monitor.should_monitor:
            self.usage_monitor.log_inference(len(text), len(doc.linked_ents))
        return doc

    def _ensure_not_training(self) -> None:
        """Method to ensure config is not set to train.

        `config.components.linking.train` should only be True while training
        and not during inference.
        This aalso corrects the setting if necessary.
        """
        # pass
        if self.config.components.linking.train:
            logger.warning("Training was enabled during inference. "
                           "It was automatically disabled.")
            self.config.components.linking.train = False

    @overload
    def get_entities(self,
                     text: str,
                     only_cui: Literal[False] = False,
                     # TODO : addl_info
                     ) -> Entities:
        pass

    @overload
    def get_entities(self,
                     text: str,
                     only_cui: Literal[True] = True,
                     # TODO : addl_info
                     ) -> OnlyCUIEntities:
        pass

    @overload
    def get_entities(self,
                     text: str,
                     only_cui: bool = False,
                     # TODO : addl_info
                     ) -> Union[dict, Entities, OnlyCUIEntities]:
        pass

    def get_entities(self,
                     text: str,
                     only_cui: bool = False,
                     # TODO : addl_info
                     ) -> Union[dict, Entities, OnlyCUIEntities]:
        """Get the entities recognised and linked within the provided text.

        This will run the text through the pipeline and annotated the
        recognised and linked entities.

        Args:
            text (str): The text to use.
            only_cui (bool, optional): Whether to only output the CUIs
                rather than the entire context. Defaults to False.

        Returns:
            Union[dict, Entities, OnlyCUIEntities]: The entities found and
                linked within the text.
        """
        self._ensure_not_training()
        doc = self(text)
        if not doc:
            return {}
        return self._doc_to_out(doc, only_cui=only_cui)

    def _mp_worker_func(
            self,
            texts_and_indices: list[tuple[str, str, bool]]
            ) -> list[tuple[str, Union[dict, Entities, OnlyCUIEntities]]]:
        # NOTE: this is needed for subprocess as otherwise they wouldn't have
        #       any of these set
        # NOTE: these need to by dynamic in case the extra's aren't included
        try:
            from medcat.components.addons.meta_cat import MetaCATAddon
            has_meta_cat = True
        except MissingDependenciesError:
            has_meta_cat = False
        try:
            from medcat.components.addons.relation_extraction.rel_cat import (
                RelCATAddon)
            has_rel_cat = True
        except MissingDependenciesError:
            has_rel_cat = False
        for addon in self._pipeline.iter_addons():
            if has_meta_cat and isinstance(addon, MetaCATAddon):
                addon._init_data_paths(self._pipeline.tokenizer)
            elif has_rel_cat and isinstance(addon, RelCATAddon):
                addon._rel_cat._init_data_paths()
        return [
            (text_index, self.get_entities(text, only_cui=only_cui))
            for text, text_index, only_cui in texts_and_indices]

    def _generate_batches_by_char_length(
            self,
            text_iter: Union[Iterator[str], Iterator[tuple[str, str]]],
            batch_size_chars: int,
            only_cui: bool,
            ) -> Iterator[list[tuple[str, str, bool]]]:
        docs: list[tuple[str, str, bool]] = []
        char_count = 0
        for i, _doc in enumerate(text_iter):
            # NOTE: not sure why mypy is complaining here
            doc = cast(
                str, _doc[1] if isinstance(_doc, tuple) else _doc)
            doc_index: str = _doc[0] if isinstance(_doc, tuple) else str(i)
            clen = len(doc)
            char_count += clen
            if char_count > batch_size_chars:
                yield docs
                docs = []
                char_count = clen
            docs.append((doc, doc_index, only_cui))

        if len(docs) > 0:
            yield docs

    def _generate_batches(
            self,
            text_iter: Union[Iterator[str], Iterator[tuple[str, str]]],
            batch_size: int,
            batch_size_chars: int,
            only_cui: bool,
            ) -> Iterator[list[tuple[str, str, bool]]]:
        if batch_size_chars < 1 and batch_size < 1:
            raise ValueError("Either `batch_size` or `batch_size_chars` "
                             "must be greater than 0.")
        if batch_size > 0 and batch_size_chars > 0:
            raise ValueError(
                "Cannot specify both `batch_size` and `batch_size_chars`. "
                "Please use one of them.")
        if batch_size_chars > 0:
            return self._generate_batches_by_char_length(
                text_iter, batch_size_chars, only_cui)
        else:
            return self._generate_simple_batches(
                text_iter, batch_size, only_cui)

    def _generate_simple_batches(
            self,
            text_iter: Union[Iterator[str], Iterator[tuple[str, str]]],
            batch_size: int,
            only_cui: bool,
            ) -> Iterator[list[tuple[str, str, bool]]]:
        text_index = 0
        while True:
            # Take a small batch from the iterator
            batch = list(itertools.islice(text_iter, batch_size))
            if not batch:
                break
            # NOTE: typing is correct:
            #        - if str, then (str, int, bool)
            #        - if tuple, then (str, int, bool)
            #       but for some reason mypy complains
            yield [
                (text, str(text_index + i), only_cui)  # type: ignore
                if isinstance(text, str) else
                (text[1], text[0], only_cui)
                for i, text in enumerate(batch)
            ]
            text_index += len(batch)

    def _mp_one_batch_per_process(
            self,
            executor: ProcessPoolExecutor,
            batch_iter: Iterator[list[tuple[str, str, bool]]],
            external_processes: int,
            saver: Optional[BatchAnnotationSaver],
            ) -> Iterator[tuple[str, Union[dict, Entities, OnlyCUIEntities]]]:
        futures: list[Future] = []
        # submit batches, one for each external processes
        for _ in range(external_processes):
            try:
                batch = next(batch_iter)
                futures.append(
                    executor.submit(self._mp_worker_func, batch))
            except StopIteration:
                break
        if not futures:
            # NOTE: if there wasn't any data, we didn't process anything
            raise OutOfDataException()
        # Main process works on next batch while workers are busy
        main_batch: Optional[list[tuple[str, str, bool]]]
        try:
            main_batch = next(batch_iter)
            main_results = self._mp_worker_func(main_batch)
            if saver:
                saver(main_results)
            # Yield main process results immediately
            yield from main_results

        except StopIteration:
            main_batch = None
        # since the main process did around the same amount of work
        # we would expect all subprocess to have finished by now
        # so we're going to wait for them to finish, yield their results,
        # and subsequently submit the next batch to keep them busy
        for _ in range(external_processes):
            if not futures:
                # NOTE: if there's no futures then there can't be
                #       anything to batch
                break
            # Wait for any future to complete
            done_future = next(as_completed(futures))
            futures.remove(done_future)

            cur_results = done_future.result()
            if saver:
                saver(cur_results)

            # Yield all results from this batch
            yield from cur_results

    def get_entities_multi_texts(
            self,
            texts: Union[Iterable[str], Iterable[tuple[str, str]]],
            only_cui: bool = False,
            n_process: int = 1,
            batch_size: int = -1,
            batch_size_chars: int = 1_000_000,
            save_dir_path: Optional[str] = None,
            batches_per_save: int = 20,
            ) -> Iterator[tuple[str, Union[dict, Entities, OnlyCUIEntities]]]:
        """Get entities from multiple texts (potentially in parallel).

        If `n_process` > 1, `n_process - 1` new processes will be created
        and data will be processed on those as well as the main process in
        parallel.

        Args:
            texts (Union[Iterable[str], Iterable[tuple[str, str]]]):
                The input text. Either an iterable of raw text or one
                with in the format of `(text_index, text)`.
            only_cui (bool):
                Whether to only return CUIs rather than other information
                like start/end and annotated value. Defaults to False.
            n_process (int):
                Number of processes to use. Defaults to 1.
            batch_size (int):
                The number of texts to batch at a time. A batch of the
                specified size will be given to each worker process.
                Defaults to -1 and in this case the character count will
                be used instead.
            batch_size_chars (int):
                The maximum number of characters to process in a batch.
                Each process will be given batch of texts with a total
                number of characters not exceeding this value. Defaults
                to 1,000,000 characters. Set to -1 to disable.
            save_dir_path (Optional[str]):
                The path to where (if specified) the results are saved.
                The directory will have a `annotated_ids.pickle` file
                containing the tuple[list[str], int] with a list of
                indices already saved and then umber of parts already saved.
                In addition there will be (usually multuple) files in the
                `part_<num>.pickle` format with the partial outputs.
            batches_per_save (int):
                The number of patches to save (if `save_dir_path` is specified)
                at once. Defaults to 20.

        Yields:
            Iterator[tuple[str, Union[dict, Entities, OnlyCUIEntities]]]:
                The results in the format of (text_index, entities).
        """
        text_iter = cast(
            Union[Iterator[str], Iterator[tuple[str, str]]], iter(texts))
        batch_iter = self._generate_batches(
            text_iter, batch_size, batch_size_chars, only_cui)
        if save_dir_path:
            saver = BatchAnnotationSaver(save_dir_path, batches_per_save)
        else:
            saver = None
        if n_process == 1:
            # just do in series
            for batch in batch_iter:
                batch_results = self._mp_worker_func(batch)
                if saver is not None:
                    saver(batch_results)
                yield from batch_results
            if saver:
                # save remainder
                saver._save_cache()
            return

        with self._no_usage_monitor_exit_flushing():
            yield from self._multiprocess(n_process, batch_iter, saver)
        if saver:
            # save remainder
            saver._save_cache()

    @contextmanager
    def _no_usage_monitor_exit_flushing(self):
        # NOTE: the `UsageMonitor.__del__` method can cause
        #       multiprocessing to stall while it waits for it to be
        #       called. So here we remove the method.
        #       However, due to the object being pickled for multiprocessing
        #       purposes, the class'es `__del__` method will be used anyway.
        #       So we need to trick it into using a different class.
        original_cls = self.usage_monitor.__class__
        self.usage_monitor.__class__ = _NoDelUM
        try:
            yield
        finally:
            self.usage_monitor.__class__ = original_cls

    def _multiprocess(
            self, n_process: int,
            batch_iter: Iterator[list[tuple[str, str, bool]]],
            saver: Optional[BatchAnnotationSaver],
            ) -> Iterator[tuple[str, Union[dict, Entities, OnlyCUIEntities]]]:
        external_processes = n_process - 1
        if self.FORCE_SPAWN_MP:
            import multiprocessing as mp
            logger.info(
                "Forcing multiprocessing start method to 'spawn' "
                "due to known compatibility issues with 'fork' and "
                "libraries using threads or native extensions.")
            mp.set_start_method("spawn", force=True)
        with ProcessPoolExecutor(max_workers=external_processes) as executor:
            while True:
                try:
                    yield from self._mp_one_batch_per_process(
                        executor, batch_iter, external_processes, saver=saver)
                except OutOfDataException:
                    break

    def _get_entity(self, ent: MutableEntity,
                    doc_tokens: list[str],
                    cui: str) -> Entity:
        context_left = self.config.annotation_output.context_left
        context_right = self.config.annotation_output.context_right

        if context_left > 0 and context_right > 0:
            left_s = max(ent.base.start_index - context_left, 0)
            left_e = ent.base.start_index
            left_context = doc_tokens[left_s:left_e]
            right_s = ent.base.end_index
            right_e = min(ent.base.end_index + context_right, len(doc_tokens))
            right_context = doc_tokens[right_s:right_e]
            ent_s, ent_e = ent.base.start_index, ent.base.end_index
            center_context = doc_tokens[ent_s:ent_e]
        else:
            left_context = []
            right_context = []
            center_context = []

        # NOTE: in case the CUI is not in the CDB, we don't want to fail here
        def_ci: dict[str, list[str]] = {'type_ids': []}
        out_dict: Entity = {
            'pretty_name': self.cdb.get_name(cui),
            'cui': cui,
            'type_ids': list(self.cdb.cui2info.get(cui, def_ci)['type_ids']),
            'source_value': ent.base.text,
            'detected_name': str(ent.detected_name),
            'acc': ent.context_similarity,
            'context_similarity': ent.context_similarity,
            'start': ent.base.start_char_index,
            'end': ent.base.end_char_index,
            # TODO: add additional info (i.e mappings)
            # for addl in addl_info:
            #     tmp = self.cdb.addl_info.get(addl, {}).get(cui, [])
            #     out_ent[addl.split("2")[-1]] = list(tmp) if type(tmp) is
            # set else tmp
            'id': ent.id,
            # TODO: add met annotations
            # if hasattr(ent._, 'meta_anns') and ent._.meta_anns:
            #     out_ent['meta_anns'] = ent._.meta_anns
            'meta_anns': {},
            'context_left': left_context,
            'context_center': center_context,
            'context_right': right_context,
        }
        # addons:
        out_dict.update(self.get_addon_output(ent))  # type: ignore
        return out_dict

    def get_addon_output(self, ent: MutableEntity) -> dict[str, dict]:
        """Get the addon output for the entity.

        This includes a key-value pair for each addon that provides some.
        Sometimes same-type addons may combine their output under the same key.

        Args:
            ent (MutableEntity): The entity in quesiton.

        Raises:
            ValueError: If unable to merge multiple addon output.

        Returns:
            dict[str, dict]: All the addon output.
        """
        out_dict: dict[str, dict] = {}
        for addon in self._pipeline._addons:
            if not addon.include_in_output:
                continue
            key, val = addon.get_output_key_val(ent)
            if key in out_dict:
                # e.g multiple meta_anns types
                # NOTE: type-ignore due to the strict TypedDict implementation
                cur_val = out_dict[key]  # type: ignore
                if not isinstance(cur_val, dict):
                    raise ValueError(
                        "Unable to merge multiple addon output for the same "
                        f" key. Tried to update '{key}'. Previously had "
                        f"{cur_val}, got {val} from addon {addon.full_name}")
                cur_val.update(val)
            else:
                # NOTE: type-ignore due to the strict TypedDict implementation
                out_dict[key] = val  # type: ignore
        return out_dict

    def _doc_to_out_entity(self, ent: MutableEntity,
                           doc_tokens: list[str],
                           only_cui: bool,
                           ) -> tuple[int, Union[Entity, str]]:
        cui = str(ent.cui)
        if not only_cui:
            out_ent = self._get_entity(ent, doc_tokens, cui)
            return ent.id, out_ent
        else:
            return ent.id, cui

    def _doc_to_out(self,
                    doc: MutableDocument,
                    only_cui: bool,
                    # addl_info: list[str], # TODO
                    out_with_text: bool = False
                    ) -> Union[Entities, OnlyCUIEntities]:
        out: Union[Entities, OnlyCUIEntities] = {'entities': {},
                                                 'tokens': []}  # type: ignore
        cnf_annotation_output = self.config.annotation_output
        _ents = doc.linked_ents

        if cnf_annotation_output.lowercase_context:
            doc_tokens = [tkn.base.text_with_ws.lower() for tkn in list(doc)]
        else:
            doc_tokens = [tkn.base.text_with_ws for tkn in list(doc)]

        for _, ent in enumerate(_ents):
            ent_id, ent_dict = self._doc_to_out_entity(ent, doc_tokens,
                                                       only_cui)
            # NOTE: the types match - not sure why mypy is having issues
            out['entities'][ent_id] = ent_dict  # type: ignore

        if cnf_annotation_output.include_text_in_output or out_with_text:
            out['text'] = doc.base.text
        return out

    @property
    def trainer(self):
        """The trainer object."""
        if not self._trainer:
            self._trainer = Trainer(self.cdb, self.__call__, self._pipeline)
        return self._trainer

    def save_model_pack(
            self, target_folder: str, pack_name: str = DEFAULT_PACK_NAME,
            serialiser_type: Union[str, AvailableSerialisers] = 'dill',
            make_archive: bool = True,
            only_archive: bool = False,
            add_hash_to_pack_name: bool = True,
            change_description: Optional[str] = None,
            ) -> str:
        """Save model pack.

        The resulting model pack name will have the hash of the model pack
        in its name if (and only if) the default model pack name is used.

        Args:
            target_folder (str):
                The folder to save the pack in.
            pack_name (str, optional): The model pack name.
                Defaults to DEFAULT_PACK_NAME.
            serialiser_type (Union[str, AvailableSerialisers], optional):
                The serialiser type. Defaults to 'dill'.
            make_archive (bool):
                Whether to make the arhive /.zip file. Defaults to True.
            only_archive (bool):
                Whether to clear the non-compressed folder. Defaults to False.
            add_hash_to_pack_name (bool):
                Whether to add the hash to the pack name. This is only relevant
                if pack_name is specified. Defaults to True.
            change_description (Optional[str]):
                If provided, this the description will be added to the
                model description. Defaults to None.

        Returns:
            str: The final model pack path.
        """
        self.config.meta.mark_saved_now()
        # figure out the location/folder of the saved files
        hex_hash = self._versioning(change_description)
        if pack_name == DEFAULT_PACK_NAME or add_hash_to_pack_name:
            pack_name = f"{pack_name}_{hex_hash}"
        model_pack_path = os.path.join(target_folder, pack_name)
        # ensure target folder and model pack folder exist
        ensure_folder_if_parent(model_pack_path)
        # tokenizer (e.g spacy model) - needs to saved before since
        #     it changes config slightly
        if isinstance(self._pipeline.tokenizer, SaveableTokenizer):
            internals_path = self._pipeline.tokenizer.save_internals_to(
                model_pack_path)
            self.config.general.nlp.modelname = internals_path
        # serialise
        serialise(serialiser_type, self, model_pack_path)
        model_card: str = self.get_model_card(as_dict=False)
        model_card_path = os.path.join(model_pack_path, "model_card.json")
        with open(model_card_path, 'w') as f:
            f.write(model_card)
        # components
        components_folder = os.path.join(
            model_pack_path, COMPONENTS_FOLDER)
        self._pipeline.save_components(serialiser_type, components_folder)
        # zip everything
        if make_archive:
            shutil.make_archive(model_pack_path, 'zip',
                                root_dir=model_pack_path)
            if only_archive:
                logger.info("Removing the non-archived model pack folder: %s",
                            model_pack_path)
                shutil.rmtree(model_pack_path, ignore_errors=True)
                # change the model pack path to the zip file so that we
                # refer to an existing file
                model_pack_path += ".zip"
        return model_pack_path

    def _get_hash(self) -> str:
        hasher = Hasher()
        logger.debug("Hashing the CDB")
        hasher.update(self.cdb.get_hash())
        for component in self._pipeline.iter_all_components():
            if isinstance(component, HashableComponet):
                logger.debug("Hashing for component %s",
                             type(component).__name__)
                hasher.update(component.get_hash())
        hex_hash = self.config.meta.hash = hasher.hexdigest()
        return hex_hash

    def _versioning(self, change_description: Optional[str]) -> str:
        date_today = date.today().strftime("%d %B %Y")
        if change_description is not None:
            self.config.meta.description += (
                f"\n[{date_today}] {change_description}")
        hex_hash = self._get_hash()
        history = self.config.meta.history
        if not history or history[-1] != hex_hash:
            history.append(hex_hash)
        logger.info("Got hash: %s", hex_hash)
        return hex_hash

    @classmethod
    def attempt_unpack(cls, zip_path: str) -> str:
        """Attempt unpack the zip to a folder and get the model pack path.

        If the folder already exists, no unpacking is done.

        Args:
            zip_path (str): The ZIP path

        Returns:
            str: The model pack path
        """
        base_dir = os.path.dirname(zip_path)
        filename = os.path.basename(zip_path)

        foldername = filename.replace(".zip", '')

        model_pack_path = os.path.join(base_dir, foldername)
        if os.path.exists(model_pack_path):
            logger.info(
                "Found an existing unzipped model pack at: %s, "
                "the provided zip will not be touched.", model_pack_path)
        else:
            logger.info("Unziping the model pack and loading models.")
            shutil.unpack_archive(zip_path, extract_dir=model_pack_path)
        return model_pack_path

    @classmethod
    def load_model_pack(cls, model_pack_path: str,
                        config_dict: Optional[dict] = None,
                        addon_config_dict: Optional[dict[str, dict]] = None
                        ) -> 'CAT':
        """Load the model pack from file.

        Args:
            model_pack_path (str): The model pack path.
            config_dict (Optional[dict]): The model config to
                merge in before initialising the pipe. Defaults to None.
            addon_config_dict (Optional[dict]): The Addon-specific
                config dict to merge in before pipe initialisation.
                If specified, it needs to have an addon dict per name.
                For instance, `{"meta_cat.Subject": {}}` would apply
                to the specific MetaCAT.

        Raises:
            ValueError: If the saved data does not represent a model pack.

        Returns:
            CAT: The loaded model pack.
        """
        if model_pack_path.endswith(".zip"):
            model_pack_path = cls.attempt_unpack(model_pack_path)
        logger.info("Attempting to load model from file: %s",
                    model_pack_path)
        is_legacy = is_legacy_model_pack(model_pack_path)
        avoid_legacy = avoid_legacy_conversion()
        if is_legacy and not avoid_legacy:
            from medcat.utils.legacy.conversion_all import Converter
            doing_legacy_conversion_message(logger, 'CAT', model_pack_path)
            return Converter(model_pack_path, None).convert()
        elif is_legacy and avoid_legacy:
            raise LegacyConversionDisabledError("CAT")
        # NOTE: ignoring addons since they will be loaded later / separately
        cat = deserialise(model_pack_path, model_load_path=model_pack_path,
                          ignore_folders_prefix={
                            AddonComponent.NAME_PREFIX,
                            # NOTE: will be loaded manually
                            AbstractCoreComponent.NAME_PREFIX,
                            # tokenizer stuff internals are loaded separately
                            # if appropraite
                            TOKENIZER_PREFIX,
                            # components will be loaded semi-manually
                            # within the creation of pipe
                            COMPONENTS_FOLDER,
                            # ignore hidden files/folders
                            '.'},
                          config_dict=config_dict,
                          addon_config_dict=addon_config_dict)
        # NOTE: deserialising of components that need serialised
        #       will be dealt with upon pipeline creation automatically
        if not isinstance(cat, CAT):
            raise ValueError(f"Unable to load CAT. Got: {cat}")
        return cat

    @classmethod
    def load_cdb(cls, model_pack_path: str) -> CDB:
        """
        Loads the concept database from the provided model pack path

        Args:
            model_pack_path (str): path to model pack, zip or dir.

        Returns:
            CDB: The loaded concept database
        """
        zip_path = (model_pack_path if model_pack_path.endswith(".zip")
                    else model_pack_path + ".zip")
        model_pack_path = cls.attempt_unpack(zip_path)
        cdb_path = os.path.join(model_pack_path, "cdb")
        cdb = CDB.load(cdb_path)
        return cdb

    @classmethod
    def load_addons(
            cls, model_pack_path: str,
            addon_config_dict: Optional[dict[str, dict]] = None
            ) -> list[tuple[str, AddonComponent]]:
        """Load addons based on a model pack path.

        Args:
            model_pack_path (str): path to model pack, zip or dir.
            addon_config_dict (Optional[dict]): The Addon-specific
                config dict to merge in before pipe initialisation.
                If specified, it needs to have an addon dict per name.
                For instance,
                `{"meta_cat.Subject": {'general': {'device': 'cpu'}}}`
                would apply to the specific MetaCAT.

        Returns:
            List[tuple(str, AddonComponent)]: list of pairs of adddon names the addons.
        """
        components_folder = os.path.join(model_pack_path, COMPONENTS_FOLDER)
        if not os.path.exists(components_folder):
            return []
        addon_paths_and_names = [
            (folder_path, folder_name.removeprefix(AddonComponent.NAME_PREFIX))
            for folder_name in os.listdir(components_folder)
            if os.path.isdir(folder_path := os.path.join(
                components_folder, folder_name))
            and folder_name.startswith(AddonComponent.NAME_PREFIX)
        ]
        loaded_addons = [
            addon for addon_path, addon_name in addon_paths_and_names
            if isinstance(addon := (
                deserialise(addon_path, model_config=addon_config_dict.get(addon_name))
                if addon_config_dict else
                deserialise(addon_path)
                ), AddonComponent)
        ]
        return [(addon.full_name, addon) for addon in loaded_addons]

    @overload
    def get_model_card(self, as_dict: Literal[True]) -> ModelCard:
        pass

    @overload
    def get_model_card(self, as_dict: Literal[False]) -> str:
        pass

    def get_model_card(self, as_dict: bool = False) -> Union[str, ModelCard]:
        """Get the model card either a (nested) `dict` or a json string.

        Args:
            as_dict (bool): Whether to return as dict. Defaults to False.

        Returns:
            Union[str, ModelCard]: The model card.
        """
        from medcat.components.addons.meta_cat import MetaCATAddon
        met_cat_model_cards = [
            mc.mc.get_model_card(True) for mc in
            self.get_addons_of_type(MetaCATAddon)
        ]
        cdb_info = self.cdb.get_basic_info()
        model_card: ModelCard = {
            'Model ID': self.config.meta.hash,
            'Last Modified On': self.config.meta.last_saved.isoformat(),
            'History (from least to most recent)': self.config.meta.history,
            'Description': self.config.meta.description,
            'Source Ontology': self.config.meta.ontology,
            'Location': self.config.meta.location,
            'MetaCAT models': met_cat_model_cards,
            'Basic CDB Stats': cdb_info,
            'Performance': {},  # TODO
            'Important Parameters (Partial view, '
            'all available in cat.config)': get_important_config_parameters(
                self.config),
            'MedCAT Version': self.config.meta.medcat_version,
        }
        if as_dict:
            return model_card
        return json.dumps(model_card, indent=2, sort_keys=False)

    @overload
    @classmethod
    def load_model_card_off_disk(cls, model_pack_path: str,
                                 as_dict: Literal[True],
                                 avoid_unpack: bool = False) -> ModelCard:
        pass

    @overload
    @classmethod
    def load_model_card_off_disk(cls, model_pack_path: str,
                                 as_dict: Literal[False],
                                 avoid_unpack: bool = False) -> str:
        pass

    @classmethod
    def load_model_card_off_disk(cls, model_pack_path: str,
                                 as_dict: bool = False,
                                 avoid_unpack: bool = False,
                                 ) -> Union[str, ModelCard]:
        """Load the model card off disk as a (nested) `dict` or a json string.

        Args:
            model_pack_path (str): The path to the model pack (zip or folder).
            as_dict (bool): Whether to return as dict. Defaults to False.
            avoid_unpack (bool): Whether to avoid unpacking the model pack if
                no previous unpacked path exists. Defaults to False.

        Returns:
            Union[str, ModelCard]: The model card.
        """
        model_card: Optional[ModelCard] = None
        # unpack if needed
        if model_pack_path.endswith(".zip"):
            if (avoid_unpack and
                    not os.path.exists(model_pack_path.removesuffix(".zip"))):
                # stream the model card directly from the zip
                with zipfile.ZipFile(model_pack_path) as zf:
                    with zf.open("model_card.json") as src:
                        model_card = json.load(src)
            else:
                # if allowed to unpack or already unpacked anyway
                model_pack_path = cls.attempt_unpack(model_pack_path)
        if model_card is None:
            # i.e not loaded directly off disk
            # load model card
            model_card_path = os.path.join(model_pack_path, "model_card.json")
            with open(model_card_path) as f:
                model_card = json.load(f)
        # return as dict or json
        if as_dict:
            return model_card
        return json.dumps(model_card, indent=2, sort_keys=False)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CAT):
            return False
        return (self.cdb == other.cdb and
                ((self.vocab is None and other.vocab is None)
                 or self.vocab == other.vocab))

    # addon (e.g MetaCAT) related stuff

    def add_addon(self, addon: AddonComponent) -> None:
        """Add the addon to the model pack an pipe.

        Args:
            addon (AddonComponent): The addon to add.
        """
        self.config.components.addons.append(addon.config)
        self._pipeline.add_addon(addon)

    def get_addons(self) -> list[AddonComponent]:
        """Get the list of all addons in this model pack.

        Returns:
            list[AddonComponent]: The list of addons present.
        """
        return list(self._pipeline.iter_addons())

    def get_addons_of_type(self, addon_type: Type[AddonType]) -> list[AddonType]:
        """Get a list of addons of a specific type.

        Args:
            addon_type (Type[AddonType]): The type of addons to look for.

        Returns:
            list[AddonType]: The list of addons of this specific type.
        """
        return [
            addon for addon in self.get_addons()
            if isinstance(addon, addon_type)
        ]


class OutOfDataException(ValueError):
    pass
