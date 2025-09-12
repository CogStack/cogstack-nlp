#!/usr/bin/env python

import logging
import time
from datetime import datetime, timezone

import numpy as np
import torch
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.components.addons.meta_cat import MetaCATAddon
from medcat.components.addons.relation_extraction.rel_cat import RelCATAddon
from medcat.components.ner.trf.deid import DeIdModel
from medcat.config import Config
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.config.config_rel_cat import ConfigRelCAT
from medcat.vocab import Vocab

from medcat_service.config import Settings
from medcat_service.types import HealthCheckResponse, ModelCardInfo, ProcessErrorsResult, ProcessResult, ServiceInfo


class MedCatProcessor:
    """"
    MedCAT Processor class is wrapper over MedCAT that implements annotations extractions functionality
    (both single and bulk processing) that can be easily exposed for an API.
    """

    def __init__(self, settings: Settings):

        self.service_settings = settings

        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(level=self.service_settings.app_log_level)

        self.log.debug("APP log level set to : " + str(self.service_settings.app_log_level))
        self.log.debug("MedCAT log level set to : " + str(self.service_settings.medcat_log_level))

        self.log.info("Initializing MedCAT processor ...")
        self._is_ready_flag = False

        self.app_version = MedCatProcessor._get_medcat_version()

        self.model_card_info = ModelCardInfo(
            ontologies=None,
            meta_cat_model_names=[],
            rel_cat_model_names=[],
            model_last_modified_on=None)

        # disale torch gradients, we don't need them for inference
        # this should also reduce memory consumption
        torch.set_grad_enabled(False)
        self.log.info("Torch autograd disabled (inference mode only)")

        # this is available to constrain torch threads when there
        # isn't a GPU
        # You probably want to set to 1
        # Not sure what happens if torch is using a cuda device
        if self.service_settings.torch_threads > 0:
            torch.set_num_threads(self.service_settings.torch_threads)
            self.log.info("Torch threads set to " + str(self.service_settings.torch_threads))

        self.cat: DeIdModel | CAT = self._create_cat()

        self._is_ready_flag = self._check_medcat_readiness()

    @staticmethod
    def _get_timestamp() -> str:
        """
        Returns the current timestamp in ISO 8601 format. Formatted as "yyyy-MM-dd"T"HH:mm:ss.SSSXXX".
        :return: timestamp string
        """
        return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")

    def _check_medcat_readiness(self) -> bool:
        readiness_text = "MedCAT is ready and can get_entities"
        try:
            result = self.cat.get_entities(readiness_text)
            self.log.debug("Result of readiness check is" + str(result))
            self.log.info("MedCAT processor is ready")
            return True
        except Exception as e:
            self.log.error(
                "MedCAT processor is not ready. Failed the readiness check", exc_info=e)
            return False

    def is_ready(self) -> HealthCheckResponse:
        """
        Is the MedCAT processor ready to get entities from input text
        """
        if self._is_ready_flag:
            return HealthCheckResponse(
                name="MedCAT",
                status="UP"
            )
        else:
            self.log.warning(
                "MedCAT Processor is not ready. Returning status DOWN")
            return HealthCheckResponse(
                name="MedCAT",
                status="DOWN"
            )

    def get_app_info(self) -> ServiceInfo:
        """Returns general information about the application.

        Returns:
            dict: Application information stored as KVPs.
        """
        return ServiceInfo(service_app_name=self.service_settings.app_name,
                           service_language=self.service_settings.app_model_language,
                           service_version=self.app_version,
                           service_model=self.service_settings.app_model_name,
                           model_card_info=self.model_card_info
                           )

    def process_entities(self, entities, *args, **kwargs):
        """Process entities for repsonse and serialisation
        """
        if type(entities) is dict:
            if "entities" in entities.keys():
                entities = entities["entities"]

            self._fix_floats(entities)

            if self.service_settings.annotations_entity_output_mode == "list":
                entities = list(entities.values())

        yield entities

    def process_content(self, content, *args, **kwargs):
        """Processes a single document extracting the annotations.

        Args:
            content (dict): Document to be processed, containing "text" field.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
                meta_anns_filters (List[Tuple[str, List[str]]]): List of task and filter values pairs to filter
                    entities by. Example: meta_anns_filters = [("Presence", ["True"]),
                    ("Subject", ["Patient", "Family"])] would filter entities where each
                    entity.meta_anns['Presence']['value'] is 'True' and
                    entity.meta_anns['Subject']['value'] is 'Patient' or 'Family'

        Returns:
            dict: Processing result containing document with extracted annotations stored as KVPs.
        """
        if "text" not in content:
            error_msg = "'text' field missing in the payload content."
            nlp_result = ProcessErrorsResult(
                success=False,
                errors=[error_msg],
                timestamp=self._get_timestamp(),
            )

            return nlp_result

        text = content["text"]

        # assume an that a blank document is a valid document and process it only
        # when it contains any non-blank characters

        start_time_ns = time.time_ns()

        if self.service_settings.deid_mode and isinstance(self.cat, DeIdModel):
            entities = self.cat.get_entities(text)
            text = self.cat.deid_text(text, redact=self.service_settings.deid_redact)
        else:
            if text is not None and len(text.strip()) > 0:
                entities = self.cat.get_entities(text)
            else:
                entities = []

        elapsed_time = (time.time_ns() - start_time_ns) / 10e8  # nanoseconds to seconds

        meta_anns_filters = kwargs.get("meta_anns_filters")
        if meta_anns_filters:
            if isinstance(entities, dict):
                entities = [
                    e
                    for e in entities["entities"].values()
                    if isinstance(e, dict)
                    and all(
                        task in e.get("meta_anns", {})
                        and e["meta_anns"][task]["value"] in filter_values
                        for task, filter_values in meta_anns_filters
                    )
                ]

        entities = list(self.process_entities(entities, **kwargs))

        nlp_result = ProcessResult(
            text=str(text),
            annotations=entities,
            success=True,
            timestamp=self._get_timestamp(),
            elapsed_time=elapsed_time,
            footer=content.get("footer"),
        )

        return nlp_result

    def process_content_bulk(self, content):
        """Processes an array of documents extracting the annotations.

        Args:
            content (list): List of documents to be processed, each containing "text" field.

        Returns:
            list: Processing results containing documents with extracted annotations, stored as KVPs.
        """
        # use generators both to provide input documents and to provide resulting annotations
        # to avoid too many mem-copies
        invalid_doc_ids = []
        ann_res = {}

        start_time_ns = time.time_ns()

        try:

            text_input = MedCatProcessor._generate_input_doc(content, invalid_doc_ids)
            if self.service_settings.deid_mode and isinstance(self.cat, DeIdModel):
                text_to_deid_from_tuple = (x[1] for x in text_input)

                ann_res = self.cat.deid_multi_texts(
                    list(text_to_deid_from_tuple),
                    redact=self.service_settings.deid_redact,
                    n_process=self.service_settings.bulk_nproc,
                )
            elif isinstance(self.cat, CAT):
                ann_res = {
                    ann_id: res for ann_id, res in
                    self.cat.get_entities_multi_texts(
                        text_input, n_process=self.service_settings.bulk_nproc)
                }
        except Exception as e:
            self.log.error("Unable to process data", exc_info=e)

        elapsed_time = (time.time_ns() - start_time_ns) / 10e8  # nanoseconds to seconds

        return self._generate_result(content, ann_res, elapsed_time)

    def _populate_model_card_info(self, config: Config) -> None:
        """Populates model card information from config.

        Args:
            config (Config): MedCAT configuration object.
        """
        self.model_card_info.ontologies = config.meta.ontology \
            if (isinstance(config.meta.ontology, list)) else str(config.meta.ontology)
        self.model_card_info.meta_cat_model_names = [
            cnf.general.category_name or "None" for cnf in config.components.addons
            if (isinstance(cnf, ConfigMetaCAT))]
        self.model_card_info.rel_cat_model_names = [
            str(cnf.general.labels2idx.values()) or "None" for cnf in config.components.addons
            if (isinstance(cnf, ConfigRelCAT))]
        self.model_card_info.model_last_modified_on = config.meta.last_saved

    def _create_cat(self) -> DeIdModel | CAT:
        """Loads MedCAT resources and creates CAT instance.

        Returns:
            DeIdModel | CAT: Initialized MedCAT instance.

        Raises:
            ValueError: If required environment variables are not set.
            Exception: If concept database path is not specified.
        """

        cdb, vocab = None, None
        cat: DeIdModel | CAT

        # ---- CUI filter ----
        cuis_to_keep: list[str] = []

        if self.service_settings.model_cui_filter_path:
            self.log.debug("Loading CUI filter ...")
            with open(self.service_settings.model_cui_filter_path) as cui_file:
                cuis_to_keep = [line.strip() for line in cui_file if line.strip()]

        # ---- Path 1: model pack ----
        if self.service_settings.medcat_model_pack:
            self.log.info("Loading model pack...")
            if self.service_settings.deid_mode:
                cat = DeIdModel.load_model_pack(self.service_settings.medcat_model_pack)
            else:
                cat = CAT.load_model_pack(self.service_settings.medcat_model_pack)

            if cuis_to_keep:
                self.log.debug("Applying CUI filter ...")
                cat.cdb.filter_by_cui(cuis_to_keep)

            cat.config.general.log_level = self.service_settings.medcat_log_level

            if not self.service_settings.app_model_name and cat.config.meta.hash:
                self.service_settings = self.service_settings.model_copy(
                    update={"app_model_name": cat.config.meta.hash}
                )

            self._populate_model_card_info(cat.config)
            return cat

        self.log.info(f"{Settings.env_name('medcat_model_pack')} not set, skipping...")

        # ---- Path 2: vocab + cdb ----
        if not self.service_settings.model_vocab_path:
            raise ValueError(
                f"Vocabulary (env {Settings.env_name('model_vocab_path')}) not specified"
            )
        self.log.debug("Loading VOCAB ...")
        vocab = Vocab.load(self.service_settings.model_vocab_path)

        if not self.service_settings.model_cdb_path:
            raise ValueError(
                f"Concept database (env {Settings.env_name('model_cdb_path')}) not specified"
            )
        self.log.debug("Loading CDB ...")
        cdb = CDB.load(self.service_settings.model_cdb_path)

        # ---- SpaCy model ----
        if self.service_settings.spacy_model:
            cdb.config.general.nlp.provider = "spacy"
            cdb.config.general.nlp.modelname = self.service_settings.spacy_model

        elif not cdb.config.general.nlp.modelname:
            raise ValueError(
                f"No {Settings.env_name('spacy_model')} env var declared and "
                "CDB has no spaCy model configured"
            )
        else:
            self.log.warning(
                f"{Settings.env_name('spacy_model')} not set, using spaCy model from CDB: "
                f"{cdb.config.general.nlp.modelname}"
            )

        if cuis_to_keep:
            self.log.debug("Applying CUI filter ...")
            cdb.filter_by_cui(cuis_to_keep)

        cat = CAT(cdb=cdb, config=cdb.config, vocab=vocab)
        cat.config.general.log_level = self.service_settings.medcat_log_level

        # ---- CAT add-ons ----
        for meta_model_path in self.service_settings.model_meta_path_list:
            self.log.debug("Loading META annotations from %s", meta_model_path)
            cat.add_addon(MetaCATAddon.deserialise_from(meta_model_path))

        for rel_model_path in self.service_settings.model_rel_path_list:
            self.log.debug("Loading RELATION annotations from %s", rel_model_path)
            cat.add_addon(RelCATAddon.deserialise_from(rel_model_path))

        if not self.service_settings.app_model_name and cat.config.meta.hash:
            self.service_settings = self.service_settings.model_copy(
                update={"app_model_name": cat.config.meta.hash}
            )

        self._populate_model_card_info(cat.config)
        return cat

    # helper generator functions to avoid multiple copies of data
    #
    @staticmethod
    def _generate_input_doc(documents, invalid_doc_idx):
        """Generator function returning documents to be processed.

        Args:
            documents (list): Array of input documents that contain "text" field.
            invalid_doc_idx (list): Array that will contain invalid document idx.

        Yields:
            tuple: Consecutive tuples of (idx, document).
        """
        for i in range(0, len(documents)):
            # assume the document to be processed only when it is not blank
            if documents[i] is not None and "text" in documents[i] and documents[i]["text"] is not None \
                    and len(documents[i]["text"].strip()) > 0:
                yield i, documents[i]["text"]
            else:
                invalid_doc_idx.append(i)

    def _generate_result(self, in_documents, annotations, elapsed_time):
        """Generator function merging the resulting annotations with the input documents.

        Args:
            in_documents (list): Array of input documents that contain "text" field.
            annotations (dict): Array of annotations extracted from documents.
            additional_info (dict, optional): Additional information to include in results. Defaults to {}.
            elapsed_time: Total elapsed time to get annotations

        Yields:
            dict: Merged document with annotations.
        """

        for i in range(len(in_documents)):
            in_ct = in_documents[i]
            if not self.service_settings.deid_mode and i in annotations.keys():
                # generate output for valid annotations

                entities = list(self.process_entities(annotations.get(i)))

                out_res = ProcessResult(
                    text=str(in_ct["text"]),
                    annotations=entities,
                    success=True,
                    timestamp=self._get_timestamp(),
                    elapsed_time=elapsed_time,
                    footer=in_ct.get("footer"),
                )
            elif self.service_settings.deid_mode:
                out_res = ProcessResult(
                    # TODO: DEID mode is passing the resulting text in the annotations field here but shouldnt.
                    text=str(annotations[i]),
                    # TODO: DEID bulk mode should also be able to return the list of annotations found,
                    #  to match the features of the singular api, this needs to be matched by MedCAT. CU-869a6wc6z
                    annotations=[],
                    success=True,
                    timestamp=self._get_timestamp(),
                    elapsed_time=elapsed_time,
                    footer=in_ct.get("footer"),
                )
            else:
                # Don't fetch an annotation set
                # as the document was invalid
                out_res = ProcessResult(
                    text=str(in_ct["text"]),
                    annotations=[],
                    success=True,
                    timestamp=self._get_timestamp(),
                    elapsed_time=elapsed_time,
                    footer=in_ct.get("footer"),
                )

            yield out_res

    @staticmethod
    def _get_medcat_version() -> str:
        """Returns the version string of the MedCAT module as reported by pip.

        Returns:
            str: Version string of MedCAT.

        Raises:
            Exception: If MedCAT library version cannot be read.
        """
        try:
            import pkg_resources
            version = pkg_resources.require("medcat")[0].version
            return str(version)
        except Exception:
            raise Exception("Cannot read the MedCAT library version")

    # NOTE: numpy uses np.float32 and those are not json serialisable
    #       so we need to fix that

    def _fix_floats(self, in_dict: dict) -> dict:
        for k, v in in_dict.items():
            if isinstance(v, np.floating):
                in_dict[k] = float(v)
            elif isinstance(v, dict):
                self._fix_floats(v)
        return in_dict
