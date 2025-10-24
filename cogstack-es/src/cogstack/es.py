from typing import Sequence, Mapping, Any, Iterable, Union, Literal, cast

from elasticsearch import Elasticsearch
import elasticsearch.helpers as es_helpers
from elasticsearch import NotFoundError, BadRequestError
from elasticsearch.client import IndicesClient

from .cogstack import IndicesClientProto


class ESIndices:

    def __init__(self, es_indices: IndicesClient):
        self.es_indices = es_indices

    def get_alias(self) -> dict:
        return self.es_indices.get_alias().body

    def get_mapping(self,
                    index: str | Sequence[str],
                    allow_no_indices: bool) -> dict:
        return self.es_indices.get_mapping(
            index=index,
            allow_no_indices=allow_no_indices).body


class ClientWrapper:

    def __init__(self,
                 hosts: list[str],
                 basic_auth: tuple[str, str] | None,
                 api_key: Union[str, tuple[str, str]] | None,
                 verify_certs: bool,
                 request_timeout: int):
        self.elastic = Elasticsearch(
            hosts=hosts,
            basic_auth=basic_auth,
            api_key=api_key,
            verify_certs=verify_certs,
            request_timeout=request_timeout,
        )

    def ping(self) -> bool:
        return self.elastic.ping()

    @property
    def indices(self) -> IndicesClientProto:
        return ESIndices(self.elastic.indices)

    def scan(self,
             query: dict,
             include_fields_map: Sequence[str] | None,
             source: bool,
             index: str | Sequence[str],
             size: int,
             request_timeout: int,
             allow_no_indices: bool,
             ) -> Iterable[Any]:
        return es_helpers.scan(
            self.elastic,
            index=index,
            query=query,
            fields=include_fields_map,
            source=source,
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
        return cast(dict, self.elastic.search(
            index=index,
            query=query,
            fields=include_fields_map,
            sort=sort,
            search_after=search_after,
            size=size,
            scroll=scroll,
            allow_no_indices=allow_no_indices,
            rest_total_hits_as_int=rest_total_hits_as_int,
            source=source,
            timeout=f"{timeout}s",
            track_scores=track_scores,
            track_total_hits=track_total_hits,
        ))

    def scroll(self,
               scroll_id: str,
               scroll: str,
               rest_total_hits_as_int: bool,
               ) -> dict:
        return cast(dict, self.elastic.scroll(
            scroll_id=scroll_id,
            scroll=scroll,
            rest_total_hits_as_int=rest_total_hits_as_int,
        ))

    def count_raw(self,
                  index: str | Sequence[str],
                  query: dict,
                  allow_no_indices: bool) -> int:
        return self.elastic.count(
            index=index, query=query,
            allow_no_indices=allow_no_indices)["count"]

    def clear_scroll(self, scroll_id: str | Sequence[str] | None) -> None:
        self.elastic.clear_scroll(scroll_id=scroll_id)

    # exception handling for import reasons

    def has_no_indices(self, err: BaseException) -> bool:
        if isinstance(err, NotFoundError):
            return True
        return (
            isinstance(err, ValueError) and
            err.args == ('Provide at least one index or index alias name',))

    def is_bad_request(self, err: BaseException) -> bool:
        return isinstance(err, BadRequestError)
