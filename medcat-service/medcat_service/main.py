import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from medcat_service.dependencies import get_settings
from medcat_service.routers import admin, health, legacy, process
from medcat_service.types import HealthCheckFailedException

settings = get_settings()

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
app.include_router(legacy.router)


@app.exception_handler(HealthCheckFailedException)
async def healthcheck_failed_exception_handler(request: Request, exc: HealthCheckFailedException):
    return JSONResponse(status_code=503, content=exc.reason.model_dump())


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
