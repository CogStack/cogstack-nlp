"""Full text search of dataset documents, backed by a single shared Solr collection.

Every document is indexed with its ``dataset_id`` so a search can be scoped to one dataset,
and a dataset can be (re-)indexed or removed with a delete-by-query.
"""
import logging
import re
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from background_task import background
from opentelemetry import trace
from opentelemetry.semconv.attributes import server_attributes
from opentelemetry.semconv._incubating.attributes import service_attributes

from api.models import Document
from core.settings import SOLR_HOST, SOLR_PORT, DOCUMENT_SEARCH_COLLECTION

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("medcat-trainer")

solr_trace_attributes = {
    service_attributes.SERVICE_PEER_NAME: "medcat-trainer-solr",
    server_attributes.SERVER_ADDRESS: SOLR_HOST,
    server_attributes.SERVER_PORT: int(SOLR_PORT),
}

INDEX_BATCH_SIZE = 500
REQUEST_TIMEOUT_SECS = 30

# Control characters can't appear in sanitised document text, so they are safe highlight delimiters.
HIGHLIGHT_PRE = '\x02'
HIGHLIGHT_POST = '\x03'
_HIGHLIGHT_RE = re.compile(f'({HIGHLIGHT_PRE}.*?{HIGHLIGHT_POST})', re.DOTALL)

DOCUMENT_FIELDS = [
    {'name': 'dataset_id', 'type': 'plong', 'indexed': True, 'stored': True},
    {'name': 'doc_id', 'type': 'plong', 'indexed': True, 'stored': True},
    {'name': 'name', 'type': 'text_general', 'indexed': True, 'stored': True, 'multiValued': False},
    {'name': 'text', 'type': 'text_general', 'indexed': True, 'stored': True, 'multiValued': False},
]


class DocumentSearchUnavailable(Exception):
    """Raised when Solr can't serve a search for a dataset, so callers can fall back to the DB."""


def _base_url() -> str:
    return f'http://{SOLR_HOST}:{SOLR_PORT}/solr'


def _collection_url() -> str:
    return f'{_base_url()}/{DOCUMENT_SEARCH_COLLECTION}'


def _list_collections() -> List[str]:
    resp = requests.get(f'{_base_url()}/admin/collections', params={'action': 'LIST'},
                        timeout=REQUEST_TIMEOUT_SECS)
    if resp.status_code != 200:
        raise DocumentSearchUnavailable(f'Failed to list Solr collections: {resp.text}')
    return resp.json().get('collections', [])


def _ensure_schema_fields():
    resp = requests.get(f'{_collection_url()}/schema/fields', timeout=REQUEST_TIMEOUT_SECS)
    if resp.status_code != 200:
        raise DocumentSearchUnavailable(f'Failed to read schema of {DOCUMENT_SEARCH_COLLECTION}: {resp.text}')
    existing = {f['name'] for f in resp.json().get('fields', [])}
    missing = [f for f in DOCUMENT_FIELDS if f['name'] not in existing]
    if missing:
        resp = requests.post(f'{_collection_url()}/schema', json={'add-field': missing},
                             timeout=REQUEST_TIMEOUT_SECS)
        if resp.status_code != 200:
            raise DocumentSearchUnavailable(f'Failed to add fields to {DOCUMENT_SEARCH_COLLECTION}: {resp.text}')


@tracer.start_as_current_span("ensure_document_collection", attributes=solr_trace_attributes)
def ensure_document_collection():
    if DOCUMENT_SEARCH_COLLECTION not in _list_collections():
        resp = requests.get(f'{_base_url()}/admin/collections',
                            params={'action': 'CREATE', 'name': DOCUMENT_SEARCH_COLLECTION, 'numShards': 1},
                            timeout=REQUEST_TIMEOUT_SECS * 4)
        # another indexing task may have created it concurrently
        if resp.status_code != 200 and DOCUMENT_SEARCH_COLLECTION not in _list_collections():
            raise DocumentSearchUnavailable(f'Failed to create {DOCUMENT_SEARCH_COLLECTION}: {resp.text}')
    _ensure_schema_fields()


def _post_update(payload, commit=False):
    params = {'commit': 'true'} if commit else None
    resp = requests.post(f'{_collection_url()}/update', json=payload, params=params,
                         timeout=REQUEST_TIMEOUT_SECS * 4)
    if resp.status_code != 200:
        raise DocumentSearchUnavailable(f'Failed to update {DOCUMENT_SEARCH_COLLECTION}: {resp.text}')


def _solr_doc(doc: Dict) -> Dict:
    return {
        'id': str(doc['id']),
        'doc_id': doc['id'],
        'dataset_id': doc['dataset_id'],
        'name': doc['name'],
        'text': doc['text'],
    }


def _batched(items: Iterable, size: int) -> Iterable[List]:
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


@tracer.start_as_current_span("index_dataset_documents", attributes=solr_trace_attributes)
def index_dataset_documents(dataset_id: int) -> int:
    """Replace every indexed document of the dataset with its current documents. Returns the number indexed."""
    ensure_document_collection()
    _post_update({'delete': {'query': f'dataset_id:{int(dataset_id)}'}})
    docs = Document.objects.filter(dataset_id=dataset_id).order_by('id') \
        .values('id', 'dataset_id', 'name', 'text').iterator(chunk_size=INDEX_BATCH_SIZE)
    total = 0
    for batch in _batched(docs, INDEX_BATCH_SIZE):
        _post_update([_solr_doc(d) for d in batch])
        total += len(batch)
    _post_update({'commit': {}})
    logger.info('Indexed %s documents of dataset %s into Solr collection %s',
                total, dataset_id, DOCUMENT_SEARCH_COLLECTION)
    return total


@tracer.start_as_current_span("remove_dataset_documents", attributes=solr_trace_attributes)
def remove_dataset_documents(dataset_id: int):
    if DOCUMENT_SEARCH_COLLECTION not in _list_collections():
        return
    _post_update({'delete': {'query': f'dataset_id:{int(dataset_id)}'}}, commit=True)


@background(schedule=1)
def index_dataset_task(dataset_id: int):
    index_dataset_documents(dataset_id)


@background(schedule=1)
def remove_dataset_task(dataset_id: int):
    remove_dataset_documents(dataset_id)


def _select(params: Dict) -> Dict:
    try:
        resp = requests.get(f'{_collection_url()}/select', params=params, timeout=REQUEST_TIMEOUT_SECS)
    except requests.RequestException as e:
        raise DocumentSearchUnavailable(f'Solr not reachable: {e}') from e
    if resp.status_code != 200:
        raise DocumentSearchUnavailable(f'Solr search of {DOCUMENT_SEARCH_COLLECTION} failed: {resp.text}')
    return resp.json()


def indexed_document_count(dataset_id: int) -> int:
    resp = _select({'q': '*:*', 'fq': f'dataset_id:{int(dataset_id)}', 'rows': 0})
    return resp['response']['numFound']


def _phrase_query(text: str) -> str:
    escaped = text.replace('\\', '\\\\').replace('"', '\\"')
    return f'text:"{escaped}"'


def highlight_segments(snippet: str) -> List[Dict]:
    segments = []
    for part in _HIGHLIGHT_RE.split(snippet):
        if not part:
            continue
        if part.startswith(HIGHLIGHT_PRE) and part.endswith(HIGHLIGHT_POST):
            segments.append({'text': part[len(HIGHLIGHT_PRE):-len(HIGHLIGHT_POST)], 'match': True})
        else:
            segments.append({'text': part, 'match': False})
    return segments


@tracer.start_as_current_span("search_dataset_documents", attributes=solr_trace_attributes)
def search_dataset_documents(dataset_id: int, text: str, start: int, rows: int,
                             expected_doc_count: Optional[int] = None) -> Tuple[int, List[Tuple[int, Optional[List]]]]:
    """Phrase search the dataset's documents.

    Returns the total number of matches and, for the requested page, (document id, highlight segments) pairs.
    Raises DocumentSearchUnavailable if Solr is unavailable or (when ``expected_doc_count`` is given) the
    dataset is not yet fully indexed.
    """
    if expected_doc_count is not None and indexed_document_count(dataset_id) != expected_doc_count:
        raise DocumentSearchUnavailable(f'Dataset {dataset_id} is not fully indexed in {DOCUMENT_SEARCH_COLLECTION}')
    resp = _select({
        'q': _phrase_query(text),
        'fq': f'dataset_id:{int(dataset_id)}',
        'fl': 'id,doc_id',
        'sort': 'score desc,doc_id asc',
        'start': start,
        'rows': rows,
        'hl': 'true',
        'hl.method': 'unified',
        'hl.fl': 'text',
        'hl.snippets': 1,
        'hl.fragsize': 160,
        'hl.maxAnalyzedChars': 1000000,
        'hl.tag.pre': HIGHLIGHT_PRE,
        'hl.tag.post': HIGHLIGHT_POST,
    })
    highlighting = resp.get('highlighting', {})
    hits = []
    for d in resp['response']['docs']:
        snippets = highlighting.get(d['id'], {}).get('text') or []
        hits.append((int(d['doc_id']), highlight_segments(snippets[0]) if snippets else None))
    return resp['response']['numFound'], hits
