# test_setup.py
from opensearchpy import OpenSearch

os = OpenSearch(["http://localhost:9200"])

# Create test index with mapping
os.indices.create(
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
    os.index(
        index="test_documents",
        id=str(i),
        document={
            "title": f"Document {i}",
            "content": f"Content for document {i}",
            "count": i
        }
    )

os.indices.refresh(index="test_documents")
