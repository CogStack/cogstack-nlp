from fastapi import APIRouter

from medcat_service.dependencies import MedCatProcessorDep
from medcat_service.types import HealthCheckFailedException, HealthCheckResponseContainer

router = APIRouter(tags=["health"])


@router.get("/api/health/live")
def liveness() -> HealthCheckResponseContainer:
    """
    Liveness API checks if the application is running.
    """
    response = HealthCheckResponseContainer(status="UP", checks=[])
    if response.status == "DOWN":
        raise HealthCheckFailedException(reason=response)
    else:
        return response


@router.get("/api/health/ready")
def readiness(medcat_processor: MedCatProcessorDep) -> HealthCheckResponseContainer:
    """
    Readiness API checks if the application is ready to start accepting traffic
    """
    medcat_is_ready = medcat_processor.is_ready()

    if medcat_is_ready.status == "UP":
        return HealthCheckResponseContainer(status="UP", checks=[medcat_is_ready])
    else:
        response = HealthCheckResponseContainer(status="DOWN", checks=[medcat_is_ready])
        raise HealthCheckFailedException(reason=response)
