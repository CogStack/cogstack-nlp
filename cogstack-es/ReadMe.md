
# Login and search
This project is responsible for logging in and performing a search for Elasticsearch or Opensearch.

# Installation

This package is distributed through PyPI and can be installed using one of:
```
pip install "cogstack-es[ES9]"  # For Elasticsearch 9
pip install "cogstack-es[ES8]"  # For Elasticsearch 8
pip install "cogstack-es[OS]"  # For Opensearch
```

PS:
After installation, the import still remains `import cogstack` even though the installed package is called `cogstack-es`.

## Login details
You need to get your login details and host from your administrator.
This is usually an API key.
There is also a mechanism for reading hosts and credentials from environmental variables:
```python
from cogstack import read_from_env, CogStack
hosts, api_key, (username, password) = read_from_env()
# subsequently use one of
cs = CogStack.with_api_key_auth(hosts=hosts, api_key=api_key)
#cs = CogStack.with_basic_auth(hosts=hosts, username=username, password=password)
```
The `read_from_env` method will read the data from the following environmental variables:

| Environmetnal variable name    |  Description                        | Example value |
| ------------------------------ | ----------------------------------- | ------------- |
| `COGSTACK_HOSTS`               | The host addresses, comma separated | `http://localhost:9200,http://localhost:9201` |
| `COGSTACK_USERNAME`            | The username for basic auth         | `user123`     |
| `COGSTACK_PASSWORD`            | The password for basic auth         | `sup3rsecur3-pw#946` |
| `COGSTACK_API_KEY_ID`          | The API key ID for authentiaction   | `l0cGtvtlw1lbsyClOm6w` |
| `COGSTACK_API_KEY`             | The unencoded API key for authentiaction with the ID | `I01NJf4Z6yvXyXThh1676g` |
| `COGSTACK_API_KEY_ENCODED`     | The encoded API key for authentiaction with just the API key | `ZZpwMtW3ky6Tw9KEtfavVzTP0JcrC7iLnVf7zXbqAh70A15VKJwHd5YX3J==` |


__Note__: If these fields are left blank then the user will be prompted to enter the details themselves.

If you are unsure about the above information please contact your CogStack system administrator.

## How to build a Search query

A core component of cogstack is Elasticsearch which is a search engine built on top of Apache Lucene.

Lucene has a custom query syntax for querying its indexes (Lucene Query Syntax). This query syntax allows for features such as Keyword matching, Wildcard matching, Regular expression, Proximity matching, Range searches.

Full documentation for this syntax is available as part of Elasticsearch [query string syntax](https://www.elastic.co/guide/en/elasticsearch/reference/8.5/query-dsl-query-string-query.html#query-string-syntax).