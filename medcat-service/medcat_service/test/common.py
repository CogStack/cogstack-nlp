#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os

log = logging.getLogger(__name__)


def get_example_short_document():
    """
    Returns an example short document to be processed with possibly minimal set of annotations to be validated
    :return:
    """
    return "The patient was prescribed with Aspirin, 4-5 tabs daily"


def get_example_long_document():
    """
    Returns a relatively long document to be processed to test multiple annotations
    :return:
    """
    return """Pt is 40yo mother, software engineer
            HPI : Sleeping trouble on present dosage of Clonidine.
            Severe Rash  on face and leg, slightly itchy
            Meds : Vyvanse 50 mgs po at breakfast daily,
            Clonidine 0.2 mgs -- 1 and 1 / 2 tabs po qhs,
            Aspirin -- 4-5 tabs daily
            HEENT : Boggy inferior turbinates, No oropharyngeal lesion
            Lungs : clear Heart : Regular rhythm
            Skin :  Papular mild erythematous eruption to hairline Follow-up as scheduled."""


def get_blank_documents():
    """
    Returns an array of empty / blank documents that can be found to be processed
    :return:
    """
    docs = []
    docs.append(" ")
    docs.append(" \n\n\n ")
    docs.append(" \n   \n   \t ")
    docs.append("\t")
    docs.append("\n\n\n \t \t    \t \n")
    return docs


def create_payload_content_from_doc_single(text):
    """
    Creates a payload (dict -> JSON) compatible with the API specs for single-document processing
    :param text: input text
    :return: the payload (dict)
    """
    return {"content": {"text": text}}


def create_payload_content_from_doc_bulk(texts):
    """
    Creates a payload (dict -> JSON) compatible with the API specs for bulk-document processing
    :param texts: input texts
    :return: the payload (dict)
    """
    return {"content": [{"text": t} for t in texts]}


def setup_medcat_processor():
    # TODO: these parameters need to be externalized into config file and a custom MedCAT processor created here
    if "APP_MODEL_CDB_PATH" not in os.environ:
        log.warning("""Env variable: 'APP_MODEL_CDB_PATH': not set
                            "-- setting to default: './models/medmen/cdb.dat'""")
        os.environ["APP_MODEL_CDB_PATH"] = "./models/medmen/cdb.dat"

    if "APP_MODEL_VOCAB_PATH" not in os.environ:
        log.warning(
            "OS ENV: APP_MODEL_VOCAB_PATH: not set -- setting to default: './models/medmen/vocab.dat'")
        os.environ["APP_MODEL_VOCAB_PATH"] = "./models/medmen/vocab.dat"

    if "APP_MODEL_META_PATH_LIST" not in os.environ:
        log.warning("""OS ENV: APP_MODEL_META_PATH_LIST: not set -- setting to
                            default: './models/medmen/Status'""")
        os.environ["APP_MODEL_META_PATH_LIST"] = "./models/medmen/Status"

    if "APP_BULK_NPROC" not in os.environ:
        log.warning(
            "OS ENV: APP_BULK_NPROC: not set -- setting to default: 8")
        os.environ["APP_BULK_NPROC"] = "8"

    os.environ["MEDCAT_DEID_MODE"] = "False"
    os.environ["MEDCAT_DEID_REDACT"] = "False"
