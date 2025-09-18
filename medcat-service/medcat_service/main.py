import logging
from contextlib import asynccontextmanager

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from medcat_service.config import Settings
from medcat_service.demo.gradio_demo import io
from medcat_service.dependencies import set_global_processor
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor
from medcat_service.routers import admin, health, process
from medcat_service.types import HealthCheckFailedException


@asynccontextmanager
async def lifespan(app: FastAPI):

    log = logging.getLogger(__name__)
    settings = Settings()
    medcat = MedCatProcessor(settings)

    app.state.settings = settings
    app.state.medcat = medcat
    app.state.title = "MedCAT Service",
    app.state.summary = "MedCAT Service",
    app.state.contact = {
        "name": "CogStack Org",
        "url": "https://cogstack.org/",
        "email": "contact@cogstack.org",
    },
    app.state.license_info = {
        "name": "Apache 2.0",
        "identifier": "Apache-2.0",
    },
    app.state.root_path = settings.app_root_path

    set_global_processor(medcat)
    log.debug("MedCAT Service lifespan setup complete")

    yield

app = FastAPI(lifespan=lifespan)

app.include_router(admin.router)
app.include_router(health.router)
app.include_router(process.router)

gr.mount_gradio_app(app, io, path="/demo")


@app.exception_handler(HealthCheckFailedException)
async def healthcheck_failed_exception_handler(request: Request, exc: HealthCheckFailedException):
    return JSONResponse(status_code=503, content=exc.reason.model_dump())

if __name__ == "__main__":
    # Only run this when directly executing `python main.py` for local dev.
    import os

    import uvicorn
    uvicorn.run("medcat_service.main:app", host="0.0.0.0", port=int(os.environ.get("SERVER_PORT", 8000)))
