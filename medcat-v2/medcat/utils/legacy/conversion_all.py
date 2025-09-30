import os
import shutil
import logging
from typing import Optional

from medcat.cat import CAT
from medcat.components.types import CoreComponentType
from medcat.storage.serialisers import AvailableSerialisers
from medcat.components.linking.no_action_linker import NoActionLinker

from medcat.utils.legacy.convert_cdb import get_cdb_from_old
from medcat.utils.legacy.convert_config import get_config_from_old
from medcat.utils.legacy.convert_vocab import get_vocab_from_old
from medcat.utils.legacy.convert_meta_cat import get_meta_cat_from_old
from medcat.utils.legacy.convert_rel_cat import get_rel_cat_from_old
from medcat.utils.legacy.convert_deid import get_trf_ner_from_old
from medcat.utils.legacy.helpers import fix_subnames


logger = logging.getLogger(__name__)


class Converter:
    """Converts v1 models to v2 models."""
    cdb_name = 'cdb.dat'
    vocab_name = 'vocab.dat'
    config_name = 'config.json'

    def __init__(self, medcat1_model_pack_path: str,
                 new_model_pack_path: Optional[str],
                 ser_type: AvailableSerialisers = AvailableSerialisers.dill):
        if medcat1_model_pack_path.endswith(".zip"):
            folder_path = medcat1_model_pack_path[:-4]
            self.old_model_name = os.path.split(
                medcat1_model_pack_path)[1].rsplit(".zip", 1)[0]
            unpack(medcat1_model_pack_path, folder_path)
            medcat1_model_pack_path = folder_path
        else:
            self.old_model_name = os.path.split(medcat1_model_pack_path)[1]
        if not os.path.isdir(medcat1_model_pack_path):
            raise ValueError(
                "Provided model path is not a directory: "
                f"{medcat1_model_pack_path}")
        self.old_model_folder = medcat1_model_pack_path
        self.new_model_folder = new_model_pack_path
        self.ser_type = ser_type
        self._validate()

    @property
    def expected_files_in_folder(self):
        """The base names of the required files in a folder for a v1 model."""
        return [self.cdb_name, ]

    def _validate(self):
        for fn in self.expected_files_in_folder:
            path = os.path.join(self.old_model_folder, fn)
            if not os.path.exists(path):
                raise ValueError(f"Unable to find {fn} in model folder "
                                 f"{self.old_model_folder}")

    def convert(self) -> CAT:
        """Use the gathered information to convert to a v2 model.

        This converts the CDB, Vocab, and Config, in order and then
        created the model pack.

        If `self.new_model_folder` is set, the model will be saved as well.

        Returns:
            CAT: The model pack.
        """
        cdb = get_cdb_from_old(
            os.path.join(self.old_model_folder, self.cdb_name))
        vocab_path = os.path.join(self.old_model_folder, self.vocab_name)
        if os.path.exists(vocab_path):
            vocab = get_vocab_from_old(vocab_path)
        else:
            # e.g in case of DeID
            vocab = None
        cnf_path = os.path.join(self.old_model_folder, self.config_name)
        if os.path.exists(cnf_path):
            config = get_config_from_old(cnf_path)
        else:
            config = cdb.config
        cat = CAT(cdb, vocab, config)
        fix_subnames(cat)
        # MetaCATs
        meta_cats = [
            get_meta_cat_from_old(
                os.path.join(self.old_model_folder, subfolder),
                cat._pipeline.tokenizer)
            for subfolder in os.listdir(self.old_model_folder)
            if subfolder.startswith("meta_")
        ]
        for mc in meta_cats:
            cat.add_addon(mc)

        # RelCATs
        rel_cats = [
            get_rel_cat_from_old(
                cdb,
                os.path.join(self.old_model_folder, subfolder),
                cat._pipeline.tokenizer)
            for subfolder in os.listdir(self.old_model_folder)
            if subfolder.startswith("rel_")
        ]
        for rc in rel_cats:
            cat.add_addon(rc)

        # DeID / TransformersNER
        trf_ners = [
            get_trf_ner_from_old(
                os.path.join(self.old_model_folder, subfolder),
                cat._pipeline.tokenizer)
            for subfolder in os.listdir(self.old_model_folder)
            if subfolder.startswith("trf_")
        ]
        if len(trf_ners) > 1:
            raise ValueError("Cannot use more than 1 tranformers NER. "
                             f"Got {len(trf_ners)}")
        if trf_ners:
            logger.info("Found a Transformers based NER component "
                        "- probably for DeID")
            trf_ner = trf_ners[0]
            # update the TrfNER-loaded CDB with the correct config
            trf_ner._component.cdb.config = config
            # update the config with the correct NER custom config
            trf_cnf = trf_ner._component.config
            config.components.ner.custom_cnf = trf_cnf
            # update the component name
            config.components.ner.comp_name = trf_ner.name
            # replace component in pipeline
            # get the index of component in list
            index = next((c_num for c_num, comp in
                          enumerate(cat._pipeline._components)
                          if comp.get_type() is CoreComponentType.ner))
            # set / change / replace the NER component
            logger.info(f"Changing the NER component in the pipe to {trf_ner}")
            cat._pipeline._components[index] = trf_ner
            # replace linker to no-action linker
            config.components.linking.comp_name = 'no_action'
            index_link = next(
                (c_num for c_num, comp in enumerate(cat._pipeline._components)
                 if comp.get_type() is CoreComponentType.linking))
            # set / change / replace Linker to no-action linker
            logger.info("Changing the linking component in the pipe to a "
                        "no-action linker")
            cat._pipeline._components[index_link] = NoActionLinker()

        if self.new_model_folder:
            logger.info("Saving converted model to '%s'",
                        self.new_model_folder)
            cat.save_model_pack(self.new_model_folder,
                                pack_name=self.old_model_name + 'v2',
                                serialiser_type=self.ser_type)
        return cat


def unpack(model_zip_path: str, target_folder: str):
    """Unpack v1 model into target folder.

    Args:
        model_zip_path (str): ZIP path.
        target_folder (str): Target folder.
    """
    shutil.unpack_archive(model_zip_path, extract_dir=target_folder)
