import json
import logging
import re
from typing import List, Dict

import requests
from django.http import HttpResponseServerError
from medcat.cdb import CDB
from medcat.cdb.concepts import CUIInfo
from rest_framework.response import Response

from api.models import ConceptDB
from core.settings import SOLR_HOST, SOLR_PORT

SOLR_INDEX_SCHEMA = {}

logger = logging.getLogger(__name__)


def _cache_solr_collection_schema_types(collection):
    url = f'http://{SOLR_HOST}:{SOLR_PORT}/solr/{collection}/schema'
    logger.info(f'Retrieving solr schema: {url}')
    try:
        resp = json.loads(requests.get(url).text)
        cui_type = [n for n in resp['schema']['fields'] if n['name'] == 'cui'][0]['type']
        # just store cui type for the time being
        SOLR_INDEX_SCHEMA[collection] = {'cui': cui_type}
    except ConnectionError as e:
        logger.error(f'Error connecting to solr search service to retrieve schema for collection: {collection}')
        raise e


def collections_available(cdbs: List[int]):
    url = f'http://{SOLR_HOST}:{SOLR_PORT}/solr/admin/collections?action=LIST'
    resp = requests.get(url)
    if resp.status_code == 200:
        collections = json.loads(resp.text)['collections']
        # cache schema field types
        for col in collections:
            _cache_solr_collection_schema_types(col)
        current_collections_cdb_ids = [c.split('_id_')[-1] for c in collections]
        if len(cdbs):
            return Response({'results': {cdb_id: cdb_id in current_collections_cdb_ids for cdb_id in cdbs}})
        else:
            return Response({'results': {cdb_id: {'imported': False, 'index_name': col}
                                         for cdb_id, col in zip(current_collections_cdb_ids, collections)}})
    else:
        return HttpResponseServerError('Error requesting solr concept search collection list')


def _process_result_repsonse(resp: Dict):
    uniq_results_map = {}
    docs = [d for d in resp['response']['docs']]
    for d in docs:
        if d['cui'][0] not in uniq_results_map:
            parsed_doc = {
                'cui': str(d['cui'][0]),
                'pretty_name': d['pretty_name'][0],
                'type_ids': d.get('type_ids', []),
                'synonyms': d['synonyms']
            }
            uniq_results_map[d['cui'][0]] = parsed_doc
    return uniq_results_map


def search_collection(cdbs: List[int], raw_query: str):
    query = raw_query.strip().replace(r'\s+', r'\s').split(' ')
    if len(query) == 1 and query[0] == '':
        return Response({'results': []})
    res = []
    if len(cdbs) > 0:
        uniq_results_map = {}
        for cdb in cdbs:
            cdb_model = ConceptDB.objects.get(id=cdb)
            collection_name = f'{cdb_model.name}_id_{cdb_model.id}'
            if collection_name not in SOLR_INDEX_SCHEMA:
                _cache_solr_collection_schema_types(collection_name)
            try:
                query_num = int(query[0])
                query_str = f'cui:{query_num}'
            except ValueError:
                # cannot be a cui if multi-word, OR single word, not a numeric cui
                query_str = f'name:"{" ".join(query)}"^2 synonyms:"{" ".join(query)}"'
                if len(query) == 1 and SOLR_INDEX_SCHEMA[collection_name]['cui'] != 'plongs':
                    # single word, alphanumeric cui type.
                    query_str = f'cui:{query[0]} ' + query_str

            solr_url = f'http://{SOLR_HOST}:{SOLR_PORT}/solr/{collection_name}/select?q.op=OR&q={query_str}&rows=15'
            logger.info(f'Searching solr collection: {solr_url}')
            resp = json.loads(requests.get(solr_url).text)

            if 'error' in resp:
                return HttpResponseServerError(f'Concept Search Index {collection_name} not available, '
                                               f'import concept DB first before trying to search it.')
            elif len(resp['response']['docs']) == 0:
                # try with wildcards at the end of the entire query, rather than each token
                fallback_query = f'name:{" ".join(query)}* synonyms:{" ".join(query)}*'
                solr_url = f'http://{SOLR_HOST}:{SOLR_PORT}/solr/{collection_name}/select?q.op=OR&q={fallback_query}&rows=15'
                logger.info(f'Searching solr collection with fall back query at url: {solr_url}')
                resp = json.loads(requests.get(solr_url).text)
                uniq_results_map.update(_process_result_repsonse(resp))
            else:
                uniq_results_map.update(_process_result_repsonse(resp))

        res = sorted(uniq_results_map.values(), key=lambda r: len(r['pretty_name']))
    return Response({'results': res})


def import_all_concepts(cdb: CDB, cdb_model: ConceptDB):
    collection_name = f'{cdb_model.name}_id_{cdb_model.id}'
    base_url = f'http://{SOLR_HOST}:{SOLR_PORT}/solr'

    # check if solr collections already exists.
    url = f'{base_url}/admin/collections?action=LIST'
    resp = requests.get(url)
    if resp.status_code != 200:
        logger.error("Error connecting to Solr to retrieve current collection list")
        raise Exception("Error connecting to Solr to retrieve current collection list")

    collections = json.loads(resp.text)['collections']
    if collection_name in collections:
        # delete collection
        url = f'{base_url}/admin/collections?action=DELETE&name={collection_name}'
        requests.get(url)

    # create solr collections.
    url = f'{base_url}/admin/collections?action=CREATE&name={collection_name}&numShards=1'
    resp = requests.get(url)
    if resp.status_code != 200:
        _solr_error_response(resp, 'Failure creating collection')

    cui2info_iter = iter(cdb.cui2info.items())

    payload = []
    try:
        while True:
            for i in range(5000):
                cui, info = next(cui2info_iter)
                concept_dct = _concept_dct(cui, cdb, info)
                payload.append(concept_dct)
            _upload_payload(f'{base_url}/{collection_name}/update', payload, collection_name)
            payload = []
    except StopIteration:
        # upload last update
        _upload_payload(f'{base_url}/{collection_name}/update', payload, collection_name, commit=True)

    # get final collection size
    logger.info(f'Successfully uploaded {cdb_model.name} cuis / names to solr collection {collection_name}')

    resp = requests.get(f'{base_url}/{collection_name}/select?q=*:*&rows=0')
    logger.info(f'{json.loads(resp.text)["response"]["numFound"]} Concepts now searchable')


def drop_collection(cdb_model: ConceptDB):
    collection_name = f'{cdb_model.name}_id_{cdb_model.id}'
    base_url = f'http://{SOLR_HOST}:{SOLR_PORT}/solr'
    url = f'{base_url}/admin/collections?action=DELETE&name={collection_name}'
    resp = requests.get(url)
    if resp.status_code == 200:
        logger.info(f'Successfullly dropped concept collection:{collection_name}')
    else:
        logger.warning(f'Error dropping concept collection {collection_name}, error: {resp.text}')


def ensure_concept_searchable(cui, cdb: CDB, cdb_model: ConceptDB):
    """
    Adds a single cui and associated metadata is available in the assocaited solr search index.
    Args:
        cui: concept unique identifier of the concept to make searchable
        cdb: the MedCAT CDB where the cui can be found
        cdb_model: the associated Django model instance for the CDB.
    """
    collection = f'{cdb_model.name}_id_{cdb_model.id}'
    base_url = f'http://{SOLR_HOST}:{SOLR_PORT}/solr'
    url = f'{base_url}/admin/collections?action=LIST'
    resp = requests.get(url)
    if resp.status_code == 200:
        collections = json.loads(resp.text)['collections']
        data = [_concept_dct(cui, cdb, cdb.cui2info[cui])]
        if collection in collections:
            _upload_payload(f'{base_url}/{collection}/update', data, collection, commit=True)


def _upload_payload(update_url, data, collection, commit=False):
    update_url = f'{update_url}?commit=true' if commit else update_url
    logger.info(f'Uploading {len(data)} to solr collection {collection}')
    resp = requests.post(update_url, json=data)
    if resp.status_code == 200:
        logger.info(f'Successfully uploaded {len(data)} concepts to solr collection {collection}')
    elif resp.status_code != 200:
        _solr_error_response(resp, f'error updating {collection}')


def _concept_dct(cui: str, cdb: CDB, info: CUIInfo):
    synonyms = list(info['original_names'] or [])
    concept_dct = {
        'cui': str(cui),
        'pretty_name': cdb.get_name(cui),
        'name': re.sub(r'\([\w+\s]+\)', '', cdb.get_name(cui)).strip(),
        'type_ids': list(info['type_ids']),
        'desc': info['description'],
        'synonyms': synonyms if len(synonyms) > 0 else [cdb.get_name(cui)]
    }
    return concept_dct


def _solr_error_response(resp, error_msg):
    try:
        error = json.loads(resp.text)['error']
    except Exception as e:
        logger.error(f'{error_msg}: unknown error')
        raise e
    error_msg = f'{error_msg}: solr error: {error}'
    logger.error(error_msg)
    raise Exception(error_msg)
