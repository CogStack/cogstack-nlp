#!/usr/bin/env python

import logging
import os
import traceback

import simplejson as json
from flask import Blueprint, Response, request

from medcat_service.nlp_service import NlpService
from medcat_service.types import HealthCheckResponseContainer, ServiceInfo

log = logging.getLogger("API")
log.setLevel(level=os.getenv("APP_LOG_LEVEL", logging.INFO))

# define API using Flask Blueprint
#
api = Blueprint(name='api', import_name='api', url_prefix='/api')


# API endpoints definition
#
# INFO: we use dependency injection to inject the actual NLP (MedCAT) service
#
@api.route('/info', methods=['GET'])
def info(nlp_service: NlpService) -> Response:
    """
    Returns basic information about the NLP Service
    :param nlp_service: NLP Service provided by dependency injection
    :return: Flask Response
    """
    app_info: ServiceInfo = nlp_service.nlp.get_app_info()
    return Response(response=app_info.model_dump_json(), status=200, mimetype="application/json")


@api.route('/process', methods=['POST'])
def process(nlp_service: NlpService) -> Response:
    """
    Returns the annotations extracted from a provided single document
    :param nlp_service: NLP Service provided by dependency injection
    :return: Flask response
    """
    payload = request.get_json()
    if payload is None or 'content' not in payload or payload['content'] is None:
        return Response(response="Input Payload should be JSON", status=400)

    # send across the meta_anns filters in the request.
    meta_anns_filters = payload.get('meta_anns_filters', None)

    try:
        result = nlp_service.nlp.process_content(
            payload['content'], meta_anns_filters=meta_anns_filters)
        app_info: ServiceInfo = nlp_service.nlp.get_app_info()
        response = {'result': result, 'medcat_info': app_info.model_dump()}
        return Response(response=json.dumps(response, iterable_as_array=True, default=str),
                        status=200, mimetype="application/json")

    except Exception as e:
        log.error(traceback.format_exc())
        return Response(response="Internal processing error %s" % e, status=500)


@api.route('/process_bulk', methods=['POST'])
def process_bulk(nlp_service: NlpService) -> Response:
    """
    Returns the annotations extracted from the provided set of documents
    :param nlp_service: NLP Service provided by dependency injection
    :return: Flask Response
    """
    payload = request.get_json()
    if payload is None or 'content' not in payload.keys() or payload['content'] is None:
        return Response(response="Input Payload should be JSON", status=400)

    try:
        result = nlp_service.nlp.process_content_bulk(payload['content'])
        app_info: ServiceInfo = nlp_service.nlp.get_app_info()

        response = {'result': result,
                    'medcat_info': app_info.model_dump()}
        return Response(response=json.dumps(response, iterable_as_array=True, default=str),
                        status=200, mimetype="application/json")

    except Exception as e:
        log.error(traceback.format_exc())
        return Response(response="Internal processing error %s" % e, status=500)


@api.route('/retrain_medcat', methods=['POST'])
def retrain_medcat(nlp_service: NlpService) -> Response:

    payload = request.get_json()
    if payload is None or 'content' not in payload or payload['content'] is None:
        return Response(response="Input Payload should be JSON", status=400)

    try:
        result = nlp_service.nlp.retrain_medcat(payload['content'], payload['replace_cdb'])
        app_info = nlp_service.nlp.get_app_info()
        response = {'result': result,
                    'annotations': payload['content'], 'medcat_info': app_info}
        return Response(response=json.dumps(response), status=200, mimetype="application/json")

    except Exception as e:
        log.error(traceback.format_exc())
        return Response(response="Internal processing error %s" % e, status=500)


@api.route('/health/live')
def liveness():
    """
    Liveness API checks if the application is running.
    """
    response = HealthCheckResponseContainer(status="UP", checks=[])
    return Response(response=response.model_dump_json(), status=200)


@api.route('/health/ready')
def readiness(nlp_service: NlpService) -> Response:
    """
    Readiness API checks if the application is ready to start accepting traffic
    """
    medcat_is_ready = nlp_service.get_processor().is_ready()

    if medcat_is_ready.status == "UP":
        response = HealthCheckResponseContainer(
            status="UP", checks=[medcat_is_ready])
        return Response(response=response.model_dump_json(), status=200)
    else:
        response = HealthCheckResponseContainer(
            status="DOWN", checks=[medcat_is_ready])
        return Response(response=response.model_dump_json(), status=503)
