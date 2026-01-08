import medcat_service.utils.telemetry  # noqa , import to initialize telemetry before any other imports

import logging
import logging.config

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from medcat_service.config import Settings
from medcat_service.demo.gradio_demo import mount_gradio_app
from medcat_service.dependencies import get_settings
from medcat_service.log_config import log_config
from medcat_service.routers import admin, health, process
from medcat_service.types import HealthCheckFailedException

settings = get_settings()

logging.config.dictConfig(log_config)

app = FastAPI(
    title="MedCAT Service",
    summary="MedCAT Service",
    contact={
        "name": "CogStack Org",
        "url": "https://cogstack.org/",
        "email": "contact@cogstack.org",
    },
    license_info={
        "name": "Apache 2.0",
        "identifier": "Apache-2.0",
    },
    root_path=settings.app_root_path,
)

app.include_router(admin.router)
app.include_router(health.router)
app.include_router(process.router)

mount_gradio_app(app, path="/demo")


def configure_observability(settings: Settings, app: FastAPI):
    if settings.observability.enable_metrics:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            excluded_handlers=["/api/health.*", "/metrics"],
        ).instrument(app).expose(app, tags=["admin"])


configure_observability(settings, app)


@app.exception_handler(HealthCheckFailedException)
async def healthcheck_failed_exception_handler(request: Request, exc: HealthCheckFailedException):
    return JSONResponse(status_code=503, content=exc.reason.model_dump())


if __name__ == "__main__":
    # Only run this when directly executing `python main.py` for local dev.
    import os

    import uvicorn

    uvicorn.run("medcat_service.main:app", host="0.0.0.0", port=int(os.environ.get("SERVER_PORT", 8000)))
