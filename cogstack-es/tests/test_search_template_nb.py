import nbformat
from nbconvert import PythonExporter
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import tempfile
import os
import pytest

from cogstack import read_creds
from cogstack.cogstack import has_elasticsearch


EXPECTED_TEMP_FILE_PATH = os.path.join(
    "data", "cogstack_search_results", "file_name.csv")


@contextmanager
def all_mocked(python_code: str):
    with tempfile.NamedTemporaryFile('w', suffix='.py') as temp_file:
        temp_file.write(python_code)
        client_cls_path = (
            'cogstack.es.Elasticsearch' if has_elasticsearch()
            else 'cogstack.os.OpenSearch')
        with patch(client_cls_path) as mock_es:
            with patch.dict('os.environ', {
                        read_creds.CS_HOSTS_ENV: 'http://localhost:9200',
                        read_creds.CS_API_KEY_ENCODED_ENV: "TEST-API-KEY",
                    }):
                helpers_scan_path = (
                    'elasticsearch.helpers.scan' if has_elasticsearch()
                    else 'opensearchpy.helpers.scan'
                )
                with patch(helpers_scan_path) as mock_scan:
                    with patch('tqdm.tqdm') as mock_tqdm:
                        yield (temp_file.name, mock_es,
                               mock_scan, mock_tqdm)


def setup_mocks(mock_es: MagicMock, mock_scan: MagicMock,
                mock_tqdm: MagicMock):
    # Setup mocks
    mock_client = Mock()
    mock_es.return_value = mock_client
    mock_client.ping.return_value = True

    if has_elasticsearch():
        mock_aliases = Mock()
        mock_aliases.body = {
            'index1': {'aliases': {'alias1': {}}}
        }
        mock_mapping = Mock()
        mock_mapping.body = {
            'index1': {'mappings': {'properties': {}}}
        }
    else:
        mock_aliases = {
            'index1': {'aliases': {'alias1': {}}}
        }
        mock_mapping = {
            'index1': {'mappings': {'properties': {}}}
        }
    # Mock Elasticsearch responses
    mock_client.indices.get_alias.return_value = mock_aliases
    mock_client.indices.get_mapping.return_value = mock_mapping
    mock_client.count.return_value = {'count': 10}

    # Mock scan results
    mock_hits = MagicMock()
    mock_hits.__iter__.return_value = [{
        '_index': 'test', '_id': '1', '_score': 1.0,
        'fields': {'test_field': ['value']}
    }]
    mock_scan.return_value = mock_hits
    mock_tqdm.return_value = mock_hits
    mock_tqdm.total = 1


@pytest.fixture
def temp_file_remover():
    yield
    if os.path.exists(EXPECTED_TEMP_FILE_PATH):
        os.remove(EXPECTED_TEMP_FILE_PATH)


def test_notebook_execution(temp_file_remover):
    """Execute the notebook with mocked dependencies"""

    # Read the notebook
    notebook_path = 'search_template.ipynb'
    with open(notebook_path, 'r') as f:
        notebook = nbformat.read(f, as_version=4)

    # Convert to Python code
    exporter = PythonExporter()
    python_code, _ = exporter.from_notebook_node(notebook)

    # Mock all the dependencies
    with all_mocked(python_code) as (temp_code_path, mock_es,
                                     mock_scan, mock_tqdm):
        setup_mocks(mock_es, mock_scan, mock_tqdm)

        # Execute the notebook code
        exec(python_code, {
            '__file__': temp_code_path,
            '__name__': '__main__'
        })
    assert os.path.exists(EXPECTED_TEMP_FILE_PATH)
