import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from cogstack import CogStack
from cogstack.cogstack import has_elasticsearch


@pytest.fixture
def mock_elasticsearch():
    """Fixture to mock Elasticsearch client"""
    client_cls_path = (
        'cogstack.es.Elasticsearch' if has_elasticsearch()
        else 'cogstack.os.OpenSearch')
    with patch(client_cls_path) as mock_es:
        mock_client = Mock()
        mock_es.return_value = mock_client
        mock_client.ping.return_value = True
        print("With Mock ES...")
        yield mock_es, mock_client
    print("DONE WITH MOCK ES")


def test_basic_auth_connection(mock_elasticsearch: tuple[MagicMock, Mock]):
    """Test basic authentication"""
    dunder_init, _ = mock_elasticsearch
    with patch('builtins.input', return_value='test_user'):
        with patch('getpass.getpass', return_value='test_pass'):
            cs = CogStack.with_basic_auth(['http://localhost:9200'])
            assert isinstance(cs, CogStack)
            assert cs.provider.ping()
            dunder_init.assert_called_once()


def test_api_key_auth_connection(mock_elasticsearch: tuple[MagicMock, Mock]):
    """Test API key authentication"""
    dunder_init, _ = mock_elasticsearch
    api_key = {"encoded": "test_encoded_key"}
    cs = CogStack.with_api_key_auth(['http://localhost:9200'], api_key)
    assert isinstance(cs, CogStack)
    assert cs.provider.ping()
    dunder_init.assert_called_once()


def test_count_search_results(mock_elasticsearch: tuple[MagicMock, Mock]):
    """Test count_search_results method"""
    # Mock the count response
    _, mock_inst = mock_elasticsearch
    mock_inst.count_raw.return_value = 100

    cs = CogStack(['http://localhost:9200'])
    cs.provider = mock_inst

    query = {"match": {"title": "test"}}
    result = cs.count_search_results('test_index', query)

    assert "100" in result
    mock_inst.count_raw.assert_called_once()


def test_read_data_with_scan(mock_elasticsearch: tuple[MagicMock, Mock]):
    """Test read_data_with_scan method"""
    _, mock_inst = mock_elasticsearch
    # Mock scan results
    mock_hits = MagicMock()
    mock_hits.__iter__.return_value = [
        {'_index': 'test_index', '_id': '1', '_score': 1.0,
         'fields': {'title': 'test1'}},
        {'_index': 'test_index', '_id': '2', '_score': 0.8,
         'fields': {'title': 'test2'}}
    ]

    # Mock scan helper
    scan_path = (
        'cogstack.es.ClientWrapper.scan' if has_elasticsearch()
        else 'cogstack.os.ClientWrapper.scan')
    with patch(scan_path) as mock_scan, \
         patch('cogstack.cogstack.tqdm.tqdm') as mock_tqdm:

        mock_scan.return_value = mock_hits
        mock_tqdm.return_value = mock_hits  # Make tqdm iterable
        mock_tqdm.total = 2

        # Mock count for progress bar
        mock_inst.count_raw.return_value = 2

        cs = CogStack(['http://localhost:9200'])
        cs.provider = mock_inst

        query = {"query": {"match": {"title": "test"}}}
        result = cs.read_data_with_scan('test_index', query, ['title'])

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert 'title' in result.columns


def _counting_source(n_docs, pulled):
    """Stand-in for provider.scan: a lazy generator that records every doc
    handed out, so a test can see how much has been fetched at any moment."""
    for i in range(n_docs):
        pulled.append(i)
        yield {'_index': 'test_index', '_id': str(i), '_score': 1.0,
               'fields': {'title': [f'doc{i}']}}


def _cs_with_source(mock_inst, n_docs, pulled):
    mock_inst.scan.return_value = _counting_source(n_docs, pulled)
    # >= 1000 so the formatted count contains a thousands separator
    mock_inst.count_raw.return_value = 10_000
    cs = CogStack(['http://localhost:9200'])
    cs.provider = mock_inst
    return cs


def test_read_data_with_scan_materialises_everything(mock_elasticsearch):
    """One call pulls the whole result set before returning anything."""
    _, mock_inst = mock_elasticsearch
    pulled = []
    cs = _cs_with_source(mock_inst, 10, pulled)

    df = cs.read_data_with_scan(
        'test_index', {"match": {"title": "test"}}, ['title'],
        size=3, show_progress=False)

    assert len(pulled) == 10
    assert len(df) == 10


def test_iter_data_with_scan_yields_in_chunks(mock_elasticsearch):
    """Docs are only pulled from the source as each chunk is requested."""
    _, mock_inst = mock_elasticsearch
    pulled = []
    cs = _cs_with_source(mock_inst, 10, pulled)

    chunks = cs.iter_data_with_scan(
        'test_index', {"match": {"title": "test"}}, ['title'],
        size=3, show_progress=False)
    assert len(pulled) == 0  # nothing fetched until iterated

    assert len(next(chunks)) == 3
    assert len(pulled) == 3  # only the first chunk has been pulled

    assert len(next(chunks)) == 3
    assert len(pulled) == 6

    assert [len(c) for c in chunks] == [3, 1]  # remainder
    assert len(pulled) == 10
