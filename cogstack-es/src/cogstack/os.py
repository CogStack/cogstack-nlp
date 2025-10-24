from typing import Sequence, Union, Mapping, Any, Iterable, Literal

from opensearchpy import OpenSearch
import opensearchpy.helpers as es_helpers
from opensearchpy import NotFoundError, RequestError

from .cogstack import IndicesClientProto


class ClientWrapper:

    def __init__(self,
                 hosts: list[str],
                 basic_auth: tuple[str, str] | None,
                 api_key: Union[str, tuple[str, str]] | None,
                 verify_certs: bool,
                 request_timeout: int):
        self.client = OpenSearch(
            hosts=hosts,
            basic_auth=basic_auth,
            api_key=api_key,
            verify_certs=verify_certs,
            request_timeout=request_timeout,
        )

    def ping(self) -> bool:
        return self.client.ping()

    @property
    def indices(self) -> IndicesClientProto:
        return self.client.indices

    def scan(self,
             query: dict,
             include_fields_map: Sequence[str] | None,
             source: bool,
             index: str | Sequence[str],
             size: int,
             request_timeout: int,
             allow_no_indices: bool,
             ) -> Iterable[Any]:
        full_query: dict[str, Any] = {
            "query": query
        } if "query" not in query else query
        if include_fields_map:
            full_query["fields"] = include_fields_map
        return es_helpers.scan(
            self.client,
            index=index,
            query=full_query,
            _source=source,
            size=size,
            request_timeout=request_timeout,
            allow_no_indices=allow_no_indices,
        )

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
        full_query: dict[str, Any] = {
            "query": query,
        }
        if include_fields_map:
            full_query["fields"] = include_fields_map
        if search_after:
            full_query["search_after"] = search_after
        if sort is None:
            sort = {"id": "asc"}
        full_query["sort"] = sort
        return self.client.search(
            index=index,
            body=full_query,
            size=size,
            scroll=scroll,
            allow_no_indices=allow_no_indices,
            rest_total_hits_as_int=rest_total_hits_as_int,
            _source=source,
            timeout=timeout,
            track_scores=track_scores,
            track_total_hits=track_total_hits,
        )

    def scroll(self,
               scroll_id: str,
               scroll: str,
               rest_total_hits_as_int: bool,
               ) -> dict:
        return self.client.scroll(
            scroll_id=scroll_id,
            scroll=scroll,
            rest_total_hits_as_int=rest_total_hits_as_int,
        )

    def count_raw(self,
                  index: str | Sequence[str],
                  query: dict,
                  allow_no_indices: bool) -> int:
        return self.client.count(
            index=index, body={"query": query},
            allow_no_indices=allow_no_indices)["count"]

    def clear_scroll(self, scroll_id: str | Sequence[str] | None) -> None:
        return self.client.clear_scroll(scroll_id=scroll_id)

    # exception handling for import reasons

    def has_no_indices(self, err: BaseException) -> bool:
        if isinstance(err, NotFoundError):
            return True
        return (
            isinstance(err, ValueError) and
            err.args == ('Provide at least one index or index alias name',))

    def is_bad_request(self, err: BaseException) -> bool:
        return isinstance(err, RequestError)
