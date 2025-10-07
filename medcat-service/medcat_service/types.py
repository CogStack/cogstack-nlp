from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field
from typing_extensions import Any, Literal

from medcat_service.types_entities import Entity


class HealthCheckResponse(BaseModel):
    """
    Using Eclipse MicroProfile health response schema
    """

    name: str
    status: Literal["UP", "DOWN"]


class HealthCheckResponseContainer(BaseModel):
    status: Literal["UP", "DOWN"]
    checks: list[HealthCheckResponse]


class HealthCheckFailedException(Exception):
    def __init__(self, reason: HealthCheckResponseContainer):
        self.reason = reason


class NoProtectedBaseModel(BaseModel, protected_namespaces=()):
    pass


class ModelCardInfo(NoProtectedBaseModel):
    ontologies: Union[str, List[str], None]
    meta_cat_model_names: list[str]
    rel_cat_model_names: list[str]
    model_last_modified_on: Optional[datetime]


class ServiceInfo(NoProtectedBaseModel):
    service_app_name: str
    service_language: str
    service_version: str
    service_model: str
    model_card_info: ModelCardInfo


class ProcessAPIInputContent(BaseModel):
    text: str = Field(examples=["Patient had been diagnosed with acute Kidney Failure the week before"])
    footer: Optional[Union[str, Dict[str, Any]]] = None

    class Config:
        extra = "forbid"


class ProcessAPIInput(BaseModel):
    content: ProcessAPIInputContent
    meta_anns_filters: Optional[List[Tuple[str, List[str]]]] = Field(default=None,
                                                                     examples=[
                                                                         [("Presence", ["True"]),
                                                                          ("Subject", ["Patient", "Family"])]
                                                                     ])
    """
    meta_anns_filters (List[Tuple[str, List[str]]]): List of task and filter values pairs to filter
        entities by. Example: meta_anns_filters = [("Presence", ["True"]),
        ("Subject", ["Patient", "Family"])] would filter entities where each
        entity.meta_anns['Presence']['value'] is 'True' and
        entity.meta_anns['Subject']['value'] is 'Patient' or 'Family'
    """


class BulkProcessAPIInput(BaseModel):
    content: List[ProcessAPIInputContent]


class ProcessResult(BaseModel):
    text: str
    # TODO: Any set as annotations has many different types
    annotations: Union[List[Dict[str, Entity]], Any]
    """
        # e.g. [{"0": {...}}, {"1": {...}}]
    """
    success: bool
    timestamp: str
    elapsed_time: float
    footer: Optional[Union[str, Dict[str, Any]]] = None


class ProcessErrorsResult(BaseModel):
    success: bool
    timestamp: str
    errors: List[str]


class ProcessAPIResponse(BaseModel):
    medcat_info: ServiceInfo
    result: Union[ProcessResult, ProcessErrorsResult]


class BulkProcessAPIResponse(BaseModel):
    medcat_info: ServiceInfo
    result: List[ProcessResult]
