#!/usr/bin/env python

import logging
import os
import time
from datetime import datetime, timezone

import simplejson as json
from medcat.cat import CAT
from medcat.cdb import CDB
from medcat.components.addons.meta_cat import MetaCATAddon
from medcat.components.ner.trf.deid import DeIdModel
from medcat.config import Config
from medcat.config.config_meta_cat import ConfigMetaCAT
from medcat.vocab import Vocab

from medcat_service.types import HealthCheckResponse, ModelCardInfo, ProcessErrorsResult, ProcessResult, ServiceInfo


class NlpProcessor:
    """
    This class defines an interface for NLP Processor
    """

    def __init__(self):
        app_log_level = os.getenv("APP_LOG_LEVEL", logging.INFO)
        medcat_log_level = os.getenv("LOG_LEVEL", logging.INFO)

        self.log = logging.getLogger(self.__class__.__name__)
        self.log.setLevel(level=app_log_level)

        self.log.debug("APP log level set to : " + str(app_log_level))
        self.log.debug("MedCAT log level set to : " + str(medcat_log_level))

    def get_app_info(self):
        pass

    def process_content(self, content, *args, **kwargs):
        pass

    def process_content_bulk(self, content, *args, **kwargs):
        pass

    def is_ready(self) -> HealthCheckResponse:
        return HealthCheckResponse(
            name="MedCAT",
            status="DOWN"
        )

    @staticmethod
    def _get_timestamp():
        """
        Returns the current timestamp in ISO 8601 format. Formatted as "yyyy-MM-dd"T"HH:mm:ss.SSSXXX".
        :return: timestamp string
        """
        return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


class MedCatProcessor(NlpProcessor):
    """"
    MedCAT Processor class is wrapper over MedCAT that implements annotations extractions functionality
    (both single and bulk processing) that can be easily exposed for an API.
    """

    def __init__(self):
        super().__init__()

        self.log.info("Initializing MedCAT processor ...")
        self._is_ready_flag = False

        self.app_name = os.getenv("APP_NAME", "MedCAT")
        self.app_lang = os.getenv("APP_MODEL_LANGUAGE", "en")
        self.app_version = MedCatProcessor._get_medcat_version()
        self.app_model = os.getenv("APP_MODEL_NAME", "unknown")
        self.entity_output_mode = os.getenv(
            "ANNOTATIONS_ENTITY_OUTPUT_MODE", "dict").lower()

        self.bulk_nproc = int(os.getenv("APP_BULK_NPROC", 8))
        self.torch_threads = int(os.getenv("APP_TORCH_THREADS", -1))
        self.DEID_MODE = eval(os.getenv("DEID_MODE", "False"))
        self.DEID_REDACT = eval(os.getenv("DEID_REDACT", "True"))
        self.model_card_info = ModelCardInfo(
            ontologies=None, meta_cat_model_names=[], model_last_modified_on=None)

        # this is available to constrain torch threads when there
        # isn't a GPU
        # You probably want to set to 1
        # Not sure what happens if torch is using a cuda device
        if self.torch_threads > 0:
            import torch
            torch.set_num_threads(self.torch_threads)
            self.log.info("Torch threads set to " + str(self.torch_threads))

        self.cat = self._create_cat()
        self.cat.train = os.getenv("APP_TRAINING_MODE", False)

        self._is_ready_flag = self._check_medcat_readiness()

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
        return ServiceInfo(service_app_name=self.app_name,
                           service_language=self.app_lang,
                           service_version=self.app_version,
                           service_model=self.app_model,
                           model_card_info=self.model_card_info
                           )

    def process_entities(self, entities, *args, **kwargs):
        """Process entities for repsonse and serialisation
        """
        if type(entities) is dict:
            if "entities" in entities.keys():
                entities = entities["entities"]

            if self.entity_output_mode == "list":
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
                timestamp=NlpProcessor._get_timestamp(),
            )

            return nlp_result

        text = content["text"]

        # assume an that a blank document is a valid document and process it only
        # when it contains any non-blank characters

        start_time_ns = time.time_ns()

        if self.DEID_MODE:
            entities = self.cat.get_entities(text)["entities"]
            text = self.cat.deid_text(text, redact=self.DEID_REDACT)
        else:
            if text is not None and len(text.strip()) > 0:
                entities = self.cat.get_entities(text)
            else:
                entities = []

        elapsed_time = (time.time_ns() - start_time_ns) / 10e8  # nanoseconds to seconds

        if kwargs.get("meta_anns_filters"):
            meta_anns_filters = kwargs.get("meta_anns_filters")
            entities = [e for e in entities['entities'].values() if
                        all(e['meta_anns'][task]['value'] in filter_values
                            for task, filter_values in meta_anns_filters)]

        entities = list(self.process_entities(entities, **kwargs))

        nlp_result = ProcessResult(
            text=str(text),
            annotations=entities,
            success=True,
            timestamp=NlpProcessor._get_timestamp(),
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
            if self.DEID_MODE:
                # TODO 2025-07-21: deid_multi_texts doesnt exist in medcat 2?
                ann_res = self.cat.deid_multi_texts(MedCatProcessor._generate_input_doc(content, invalid_doc_ids),
                                                    redact=self.DEID_REDACT)
            else:
                text_input = MedCatProcessor._generate_input_doc(
                    content, invalid_doc_ids)
                ann_res = {
                    ann_id: res for ann_id, res in
                    self.cat.get_entities_multi_texts(
                        text_input, n_process=self.bulk_nproc)
                }
        except Exception as e:
            self.log.error("Unable to process data", exc_info=e)

        elapsed_time = (time.time_ns() - start_time_ns) / 10e8  # nanoseconds to seconds

        return self._generate_result(content, ann_res, elapsed_time)

    def retrain_medcat(self, content, replace_cdb):
        """Retrains Medcat and redeploys model.

        Args:
            content: Training data for retraining.
            replace_cdb: Whether to replace the existing CDB.

        Returns:
            dict: Results containing precision, recall, F1 scores and error dictionaries.
        """

        with open("/cat/models/data.json", "w") as f:
            json.dump(content, f)

        DATA_PATH = "/cat/models/data.json"
        CDB_PATH = "/cat/models/cdb.dat"
        VOCAB_PATH = "/cat/models/vocab.dat"

        self.log.info("Retraining Medcat Started...")

        p, r, f1, tp_dict, fp_dict, fn_dict = MedCatProcessor._retrain_supervised(
            self, CDB_PATH, DATA_PATH, VOCAB_PATH)

        self.log.info("Retraining Medcat Completed...")

        return {"results": [p, r, f1, tp_dict, fp_dict, fn_dict]}

    def _populate_model_card_info(self, config: Config):
        """Populates model card information from config.

        Args:
            config (Config): MedCAT configuration object.
        """
        self.model_card_info.ontologies = config.meta.ontology \
            if (isinstance(config.meta.ontology, list)) else str(config.meta.ontology)
        self.model_card_info.meta_cat_model_names = [
            cnf.general.category_name or "None" for cnf in config.components.addons
            if (isinstance(cnf, ConfigMetaCAT))]
        self.model_card_info.model_last_modified_on = config.meta.last_saved

    # helper MedCAT methods
    #
    def _create_cat(self):
        """Loads MedCAT resources and creates CAT instance.

        Returns:
            CAT: Initialized MedCAT instance.

        Raises:
            ValueError: If required environment variables are not set.
            Exception: If concept database path is not specified.
        """
        cat, cdb, vocab, config = None, None, None, None

        # Load CUIs to keep if provided
        if os.getenv("APP_MODEL_CUI_FILTER_PATH", None) is not None:
            self.log.debug("Loading CUI filter ...")
            with open(os.getenv("APP_MODEL_CUI_FILTER_PATH")) as cui_file:
                all_lines = (line.rstrip() for line in cui_file)
                # filter blank lines
                cuis_to_keep = [line for line in all_lines if line]

        model_pack_path = os.getenv("APP_MEDCAT_MODEL_PACK", "").strip()

        if model_pack_path != "":
            self.log.info("Loading model pack...")
            cat = CAT.load_model_pack(model_pack_path)

            if self.DEID_MODE:
                cat = DeIdModel.load_model_pack(model_pack_path)

            # Apply CUI filter if provided
            if os.getenv("APP_MODEL_CUI_FILTER_PATH", None) is not None:
                self.log.debug("Applying CUI filter ...")
                cat.cdb.filter_by_cui(cuis_to_keep)

            if self.app_model.lower() in ["", "unknown", "medmen"] and cat.config.meta.hash is not None:
                self.app_model = cat.config.meta.hash

            self._populate_model_card_info(cat.config)

            return cat
        else:
            self.log.info("APP_MEDCAT_MODEL_PACK not set, skipping....")

        # Vocabulary and Concept Database are mandatory
        if os.getenv("APP_MODEL_VOCAB_PATH", None) is None and cat is None:
            raise ValueError(
                "Vocabulary (env: APP_MODEL_VOCAB_PATH) not specified")
        else:
            self.log.debug("Loading VOCAB ...")
            vocab = Vocab.load(os.getenv("APP_MODEL_VOCAB_PATH"))

        if os.getenv("APP_MODEL_CDB_PATH", None) is None and cat is None:
            raise Exception(
                "Concept database (env: APP_MODEL_CDB_PATH) not specified")
        else:
            self.log.debug("Loading CDB ...")
            cdb = CDB.load(os.getenv("APP_MODEL_CDB_PATH"))

        spacy_model = os.getenv("SPACY_MODEL", "")

        if spacy_model != "":
            cdb.config.general.nlp.modelname = spacy_model
        else:
            logging.warning("SPACY_MODEL environment var not set" +
                            ", attempting to load the spacy model found within the CDB : "
                            + cdb.config.general.nlp.modelname)

            if cdb.config.general.nlp.modelname == "":
                raise ValueError("No SPACY_MODEL env var declared, the CDB loaded does not have a\
                     spacy_model set in the config variable! \
                 To solve this declare the SPACY_MODEL in the env_medcat file.")

        if cat is None:
            # this is redundant as the config is already in the CDB
            config = cdb.config

        # Apply CUI filter if provided
        if os.getenv("APP_MODEL_CUI_FILTER_PATH", None) is not None:
            self.log.debug("Applying CUI filter ...")
            cdb.filter_by_cui(cuis_to_keep)

        # Meta-annotation models are optional
        meta_models = []
        if os.getenv("APP_MODEL_META_PATH_LIST", None) is not None:
            self.log.debug("Loading META annotations ...")
            for model_path in os.getenv("APP_MODEL_META_PATH_LIST").split(":"):
                m = MetaCATAddon.deserialise_from(model_path)
                meta_models.append(m)

        # if cat:
        #     meta_models.extend(cat._meta_cats)

        if self.app_model.lower() in [None, "unknown"] and cdb.config.meta.hash is not None:
            self.app_model = cdb.config.meta.hash

        config.general.log_level = os.getenv("LOG_LEVEL", logging.INFO)

        cat = CAT(cdb=cdb, config=config, vocab=vocab)
        # add MetaCATs
        for mc in meta_models:
            cat.add_addon(mc)

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
            if not self.DEID_MODE and i in annotations.keys():
                # generate output for valid annotations

                entities = list(self.process_entities(annotations.get(i)))

                out_res = ProcessResult(
                    text=str(in_ct["text"]),
                    annotations=entities,
                    success=True,
                    timestamp=NlpProcessor._get_timestamp(),
                    elapsed_time=elapsed_time,
                    footer=in_ct.get("footer"),
                )
            elif self.DEID_MODE:

                out_res = ProcessResult(
                    text=str(in_ct["text"]),
                    annotations=[],
                    success=True,
                    timestamp=NlpProcessor._get_timestamp(),
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
                    timestamp=NlpProcessor._get_timestamp(),
                    elapsed_time=elapsed_time,
                    footer=in_ct.get("footer"),
                )

            yield out_res

    @staticmethod
    def _get_medcat_version():
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

    def _retrain_supervised(self, cdb_path, data_path, vocab_path, cv=1, nepochs=1,
                            test_size=0.1, lr=1, groups=None, **kwargs):
        """Retrains MedCAT model using supervised learning.

        Args:
            cdb_path (str): Path to concept database.
            data_path (str): Path to training data.
            vocab_path (str): Path to vocabulary.
            cv (int, optional): Number of cross-validation folds. Defaults to 1.
            nepochs (int, optional): Number of training epochs. Defaults to 1.
            test_size (float, optional): Size of test set. Defaults to 0.1.
            lr (float, optional): Learning rate. Defaults to 1.
            groups (list, optional): Training groups. Defaults to None.
            **kwargs: Additional keyword arguments.

        Returns:
            tuple: Precision, recall, F1 score, and error dictionaries.
        """

        data = json.load(open(data_path))
        correct_ids = MedCatProcessor._prepareDocumentsForPeformanceAnalysis(
            data)

        cat = MedCatProcessor._create_cat(self)

        f1_base = MedCatProcessor._computeF1forDocuments(
            self, data, self.cat, correct_ids)[2]
        self.log.info("Base model F1: " + str(f1_base))

        cat.train = True
        cat.spacy_cat.MIN_ACC = os.getenv("MIN_ACC", 0.20)
        cat.spacy_cat.MIN_ACC_TH = os.getenv("MIN_ACC_TH", 0.20)

        self.log.info("Starting supervised training...")

        try:
            cat.train_supervised(data_path=data_path, lr=1,
                                 test_size=0.1, use_groups=None, nepochs=3)
        except Exception:
            self.log.info("Did not complete all supervised training")

        p, r, f1, tp_dict, fp_dict, fn_dict = MedCatProcessor._computeF1forDocuments(
            self, data, cat, correct_ids)

        self.log.info("Trained model F1: " + str(f1))

        if MedCatProcessor._checkmodelimproved(f1, f1_base):
            self.log.info("Model will be saved...")

            cat.cdb.save_dict("/cat/models/cdb_new.dat")

        self.log.info("Completed Retraining Medcat...")
        return p, r, f1, tp_dict, fp_dict, fn_dict

    def _computeF1forDocuments(self, data, cat, correct_ids):
        """Computes F1 score and related metrics for documents.

        Args:
            data (dict): Input data containing projects and documents.
            cat (CAT): MedCAT instance.
            correct_ids (dict): Dictionary of correct annotations.

        Returns:
            tuple: Precision, recall, F1 score, and error dictionaries.
        """

        true_positives_dict, false_positives_dict, false_negatives_dict = {}, {}, {}
        true_positive_no, false_positive_no, false_negative_no = 0, 0, 0

        for project in data["projects"]:

            predictions = {}
            documents = project["documents"]
            true_positives_dict[project["id"]] = {}
            false_positives_dict[project["id"]] = {}
            false_negatives_dict[project["id"]] = {}

            for document in documents:
                true_positives_dict[project["id"]][document["id"]] = {}
                false_positives_dict[project["id"]][document["id"]] = {}
                false_negatives_dict[project["id"]][document["id"]] = {}

                results = cat.get_entities(document["text"])
                predictions[document["id"]] = [
                    [a["start"], a["end"], a["cui"]] for a in results]

                tps, fps, fns = MedCatProcessor._getAccuraciesforDocument(
                    predictions[document["id"]],
                    correct_ids[project["id"]][document["id"]]
                )
                true_positive_no += len(tps)
                false_positive_no += len(fps)
                false_negative_no += len(fns)

                true_positives_dict[project["id"]][document["id"]] = tps
                false_positives_dict[project["id"]][document["id"]] = fps
                false_negatives_dict[project["id"]][document["id"]] = fns

        if (true_positive_no + false_positive_no) == 0:
            precision = 0
        else:
            precision = true_positive_no / \
                (true_positive_no + false_positive_no)
        if (true_positive_no + false_negative_no) == 0:
            recall = 0
        else:
            recall = true_positive_no / (true_positive_no + false_negative_no)
        if (precision + recall) == 0:
            f1 = 0
        else:
            f1 = 2*((precision*recall) / (precision + recall))

        return precision, recall, f1, true_positives_dict, false_positives_dict, false_negatives_dict

    @staticmethod
    def _prepareDocumentsForPeformanceAnalysis(data):
        """Prepares documents for performance analysis.

        Args:
            data (dict): Input data containing projects and documents.

        Returns:
            dict: Dictionary of correct annotations by project and document.
        """
        correct_ids = {}
        for project in data["projects"]:
            correct_ids[project["id"]] = {}

            for document in project["documents"]:
                for entry in document["annotations"]:
                    if entry["correct"]:
                        if document["id"] not in correct_ids[project["id"]]:
                            correct_ids[project["id"]][document["id"]] = []
                        correct_ids[project["id"]][document["id"]].append(
                            [entry["start"], entry["end"], entry["cui"]])

        return correct_ids

    @staticmethod
    def _getAccuraciesforDocument(prediction, correct_ids):
        """Computes accuracy metrics for a single document.

        Args:
            prediction (list): List of predicted annotations.
            correct_ids (list): List of correct annotations.

        Returns:
            tuple: True positives, false positives, and false negatives.
        """

        tup1 = list(map(tuple, correct_ids))
        tup2 = list(map(tuple, prediction))

        true_positives = list(map(list, set(tup1).intersection(tup2)))
        false_positives = list(map(list, set(tup1).difference(tup2)))
        false_negatives = list(map(list, set(tup2).difference(tup1)))

        return true_positives, false_positives, false_negatives

    @staticmethod
    def _checkmodelimproved(f1_model_a, f1_model_b):
        """Checks if model performance has improved.

        Args:
            f1_model_a (float): F1 score of first model.
            f1_model_b (float): F1 score of second model.

        Returns:
            bool: True if first model has better F1 score, False otherwise.
        """

        if f1_model_a > f1_model_b:
            return True
        else:
            return False
