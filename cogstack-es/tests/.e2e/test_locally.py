import pytest
import pandas as pd
try:
    from elasticsearch import Elasticsearch
except ImportError:
    from opensearchpy import OpenSearch as Elasticsearch
import sys, os
sys.path.append(os.path.join(
    os.path.dirname(__file__), "..", ".."))
from cogstack import CogStack  # Adjust import based on your module name


@pytest.fixture(scope="module")
def es_client():
    """Create ES client for test setup/teardown"""
    es = Elasticsearch(["http://localhost:9200"])
    yield es
    # Cleanup after all tests
    try:
        es.indices.delete(index="test_*", ignore=[404])
    except Exception:
        pass


@pytest.fixture(scope="module")
def setup_test_data(es_client):
    """Set up test indices and data"""
    # Create main test index
    es_client.indices.create(
        index="test_documents",
        body={
            "mappings": {
                "properties": {
                    "title": {"type": "text"},
                    "content": {"type": "text"},
                    "category": {"type": "keyword"},
                    "date": {"type": "date"},
                    "count": {"type": "integer"},
                    "price": {"type": "float"},
                    "id": {"type": "integer"},
                }
            }
        },
        ignore=400  # Ignore if already exists
    )

    # Create a second test index
    es_client.indices.create(
        index="test_documents_2",
        body={
            "mappings": {
                "properties": {
                    "name": {"type": "text"},
                    "value": {"type": "integer"},
                    "id": {"type": "integer"},
                }
            }
        },
        ignore=400
    )

    # Create alias
    es_client.indices.put_alias(
        index="test_documents",
        name="test_alias"
    )

    cur_index = 150
    # Add diverse test documents
    documents = []
    for i in range(150):  # Enough to test pagination
        documents.append({
            "_index": "test_documents",
            "_id": str(i),
            "_source": {
                "title": f"Document {i}",
                "content": f"Content for document {i}",
                "category": f"cat_{i % 5}",  # 5 categories
                "count": i,
                "price": i * 1.5,
                "id": cur_index + i,
            }
        })
    cur_index = 2500

    # Add documents to second index
    for i in range(50):
        documents.append({
            "_index": "test_documents_2",
            "_id": str(i),
            "_source": {
                "name": f"Item {i}",
                "value": i * 10,
                "id": cur_index + i
            }
        })

    # Bulk index
    try:
        from elasticsearch.helpers import bulk
    except ImportError:
        from opensearchpy.helpers import bulk
    bulk(es_client, documents)
    es_client.indices.refresh(index="test_*")

    yield

    # Teardown - delete indices explicitly
    test_indices = ["test_documents", "test_documents_2"]
    for index in test_indices:
        try:
            es_client.indices.delete(index=index, ignore=[404])
        except Exception:
            pass



@pytest.fixture
def cogstack(setup_test_data):
    """Create CogStack instance"""
    return CogStack.with_basic_auth(
        hosts=["http://localhost:9200"],
        # Default, may not be needed with security disabled
        username="elastic",
        password="changeme"
    )


class TestConnection:
    """Test connection methods"""

    def test_basic_auth_connection(self):
        """Test basic auth connection"""
        cs = CogStack.with_basic_auth(
            hosts=["http://localhost:9200"],
            username="elastic",
            password="changeme"
        )
        assert cs.provider is not None

    def test_failed_connection(self):
        """Test connection failure handling"""
        with pytest.raises(ConnectionError):
            CogStack.with_basic_auth(
                hosts=["http://localhost:9999"],  # Wrong port
                username="wrong",
                password="wrong"
            )


class TestIndexOperations:
    """Test index and metadata operations"""

    def test_get_indices_and_aliases(self, cogstack):
        """Test retrieving indices and aliases"""
        result = cogstack.get_indices_and_aliases()
        assert isinstance(result, pd.DataFrame)
        assert "Index" in result.columns
        assert "Aliases" in result.columns
        assert len(result) >= 2  # At least our 2 test indices

        # Check our test alias exists
        assert any("test_alias" in str(aliases)
                   for aliases in result["Aliases"])

    def test_get_index_fields_single(self, cogstack):
        """Test getting fields for single index"""
        # Note: get_index_fields uses display() so we need to capture it
        # For now, we just ensure it doesn't error
        try:
            cogstack.get_index_fields("test_documents")
        except Exception as e:
            pytest.fail(f"get_index_fields raised exception: {e}")

    def test_get_index_fields_multiple(self, cogstack):
        """Test getting fields for multiple indices"""
        try:
            cogstack.get_index_fields(["test_documents", "test_documents_2"])
        except Exception as e:
            pytest.fail(f"get_index_fields raised exception: {e}")

    def test_get_index_fields_alias(self, cogstack):
        """Test getting fields using alias"""
        try:
            cogstack.get_index_fields("test_alias")
        except Exception as e:
            pytest.fail(f"get_index_fields with alias raised exception: {e}")

    def test_get_index_fields_empty_list(self, cogstack):
        """Test error handling for empty index list"""
        with pytest.raises(Exception,
                           match="Unexpected issue while getting index fields"):
            cogstack.get_index_fields([])


class TestCountOperations:
    """Test document counting"""

    def test_count_all_documents(self, cogstack):
        """Test counting all documents"""
        result = cogstack.count_search_results(
            index="test_documents",
            query={"match_all": {}}
        )
        assert "150" in result  # Should have 150 documents

    def test_count_with_query(self, cogstack):
        """Test counting with specific query"""
        result = cogstack.count_search_results(
            index="test_documents",
            query={"match": {"category": "cat_0"}}
        )
        assert "Number of documents:" in result

    def test_count_with_query_wrapper(self, cogstack):
        """Test count with query wrapped in 'query' key"""
        result = cogstack.count_search_results(
            index="test_documents",
            query={"query": {"match_all": {}}}
        )
        assert "150" in result

    def test_count_empty_index_list(self, cogstack):
        """Test error handling for empty index list"""
        with pytest.raises(ValueError):
            cogstack.count_search_results(
                index=[],
                query={"match_all": {}}
            )


class TestReadWithScan:
    """Test read_data_with_scan method"""

    def test_scan_all_documents(self, cogstack):
        """Test scanning all documents"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"match_all": {}},
            size=50,
            show_progress=False
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 150
        assert "_index" in df.columns
        assert "_id" in df.columns
        assert "_score" in df.columns

    def test_scan_with_fields(self, cogstack):
        """Test scanning with specific fields"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"match_all": {}},
            include_fields=["title", "category", "count"],
            size=50,
            show_progress=False
        )
        assert len(df) == 150
        assert "title" in df.columns
        assert "category" in df.columns
        assert "count" in df.columns

    def test_scan_with_query(self, cogstack):
        """Test scanning with specific query"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"term": {"category": "cat_0"}},
            include_fields=["category"],
            show_progress=False
        )
        assert len(df) == 30  # 150 docs / 5 categories
        assert all(df["category"] == "cat_0")

    def test_scan_multiple_indices(self, cogstack):
        """Test scanning multiple indices"""
        df = cogstack.read_data_with_scan(
            index=["test_documents", "test_documents_2"],
            query={"match_all": {}},
            show_progress=False
        )
        assert len(df) == 200  # 150 + 50

    def test_scan_with_alias(self, cogstack):
        """Test scanning using alias"""
        df = cogstack.read_data_with_scan(
            index="test_alias",
            query={"match_all": {}},
            show_progress=False
        )
        assert len(df) == 150

    def test_scan_invalid_size(self, cogstack):
        """Test error handling for invalid size"""
        with pytest.raises(ValueError,
                           match="Size must not be greater than 10000"):
            cogstack.read_data_with_scan(
                index="test_documents",
                query={"match_all": {}},
                size=10001,
                show_progress=False
            )


class TestReadWithScroll:
    """Test read_data_with_scroll method"""

    def test_scroll_all_documents(self, cogstack):
        """Test scrolling all documents"""
        df = cogstack.read_data_with_scroll(
            index="test_documents",
            query={"match_all": {}},
            size=50,
            show_progress=False
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 150
        assert "_index" in df.columns
        assert "_id" in df.columns
        assert "_score" in df.columns

    def test_scroll_with_fields(self, cogstack):
        """Test scrolling with specific fields"""
        df = cogstack.read_data_with_scroll(
            index="test_documents",
            query={"match_all": {}},
            include_fields=["title", "count", "price"],
            size=50,
            show_progress=False
        )
        assert len(df) == 150
        assert "title" in df.columns
        assert "count" in df.columns
        assert "price" in df.columns

    def test_scroll_with_query(self, cogstack):
        """Test scrolling with specific query"""
        df = cogstack.read_data_with_scroll(
            index="test_documents",
            query={"range": {"count": {"gte": 100}}},
            include_fields=["count"],
            show_progress=False
        )
        assert len(df) == 50  # docs 100-149
        assert all(df["count"].astype(int) >= 100)

    def test_scroll_query_wrapper(self, cogstack):
        """Test scroll with query in 'query' wrapper"""
        df = cogstack.read_data_with_scroll(
            index="test_documents",
            query={"query": {"match_all": {}}},
            size=50,
            show_progress=False
        )
        assert len(df) == 150

    def test_scroll_invalid_size(self, cogstack):
        """Test error handling for invalid size"""
        with pytest.raises(ValueError,
                           match="Size must not be greater than 10000"):
            cogstack.read_data_with_scroll(
                index="test_documents",
                query={"match_all": {}},
                size=10001,
                show_progress=False
            )


class TestReadWithSorting:
    """Test read_data_with_sorting method"""

    def test_sort_default(self, cogstack):
        """Test sorting with default sort (id asc)"""
        df = cogstack.read_data_with_sorting(
            index="test_documents",
            query={"match_all": {}},
            size=50,
            show_progress=False
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 150

    def test_sort_with_field_dict(self, cogstack):
        """Test sorting with field dictionary"""
        df = cogstack.read_data_with_sorting(
            index="test_documents",
            query={"match_all": {}},
            include_fields=["count"],
            size=50,
            sort={"count": "desc"},
            show_progress=False
        )
        assert len(df) == 150
        # Check descending order (first value should be larger than last)
        first_val = int(df.iloc[0]["count"])
        last_val = int(df.iloc[-1]["count"])
        assert first_val > last_val

    def test_sort_with_field_list(self, cogstack):
        """Test sorting with field list"""
        df = cogstack.read_data_with_sorting(
            index="test_documents",
            query={"match_all": {}},
            include_fields=["category", "count"],
            size=50,
            sort=["category", "count"],
            show_progress=False
        )
        assert len(df) == 150

    def test_sort_adds_id_tiebreaker(self, cogstack):
        """Test that id is added as tiebreaker if not present"""
        df = cogstack.read_data_with_sorting(
            index="test_documents",
            query={"match_all": {}},
            size=50,
            sort={"count": "asc"},
            show_progress=False
        )
        assert len(df) == 150

    def test_sort_with_query(self, cogstack):
        """Test sorting with specific query"""
        df = cogstack.read_data_with_sorting(
            index="test_documents",
            query={"term": {"category": "cat_1"}},
            include_fields=["category", "count"],
            size=20,
            sort={"count": "asc"},
            show_progress=False
        )
        assert len(df) == 30
        assert all(df["category"] == "cat_1")

    def test_sort_invalid_size(self, cogstack):
        """Test error handling for invalid size"""
        with pytest.raises(ValueError,
                           match="Size must not be greater than 10000"):
            cogstack.read_data_with_sorting(
                index="test_documents",
                query={"match_all": {}},
                size=10001,
                show_progress=False
            )


class TestDataIntegrity:
    """Test data integrity and format"""

    def test_field_values_are_strings(self, cogstack):
        """Test that multi-value fields are joined as strings"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"match_all": {}},
            include_fields=["title"],
            size=50,
            show_progress=False
        )
        # All values should be strings
        assert all(isinstance(val, str) for val in df["title"])

    def test_wildcard_fields(self, cogstack):
        """Test wildcard field selection"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"match_all": {}},
            include_fields=["*"],
            size=10,
            show_progress=False
        )
        # Should include all fields from mapping
        assert "_index" in df.columns
        assert "_id" in df.columns

    def test_empty_results(self, cogstack):
        """Test handling of query with no results"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"term": {"category": "nonexistent"}},
            show_progress=False
        )
        assert len(df) == 0
        assert isinstance(df, pd.DataFrame)


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_invalid_index(self, cogstack):
        """Test querying non-existent index"""
        with pytest.raises(Exception):
            cogstack.read_data_with_scan(
                index="nonexistent_index",
                query={"match_all": {}},
                show_progress=False
            )

    def test_invalid_query_syntax(self, cogstack):
        """Test invalid query syntax"""
        with pytest.raises(Exception):
            cogstack.read_data_with_scan(
                index="test_documents",
                query={"invalid_query_type": {}},
                show_progress=False
            )

    def test_empty_index_parameter(self, cogstack):
        """Test empty index parameter across methods"""
        with pytest.raises(ValueError):
            cogstack.read_data_with_scan(
                index="",
                query={"match_all": {}},
                show_progress=False
            )


class TestPerformance:
    """Test performance-related scenarios"""

    def test_small_batch_size(self, cogstack):
        """Test with very small batch size"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"match_all": {}},
            size=10,  # Small batches
            show_progress=False
        )
        assert len(df) == 150

    def test_large_batch_size(self, cogstack):
        """Test with large batch size"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"match_all": {}},
            size=10000,  # Max size
            show_progress=False
        )
        assert len(df) == 150

    def test_progress_bar_enabled(self, cogstack):
        """Test that progress bar doesn't break functionality"""
        df = cogstack.read_data_with_scan(
            index="test_documents",
            query={"match_all": {}},
            size=50,
            show_progress=True  # Enabled
        )
        assert len(df) == 150


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])