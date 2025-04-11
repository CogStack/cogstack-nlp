from typing import Optional, Union, Any
import os

import shutil
import logging

from medcat2.utils.defaults import DEFAULT_PACK_NAME, COMPONENTS_FOLDER
from medcat2.cdb import CDB
from medcat2.vocab import Vocab
from medcat2.config.config import Config
from medcat2.trainer import Trainer
from medcat2.storage.serialisers import serialise, AvailableSerialisers
from medcat2.storage.serialisers import deserialise
from medcat2.storage.serialisables import AbstractSerialisable
from medcat2.utils.fileutils import ensure_folder_if_parent
from medcat2.utils.hasher import Hasher
from medcat2.pipeline.pipeline import Pipeline
from medcat2.tokenizing.tokens import MutableDocument, MutableEntity
from medcat2.data.entities import Entity, Entities, OnlyCUIEntities
from medcat2.components.types import AbstractCoreComponent, HashableComponet
from medcat2.components.addons.addons import AddonComponent


logger = logging.getLogger(__name__)


class CAT(AbstractSerialisable):
    """This is a collection of serialisable model parts.
    """

    def __init__(self,
                 cdb: CDB,
                 vocab: Union[Vocab, None] = None,
                 config: Optional[Config] = None,
                 model_load_path: Optional[str] = None,
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

        self._trainer: Optional[Trainer] = None
        self._pipeline = self._recrate_pipe(model_load_path)

    def _recrate_pipe(self, model_load_path: Optional[str] = None) -> Pipeline:
        self._pipeline = Pipeline(self.cdb, self.vocab, model_load_path)
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
        ]

    def __call__(self, text: str) -> Optional[MutableDocument]:
        return self._pipeline.get_doc(text)

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
        _ents = doc.final_ents

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

        Returns:
            str: The final model pack path.
        """
        self.config.meta.mark_saved_now()
        # figure out the location/folder of the saved files
        hex_hash = self._versioning()
        if pack_name == DEFAULT_PACK_NAME:
            pack_name = f"{pack_name}_{hex_hash}"
        model_pack_path = os.path.join(target_folder, pack_name)
        # ensure target folder and model pack folder exist
        ensure_folder_if_parent(model_pack_path)
        # serialise
        serialise(serialiser_type, self, model_pack_path)
        # components
        components_folder = os.path.join(
            model_pack_path, COMPONENTS_FOLDER)
        self._pipeline.save_components(serialiser_type, components_folder)
        # zip everything
        if make_archive:
            shutil.make_archive(model_pack_path, 'zip',
                                root_dir=model_pack_path)
        return model_pack_path

    def _versioning(self) -> str:
        hasher = Hasher()
        logger.debug("Hashing the CDB")
        hasher.update(self.cdb.get_hash())
        for component in self._pipeline.iter_all_components():
            if isinstance(component, HashableComponet):
                logger.debug("Hashing for component %s",
                             type(component).__name__)
                hasher.update(component.get_hash())
        hex_hash = self.config.meta.hash = hasher.hexdigest()
        history = self.config.meta.history
        if not history or history[-1] != hex_hash:
            history.append(hex_hash)
        logger.info("Got hash: %s", hex_hash)
        return hex_hash

    @classmethod
    def load_model_pack(cls, model_pack_path: str) -> 'CAT':
        """Load the model pack from file.

        Args:
            model_pack_path (str): The model pack path.

        Raises:
            ValueError: If the saved data does not represent a model pack.

        Returns:
            CAT: The loaded model pack.
        """
        if model_pack_path.endswith(".zip"):
            folder_path = model_pack_path.rsplit(".zip", 1)[0]
            if not os.path.exists(folder_path):
                logger.info("Unpacking model pack from %s to %s",
                            model_pack_path, folder_path)
                shutil.unpack_archive(model_pack_path,
                                      folder_path)
            model_pack_path = folder_path
        logger.info("Attempting to load model from file: %s",
                    model_pack_path)
        # NOTE: ignoring addons since they will be loaded later / separately
        cat = deserialise(model_pack_path, model_load_path=model_pack_path,
                          ignore_folders_prefix={
                            AddonComponent.NAME_PREFIX,
                            # NOTE: will be loaded manually
                            AbstractCoreComponent.NAME_PREFIX,
                            # components will be loaded semi-manually
                            # within the creation of pipe
                            COMPONENTS_FOLDER})
        # NOTE: deserialising of components that need serialised
        #       will be dealt with upon pipeline creation automatically
        if not isinstance(cat, CAT):
            raise ValueError(f"Unable to load CAT. Got: {cat}")
        # NOTE: Some CDB attributes will have been set manually
        #       after init so the CDB is likely "dirty"
        cat.cdb._reset_subnames()
        return cat

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, CAT):
            return False
        return (self.cdb == other.cdb and
                ((self.vocab is None and other.vocab is None)
                 or self.vocab == other.vocab))

    # addon (e.g MetaCAT) related stuff

    def add_addon(self, addon: AddonComponent) -> None:
        self.config.components.addons.append(addon.config)
        self._pipeline.add_addon(addon)
