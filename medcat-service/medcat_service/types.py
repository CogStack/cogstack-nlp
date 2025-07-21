from datetime import datetime
from typing import Dict, List, Literal, Optional, Tuple, Union

from medcat.data.entities import Entity
from pydantic import BaseModel


class HealthCheckResponse(BaseModel):
    """
    Using Eclipse MicroProfile health response schema
    """

    name: str
    status: Literal["UP", "DOWN"]


class HealthCheckResponseContainer(BaseModel):
    status: Literal["UP", "DOWN"]
    checks: list[HealthCheckResponse]


class NoProtectedBaseModel(BaseModel, protected_namespaces=()):
    pass


class ModelCardInfo(NoProtectedBaseModel):
    ontologies: Union[str, List[str], None]
    meta_cat_model_names: list[str]
    model_last_modified_on: Optional[datetime]


class ServiceInfo(NoProtectedBaseModel):
    service_app_name: str
    service_language: str
    service_version: str
    service_model: str
    model_card_info: ModelCardInfo


class ProcessAPIInputContent(BaseModel):
    text: str
    footer: Optional[str] = None


class ProcessAPIInput(BaseModel):
    content: ProcessAPIInputContent
    meta_anns_filters: Optional[List[Tuple[str, List[str]]]] = None
    """
    Optional list of (task, values) pairs to filter entities by their meta annotations.
    Example: [('Presence', ['True']), ('Subject', ['Patient', 'Family'])]
    """


class BulkProcessAPIInput(BaseModel):
    content: List[ProcessAPIInputContent]


class ProcessAPIResult(BaseModel):
    text: str
    annotations: List[Dict[str, Entity]]
    """
        # e.g. [{"0": {...}}, {"1": {...}}]
    """
    success: bool
    timestamp: datetime
    elapsed_time: float
    footer: Optional[str] = None
