import logging
from typing import Annotated

from fastapi import Depends, Request

from medcat_service.config import Settings
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor

log = logging.getLogger(__name__)

def get_medcat_processor(request: Request) -> MedCatProcessor:
    proc = getattr(request.app.state, "medcat", None)
    if proc is None:
        raise RuntimeError("MedCatProcessor is not initialised on app.state")
    return proc

def get_settings() -> Settings:
    settings = Settings()
    log.debug("Using settings: %s", settings)
    return settings

processor_singleton: MedCatProcessor | None = None

def set_global_processor(proc: MedCatProcessor):
    global processor_singleton
    processor_singleton = proc

def get_global_processor() -> MedCatProcessor:
    if processor_singleton is None:
        raise RuntimeError("MedCatProcessor has not been initialised yet")
    return processor_singleton

MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]