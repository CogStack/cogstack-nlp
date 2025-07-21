from datetime import datetime
from typing import List, Literal, Optional, Union

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
