
# Login and search
This project is responsible for logging in and performing a search for Elasticsearch or Opensearch.

# Installation

This package is distributed through PyPI and can be installed using one of:
```
pip install cogstack-es[ES9]  # For Elasticsearch 9
pip install cogstack-es[ES8]  # For Elasticsearch 8
pip install cogstack-es[OS]  # For Opensearch
```

PS:
After installation, the import still remains `import cogstack` even though the installed package is called `cogstack-es`.

## Login details
You need to get your login details and host from your administrator.
This is usually an API key.
An example template can be seen below:
```
hosts = []  # This is a list of your cogstack elasticsearch instances.

# These are your login details (either via http_auth or API)
username = None
password = None
```

__Note__: If these fields are left blank then the user will be prompted to enter the details themselves.

If you are unsure about the above information please contact your CogStack system administrator.

## How to build a Search query

A core component of cogstack is Elasticsearch which is a search engine built on top of Apache Lucene.

Lucene has a custom query syntax for querying its indexes (Lucene Query Syntax). This query syntax allows for features such as Keyword matching, Wildcard matching, Regular expression, Proximity matching, Range searches.

Full documentation for this syntax is available as part of Elasticsearch [query string syntax](https://www.elastic.co/guide/en/elasticsearch/reference/8.5/query-dsl-query-string-query.html#query-string-syntax).