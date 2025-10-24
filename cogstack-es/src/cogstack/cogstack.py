from collections.abc import Mapping
import getpass
import traceback
from typing import Any, Optional, Iterable, Sequence, Union, Protocol, Type
from typing import Literal
import warnings
# from functools import partial
from importlib.util import find_spec

from IPython.display import display, HTML
import pandas as pd
import tqdm

warnings.filterwarnings("ignore")


def has_module(module_name: str) -> bool:
    """Check whether a module is present.

    This can be useful for figuring out whether Elasticsearch
    or Opensearch could / can be used.

    Args:
        module_name (str): The module path.

    Returns:
        bool: Whether its present.
    """
    return find_spec(module_name) is not None


def has_elasticsearch() -> bool:
    """Checks whether elasticsearch client library is available.

    Returns:
        bool: Whether elasticsearch is available.
    """
    return has_module("elasticsearch")


def has_opensearch() -> bool:
    """Checks whether opensearch client library is available.

    Returns:
        bool: Whether opensearch is available.
    """
    return has_module("opensearchpy")


if not has_elasticsearch() and not has_opensearch():
    ImportError(
        "No Elasticsearch or Opensearch client found. Install with one of:\n"
        "  pip install cogstack-es[ES8]\n"
        "  pip install cogstack-es[ES9]\n"
        "  pip install cogstack-es[OS]"
    )


class IndicesClientProto(Protocol):

    def get_alias(self) -> dict:
        pass

    def get_mapping(self,
                    index: str | Sequence[str],
                    allow_no_indices: bool) -> dict:
        pass


class ClientProvider(Protocol):

    def ping(self) -> bool:
        pass

    @property
    def indices(self) -> IndicesClientProto:
        pass

    def scan(self,
             query: dict,
             include_fields_map: Sequence[str] | None,
             source: bool,
             index: str | Sequence[str],
             size: int,
             request_timeout: int,
             allow_no_indices: bool,
             ) -> Iterable[Any]:
        pass

    def search(self,
               query: dict,
               include_fields_map: Sequence[Mapping[str, Any]] | None,
               index: str | Sequence[str],
               size: int | None,
               allow_no_indices: bool,
               rest_total_hits_as_int: bool,
               source: bool,
               timeout: int | None,
               scroll: str | Literal[-1, 0] | None = None,
               track_scores: bool | None = None,
               track_total_hits: bool | int | None = None,
               sort: dict | list[str] | None = None,
               search_after: list[Union[
                   str, int, float, Any, None]] | None = None,
               ) -> dict:
        pass

    def scroll(self,
               scroll_id: str,
               scroll: str,
               rest_total_hits_as_int: bool,
               ) -> dict:
        pass

    def count_raw(self,
                  index: str | Sequence[str],
                  query: dict,
                  allow_no_indices: bool) -> int:
        pass

    def clear_scroll(self, scroll_id: str | None) -> None:
        pass

    # exception handling for import reasons

    def has_no_indices(self, err: BaseException) -> bool:
        pass

    def is_bad_request(self, err: BaseException) -> bool:
        pass


class CogStack:
    """
    A class for interacting with Elasticsearch or OpenSearch.

    Parameters
    ------------
        elastic : ESClient
            The ElasticSearch or OpenSearch instance.
    """

    ES_TIMEOUT = 300

    def __init__(self, provider: ClientProvider) -> None:
        self.provider = provider

    @classmethod
    def with_basic_auth(
        cls,
        hosts: list[str],
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> "CogStack":
        """
        Create an instance of CogStack using basic authentication.

        Parameters
        ----------
        hosts : list[str]
            A list of Elasticsearch host URLs.
        username : str, optional
            The username to use when connecting to Elasticsearch.
            If not provided, the user will be prompted to enter a username.
        password : str, optional
            The password to use when connecting to Elasticsearch.
            If not provided, the user will be prompted to enter a password.
        Returns
        -------
            CogStack: An instance of the CogStack class.
        """
        elastic = CogStack.get_es_with_basic_auth(hosts, username, password)
        return cls(elastic)

    @classmethod
    def with_api_key_auth(
        cls, hosts: list[str], api_key: Optional[dict] = None
    ) -> "CogStack":
        """
        Create an instance of CogStack using API key authentication.

        Parameters
        ----------
        hosts : list[str]
            A list of Elasticsearch host URLs.
        apiKey : dict, optional

            API key object with string fields either:
            - A: "id" and "api_key"
            - B: "encoded"
            Generated in Elasticsearch or Kibana and provided by your
            CogStack administrator.

            If not provided, the user will be prompted to enter API
            key "encoded" value.

            Example:
                .. code-block:: json
                        {
                            "id": "API_KEY_ID",
                            "api_key": "API_KEY",
                            "encoded": "API_KEY_ENCODED_STRING"
                        }
        Returns
        -------
            CogStack: An instance of the CogStack class.
        """
        provider = CogStack.get_es_with_api_key(hosts, api_key)
        return cls(provider)

    @staticmethod
    def get_es_with_basic_auth(
        hosts: list[str], username: Optional[str] = None,
        password: Optional[str] = None
    ) -> ClientProvider:
        """
        Create an instance of CogStack using basic authentication.
        If the `username` or `password` parameters are not provided,
        the user will be prompted to enter them.

        Parameters
        ----------
        hosts : list[str]
            A list of Elasticsearch or OpenSearch host URLs.
        username : str, optional
            The username to use when connecting to Elasticsearch or OpenSearch.
            If not provided, the user will be prompted to enter a username.
        password : str, optional
            The password to use when connecting to Elasticsearch or OpenSearch.
            If not provided, the user will be prompted to enter a password.

        Returns
        -------
            ClientProvider: A provider of Elasticsearch or OpenSearch.
        """
        if username is None:
            username = input("Username: ")
        if password is None:
            password = getpass.getpass("Password: ")

        return CogStack.__connect(
            hosts,
            basic_auth=(username, password) if username and password else None
        )

    @staticmethod
    def get_es_with_api_key(hosts: list[str],
                            api_key: Optional[dict] = None
                            ) -> ClientProvider:
        """
        Create an instance of CogStack using API key authentication.

        Parameters
        ----------
        hosts : list[str]
            A list of Elasticsearch or OpenSearch host URLs.
        apiKey : Dict, optional

            API key object with string fields either:
            - A: "id" and "api_key"
            - B: "encoded"
            Generated in Elasticsearch, OpenSearch, or Kibana and provided by
            your CogStack administrator.

            If not provided, the user will be prompted to enter API
            key "encoded" value.

            If not provided, the user will be prompted to enter API
            key "encoded" value.

            Example:
             .. code-block:: json
                    {
                        "id": "API_KEY_ID",
                        "api_key": "API_KEY",
                        "encoded": "API_KEY_ENCODED_STRING"
                    }

        Returns
        -------
            ClientProvider: A provider of Elasticsearch or OpenSearch.
        """
        has_encoded_value = False
        api_id_value: str
        api_key_value: str

        if not api_key:
            api_key = {"encoded": input("Encoded API key: ")}
        else:
            if isinstance(api_key, str):
                # If api_key is a string, it is assumed to be
                # the encoded API key
                encoded = api_key
                has_encoded_value = True
            elif isinstance(api_key, dict):
                # If api_key is a dictionary, check for "encoded",
                # "id" and "api_key" keys
                if (
                    "id" in api_key.keys()
                    and api_key["id"] != ""
                    and "api_key" in api_key.keys()
                    and api_key["api_key"] != ""
                ):
                    # If both "id" and "api_key" are present, use them
                    encoded = None
                else:
                    # If "encoded" is present, use it; otherwise prompt for it
                    encoded = (
                        api_key["encoded"]
                        if "encoded" in api_key.keys() and api_key["encoded"]
                        else input("Encoded API key: ")
                    )
                    has_encoded_value = encoded is not None and encoded != ""

            if not has_encoded_value:
                api_id_value = str(
                    api_key["id"]
                    if "id" in api_key.keys() and api_key["id"] != ""
                    else input("API Id: ")
                )
                api_key_value = str(
                    api_key["api_key"]
                    if "api_key" in api_key.keys() and api_key["api_key"] != ""
                    else getpass.getpass("API Key: ")
                )

        return CogStack.__connect(
            hosts,
            api_key=encoded if has_encoded_value else
            (api_id_value, api_key_value)
        )

    @staticmethod
    def __connect(
        hosts: list[str],
        basic_auth: Optional[tuple[str, str]] = None,
        api_key: Optional[Union[str, tuple[str, str]]] = None,
    ) -> ClientProvider:
        """Connect to Elasticsearch or OpenSearch using the credentials.
        Parameters
        ----------
            hosts : list[str]
                A list of Elasticsearch or OpenSearch host URLs.
            basic_auth : Tuple[str, str], optional
                A tuple containing the username and password for
                basic authentication.
            api_key : str or Tuple[str, str], optional
                The API key or a tuple containing the API key ID and API key
                for API key authentication.
        Returns
        -------
            ClientProvider: A provider of Elasticsearch or OpenSearch.
        Raises
        ------
            Exception: If the connection to Elasticsearch or OpenSearch fails.
        """
        ClientWrapper: Type[ClientProvider]
        if has_elasticsearch():
            print("Using Elasticsearch")
            from .es import ClientWrapper
        else:
            print("Using Opensearch")
            from .os import ClientWrapper
        # they currently have the same init args
        provider = ClientWrapper(  # type: ignore
            hosts=hosts,
            api_key=api_key,
            basic_auth=basic_auth,
            verify_certs=False,
            request_timeout=CogStack.ES_TIMEOUT,
        )
        if not provider.ping():
            raise ConnectionError(
                "CogStack connection failed. "
                "Please check your host list and credentials and try again."
            )
        print("CogStack connection established successfully.")
        return provider

    def get_indices_and_aliases(self):
        """
        Retrieve indices and their aliases

        Returns:
        ---------
            A table of indices and aliases to use in subsequent queries
        """
        all_aliases = self.provider.indices.get_alias()
        index_aliases_coll = []
        for index in all_aliases:
            index_aliases = {}
            index_aliases["Index"] = index
            aliases = []
            for alias in all_aliases[index]["aliases"]:
                aliases.append(alias)
            index_aliases["Aliases"] = ", ".join(aliases)
            index_aliases_coll.append(index_aliases)
        with pd.option_context("display.max_colwidth", None):
            return pd.DataFrame(
                index_aliases_coll, columns=["Index", "Aliases"])

    def get_index_fields(self, index: Union[str, Sequence[str]]):
        """
        Retrieve indices and their fields with data type

        Parameters
        ----------
         index: str | Sequence[str]
            Name(s) of indices or aliases for which the list of fields
            is retrieved

        Returns
        ----------
            pandas.DataFrame
                A DataFrame containing index names and their fields with
                data types

        Raises
        ------
            Exception
                If the operation fails for any reason.
        """
        try:
            if len(index) == 0:
                raise ValueError(
                    "Provide at least one index or index alias name")
            all_mappings = self.provider.indices.get_mapping(
                index=index, allow_no_indices=False
            )
            # if self.using_elastic:
            #     all_mappings = all_mappings.body
            columns = ["Field", "Type"]
            if isinstance(index, list):
                columns.insert(0, "Index")
            index_mappings_coll = []
            for index_name in all_mappings:
                for property_name in all_mappings[
                        index_name]["mappings"]["properties"]:
                    index_mapping = {}
                    index_mapping["Index"] = index_name
                    index_mapping["Field"] = property_name
                    index_mapping["Type"] = (
                        all_mappings[index_name]["mappings"]["properties"][
                            property_name
                        ]["type"]
                        if "type"
                        in all_mappings[index_name]["mappings"]["properties"][
                            property_name
                        ].keys()
                        else "?"
                    )
                    index_mappings_coll.append(index_mapping)
        except Exception as err:
            raise Exception(
                "Unexpected issue while getting index fields") from err
        with pd.option_context(
                "display.max_rows", len(index_mappings_coll) + 1):
            return display(pd.DataFrame(
                data=index_mappings_coll, columns=columns))

    def count_search_results(self, index: Union[str, Sequence[str]],
                             query: dict):
        """
        Count number of documents returned by the query

        Parameters
        ----------
             index : str or Sequence[str]
                     The name(s) of the Elasticsearch indices or their
                     aliases to search.

             query : dict
                     A dictionary containing the search query parameters.
                     Query can start with `query` key and contain other
                     query options which will be ignored

                         .. code-block:: json
                             {"query": {"match": {"title": "python"}}}}
                     or only consist of content of `query` block
                         .. code-block:: json
                             {"match": {"title": "python"}}}
        """
        if len(index) == 0:
            raise ValueError("Provide at least one index or index alias name")
        query = self.__extract_query(query=query)
        count = self.provider.count_raw(
            index=index, query=query, allow_no_indices=False)
        return f"Number of documents: {format(count, ',')}"

    def read_data_with_scan(
        self,
        index: Union[str, Sequence[str]],
        query: dict,
        include_fields: Optional[list[str]] = None,
        size: int = 1000,
        request_timeout: int = ES_TIMEOUT,
        show_progress: bool = True,
    ):
        """
        Retrieve documents from an Elasticsearch or OpenSearch index or
        indices using search query and elasticsearch or OpenSearch scan helper
        function. The function converts search results to a Pandas DataFrame
        and does not return current scroll id if the process fails.

        Parameters
        ----------
            index : str or Sequence[str]
                    The name(s) of the Elasticsearch or OpenSearch indices or
                    their aliases to search.
            query : dict
                    A dictionary containing the search query parameters.
                    Query can start with `query` key and contain other
                    query options which will be used in the search

                        .. code-block:: json
                            {"query": {"match": {"title": "python"}}}}
                    or only consist of content of `query` block
                    (preferred method to avoid clashing with other parameters)

                        .. code-block:: json
                            {"match": {"title": "python"}}}

            include_fields : list[str], optional
                    A list of fields to be included in search results
                    and presented as columns in the DataFrame.
                    If not provided, only _index, _id and _score fields will
                    be included. Columns <strong>_index, _id, _score</strong>
                    are present in all search results
            size : int, optional, default = 1000
                    The number of documents to be returned by the query or
                    scroll API during each iteration.
                    <strong>MAX: 10,000</strong>.
            request_timeout : int, optional, default=300
                    The time in seconds to wait for a response
                    from Elasticsearch or OpenSearch before timing out.
            show_progress : bool, optional, default=True
                    Whether to show the progress in console.
        Returns
        ------
        pandas.DataFrame
            A DataFrame containing the retrieved documents.

        Raises
        ------
        Exception
            If the search fails or cancelled by the user.
        """
        pr_bar: Optional[tqdm.tqdm] = None
        all_mapped_results = []
        try:
            if len(index) == 0:
                raise ValueError(
                    "Provide at least one index or index alias name")
            self.__validate_size(size=size)
            if "query" not in query.keys():
                temp_query = query.copy()
                query.clear()
                query["query"] = temp_query
            pr_bar = tqdm.tqdm(
                desc="CogStack retrieved...",
                disable=not show_progress, colour="green"
            )
            scan_results = self.provider.scan(
                include_fields_map=include_fields,
                source=False,
                index=index,
                query=query,
                size=size,
                request_timeout=request_timeout,
                allow_no_indices=False,
            )
            pr_bar.iterable = scan_results
            csr_str = self.count_search_results(index, query)
            total = int(csr_str.rsplit(" ", 1)[-1])
            pr_bar.total = total
            all_mapped_results = self.__map_search_results(hits=pr_bar)
        except BaseException as err:
            if isinstance(err, KeyboardInterrupt):
                if pr_bar is not None:
                    pr_bar.bar_format = "%s{l_bar}%s{bar}%s{r_bar}" % (
                        "\033[0;33m",
                        "\033[0;33m",
                        "\033[0;33m",
                    )
                    pr_bar.set_description(
                        "CogStack read cancelled! Processed", refresh=True
                    )
                print("Request cancelled and current "
                      "search_scroll_id deleted...")
            elif self.provider.has_no_indices(err):
                raise ValueError("Index not found") from err
            elif self.provider.is_bad_request(err):
                raise ValueError("Bad request") from err
            elif isinstance(err, ValueError) and err.args == (
                    'Size must not be greater than 10000',):
                raise err
            else:
                if pr_bar is not None:
                    pr_bar.bar_format = "%s{l_bar}%s{bar}%s{r_bar}" % (
                        "\033[0;31m",
                        "\033[0;31m",
                        "\033[0;31m",
                    )
                    pr_bar.set_description(
                        "CogStack read failed! Processed", refresh=True
                    )
                print(
                    Exception(
                        f"Unexpected {err=},\n {traceback.format_exc()}, "
                        f"{type(err)=}")
                )
        return self.__create_dataframe(all_mapped_results, include_fields)

    def read_data_with_scroll(
        self,
        index: Union[str, Sequence[str]],
        query: dict,
        include_fields: Optional[list[str]] = None,
        size: int = 1000,
        search_scroll_id: Optional[str] = None,
        request_timeout: Optional[int] = ES_TIMEOUT,
        show_progress: Optional[bool] = True,
    ):
        """
        Retrieves documents from an Elasticsearch or OpenSearch index using
        search query and scroll API. Default scroll timeout is set to 10
        minutes. The function converts search results to a Pandas DataFrame.

        Parameters
        ----------
            index : str or Sequence[str]
                    The name(s) of the Elasticsearch or OpenSearch indices or
                    their aliases to search.
            query : dict
                    A dictionary containing the search query parameters.
                    Query can start with `query` key
                    and contain other query options which will be ignored

                        .. code-block:: json
                            {"query": {"match": {"title": "python"}}}}
                    or only consist of content of `query` block
                        .. code-block:: json
                            {"match": {"title": "python"}}}

            include_fields : list[str], optional
                    A list of fields to be included in search results
                    and presented as columns in the DataFrame.
                    If not provided, only _index, _id and _score fields
                    will be included.
                    Columns <strong>_index, _id, _score</strong> are present
                    in all search results
            size : int, optional, default = 1000
                    The number of documents to be returned by the query
                    or scroll API during each iteration.
                    <strong>MAX: 10,000</strong>.
            search_scroll_id : str, optional
                    The value of the last <strong>scroll_id</strong>
                    returned by scroll API and used to continue the search
                    if the current search fails.
                    The value of <strong>scroll_id</strong>
                    times out after <strong>10 minutes</strong>.
                    After which the search will have to be restarted.
                    <strong>Note:</strong> Absence of this parameter indicates
                    a new search.
            request_timeout : int, optional, default=300
                    The time in seconds to wait for a response from
                    Elasticsearch or OpenSearch before timing out.
            show_progress : bool, optional, default=True
                    Whether to show the progress in console.
                    <strong>IMPORTANT:</strong> The progress bar displays
                    the total hits for the query even if continuing the
                    search using `search_scroll_id`.
        Returns
        ------
        pandas.DataFrame
            A DataFrame containing the retrieved documents.

        Raises
        ------
        Exception
            If the search fails or cancelled by the user.
            If the search fails, error message includes the value of
            current `search_scroll_id` which can be used as a function
            parameter to continue the search. <strong>IMPORTANT:</strong>
            If the function fails after `scroll` request, the subsequent
            request will skip results of the failed scroll by the value
            of `size` parameter.
        """
        pr_bar: Optional[tqdm.tqdm] = None
        all_mapped_results = []
        try:
            if len(index) == 0:
                raise ValueError(
                    "Provide at least one index or index alias name")
            self.__validate_size(size=size)
            query = self.__extract_query(query=query)
            result_count = size
            search_result = None
            include_fields_map: Union[Sequence[Mapping[str, Any]], None] = (
                [{"field": field} for field in include_fields]
                if include_fields is not None
                else None
            )

            pr_bar = tqdm.tqdm(
                desc="CogStack retrieved...",
                disable=not show_progress, colour="green")

            if search_scroll_id is None:
                search_result = self.provider.search(
                    query=query,
                    include_fields_map=include_fields_map,
                    index=index,
                    size=size,
                    scroll="10m",
                    allow_no_indices=False,
                    rest_total_hits_as_int=True,
                    source=False,
                    timeout=request_timeout,
                )
                pr_bar.total = search_result["hits"]["total"]
                hits = search_result["hits"]["hits"]
                result_count = len(hits)
                search_scroll_id = search_result["_scroll_id"]
                all_mapped_results.extend(self.__map_search_results(hits=hits))
                pr_bar.update(len(hits))
                if search_result["_shards"]["failed"] > 0:
                    raise LookupError(search_result["_shards"]["failures"])

            while search_scroll_id and result_count == size:
                # Perform ES scroll request
                search_result = self.provider.scroll(
                    scroll_id=search_scroll_id,
                    scroll="10m",
                    rest_total_hits_as_int=True,
                )
                hits = search_result["hits"]["hits"]
                pr_bar.total = (
                    pr_bar.total
                    if pr_bar.total
                    else search_result["hits"]["total"]
                )
                all_mapped_results.extend(self.__map_search_results(hits=hits))
                search_scroll_id = search_result["_scroll_id"]
                result_count = len(hits)
                pr_bar.update(result_count)
            self.provider.clear_scroll(scroll_id=search_scroll_id)
        except BaseException as err:
            if isinstance(err, KeyboardInterrupt):
                if pr_bar is not None:
                    pr_bar.bar_format = "%s{l_bar}%s{bar}%s{r_bar}" % (
                        "\033[0;33m",
                        "\033[0;33m",
                        "\033[0;33m",
                    )
                    pr_bar.set_description(
                        "CogStack read cancelled! Processed", refresh=True
                    )
                self.provider.clear_scroll(scroll_id=search_scroll_id)
                print("Request cancelled and current "
                      "search_scroll_id deleted...")
            elif isinstance(err, ValueError) and err.args == (
                    'Size must not be greater than 10000',):
                raise err
            else:
                if pr_bar is not None:
                    pr_bar.bar_format = "%s{l_bar}%s{bar}%s{r_bar}" % (
                        "\033[0;31m",
                        "\033[0;31m",
                        "\033[0;31m",
                    )
                    pr_bar.set_description(
                        "CogStack read failed! Processed", refresh=True
                    )
                print(
                    Exception(
                        f"Unexpected {err=},\n {traceback.format_exc()}, "
                        f"{type(err)=}"),
                    f"{search_scroll_id=}",
                    sep="\n",
                )

        return self.__create_dataframe(all_mapped_results, include_fields)

    def read_data_with_sorting(
        self,
        index: Union[str, Sequence[str]],
        query: dict,
        include_fields: Optional[list[str]] = None,
        size: Optional[int] = 1000,
        sort: Optional[Union[dict, list[str]]] = None,
        search_after: Optional[list[Union[str, int, float, Any, None]]] = None,
        request_timeout: Optional[int] = ES_TIMEOUT,
        show_progress: Optional[bool] = True,
    ):
        """
        Retrieve documents from an Elasticsearch or OpenSearch index using
        search query and convert them to a Pandas DataFrame.

        Parameters
        ----------
            index : str or Sequence[str]
                    The name(s) of the Elasticsearch  or OpenSearch indices or
                    their aliases to search.
            query : dict
                    A dictionary containing the search query parameters.
                    Query can start with `query` key and contain other
                    query options which will be ignored

                        .. code-block:: json
                            {"query": {"match": {"title": "python"}}}}
                    or only consist of content of `query` block
                        .. code-block:: json
                            {"match": {"title": "python"}}}
            include_fields : list[str], optional
                    A list of fields to be included in search results
                    and presented as columns in the DataFrame.
                    If not provided, only _index, _id and _score
                    fields will be included.
                    Columns <strong>_index, _id, _score</strong> are
                    present in all search results
            size : int, optional, default = 1000
                    The number of documents to be returned by the query
                    or scroll API during each iteration.
                    <strong>MAX: 10,000</strong>.
            sort : dict|list[str], optional, default = {"id": "asc"}
                    Sort field name(s) and order (`asc` or `desc`)
                    in dictionary format or list of field names without order.
                    `{"id":"asc"}` or `id` is added if not provided as a
                    tiebreaker field. Default sorting order is `asc`
                    <strong>Example:</strong>
                    - `dict : {"filed_Name" : "desc", "id" : "asc"}`
                    - `list : ["filed_Name", "id"]`
            search_after : list[str|int|float|Any|None], optional
                    The sort value of the last record in search results.
                    Can be provided if the a search fails and needs to
                    be restarted from the last successful search.
                    Use the value of `search_after_value` from the
                    error message
            request_timeout : int, optional, default = 300
                    The time in seconds to wait for a response from
                    Elasticsearch or OpenSearch before timing out.
            show_progress : bool, optional
                    Whether to show the progress in console. Defaults to true.

        Returns
        ------
            pandas.DataFrame
                A DataFrame containing the retrieved documents.

        Raises
        ------
            Exception
                If the search fails or cancelled by the user.
                Error message includes the value of current
                `search_after_value` which can be used as a function
                parameter to continue the search.
        """
        pr_bar: Optional[tqdm.tqdm] = None
        try:
            if len(index) == 0:
                raise ValueError(
                    "Provide at least one index or index alias name")
            result_count = size
            all_mapped_results = []
            if sort is None:
                sort = {"id": "asc"}
            search_after_value = search_after
            include_fields_map: Union[Sequence[Mapping[str, Any]], None] = (
                [{"field": field} for field in include_fields]
                if include_fields is not None
                else None
            )

            self.__validate_size(size=size)
            query = self.__extract_query(query=query)

            if (isinstance(sort, dict) and "id" not in sort.keys()) or (
                isinstance(sort, list) and "id" not in sort
            ):
                if isinstance(sort, dict):
                    sort["id"] = "asc"
                else:
                    sort.append("id")
            pr_bar = tqdm.tqdm(
                desc="CogStack retrieved...",
                disable=not show_progress, colour="green")

            while result_count == size:
                search_result = self.provider.search(
                    query=query,
                    include_fields_map=include_fields_map,
                    sort=sort,
                    search_after=search_after_value,
                    index=index,
                    size=size,
                    track_scores=True,
                    track_total_hits=True,
                    allow_no_indices=False,
                    rest_total_hits_as_int=True,
                    source=False,
                    timeout=request_timeout
                )
                hits = search_result["hits"]["hits"]
                all_mapped_results.extend(self.__map_search_results(hits=hits))
                result_count = len(hits)
                pr_bar.update(result_count)
                search_after_value = hits[-1]["sort"]
                pr_bar.total = (
                    pr_bar.total
                    if pr_bar.total
                    else search_result["hits"]["total"]
                )
                if search_result["_shards"]["failed"] > 0:
                    raise LookupError(search_result["_shards"]["failures"])
        except BaseException as err:
            if isinstance(err, KeyboardInterrupt):
                if pr_bar is not None:
                    pr_bar.bar_format = "%s{l_bar}%s{bar}%s{r_bar}" % (
                        "\033[0;33m",
                        "\033[0;33m",
                        "\033[0;33m",
                    )
                    pr_bar.set_description(
                        "CogStack read cancelled! Processed", refresh=True
                    )
                print("Request cancelled.")
            elif isinstance(err, ValueError) and err.args == (
                    'Size must not be greater than 10000',):
                raise err
            else:
                if pr_bar is not None:
                    pr_bar.bar_format = "%s{l_bar}%s{bar}%s{r_bar}" % (
                        "\033[0;31m",
                        "\033[0;31m",
                        "\033[0;31m",
                    )
                    pr_bar.set_description(
                        "CogStack read failed! Processed", refresh=True
                    )
                print(f"Unexpected {err=},\n {traceback.format_exc()}, "
                      f"{type(err)=}")
            print(f"The last {search_after_value=}")

        return self.__create_dataframe(all_mapped_results, include_fields)

    def __extract_query(self, query: dict):
        if "query" in query.keys():
            return query["query"]
        return query

    def __validate_size(self, size):
        if size > 10000:
            raise ValueError("Size must not be greater than 10000")

    def __map_search_results(self, hits: Iterable):
        hit: dict
        for hit in hits:
            row = dict()
            row["_index"] = hit["_index"]
            row["_id"] = hit["_id"]
            row["_score"] = hit["_score"]
            if "fields" in hit.keys():
                row.update(
                    {k: ", ".join(map(str, v)) for
                     k, v in dict(hit["fields"]).items()}
                )
            yield row

    def __create_dataframe(self, all_mapped_results, column_headers):
        """
        Create a Pandas DataFrame from the search results.

        Parameters
        ----------
                all_mapped_results : list
                    The list of mapped search results.
                column_headers : list or None
                    The list of column headers to include in the DataFrame.

        Returns
        -------
            pandas.DataFrame
                A DataFrame containing the search results.
        """
        df_headers = ["_index", "_id", "_score"]
        if column_headers and "*" not in column_headers:
            df_headers.extend(column_headers)
            return pd.DataFrame(data=all_mapped_results, columns=df_headers)
        return pd.DataFrame(data=all_mapped_results)


def print_dataframe(df: pd.DataFrame, separator: str = "\\n"):
    """
    Replace <strong>separator</strong> string with HTML
    <strong>&lt;br/&gt;</strong> tag for printing in Notebook

    Parameters:
    -----------
        df : DataFrame
            Input DataFrame
        separator : str
            Separator to be replaced with HTML <strong>&lt;br/&gt;</strong>
    """
    return display(HTML(df.to_html().replace(separator, "<br/>")))


def list_chunker(user_list: list[Any], n: int) -> list[list[Any]]:
    """
    Divide a list into sublists of a specified size.

    Parameters:
    ----------
        user_list : list[Any]
            The list to be divided.
        n : int
            The size of the sublists.

    Returns:
    --------
        list[list[Any]]: A list of sublists containing the elements of
            the input list.
    """
    n = max(1, n)
    return [user_list[i: i + n] for i in range(0, len(user_list), n)]
