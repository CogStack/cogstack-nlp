from fastapi import APIRouter

from medcat_service.dependencies import MedCatProcessorDep
from medcat_service.types import ServiceInfo

router = APIRouter(tags=["admin"])


@router.get("/api/info")
def info(medcat_processor: MedCatProcessorDep) -> ServiceInfo:
    """
    Returns basic information about the NLP Service
    """
    return medcat_processor.get_app_info()
