# test_setup.py
from elasticsearch import Elasticsearch

es = Elasticsearch(["http://localhost:9200"])

# Create test index with mapping
es.indices.create(
    index="test_documents",
    body={
        "mappings": {
            "properties": {
                "title": {"type": "text"},
                "content": {"type": "text"},
                "date": {"type": "date"},
                "count": {"type": "integer"}
            }
        }
    }
)

# Add test documents
for i in range(1000):
    es.index(
        index="test_documents",
        id=str(i),
        document={
            "title": f"Document {i}",
            "content": f"Content for document {i}",
            "count": i
        }
    )

es.indices.refresh(index="test_documents")
