import logging
from typing import Annotated, Optional

from fastapi import Depends, Request

from medcat_service.config import Settings
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor

log = logging.getLogger(__name__)

processor_singleton: Optional[MedCatProcessor] = None
settings_singleton: Optional[Settings] = None


def get_settings(request: Request) -> Settings:
    _settings = request.app.state.settings
    log.debug("Using settings: %s", _settings)
    return _settings


def set_global_settings(settings: Settings) -> None:
    global settings_singleton
    settings_singleton = settings


def get_global_settings() -> Settings:
    if settings_singleton is None:
        raise RuntimeError("Settings have not been initialised yet")
    return settings_singleton


def set_global_processor(proc: MedCatProcessor):
    global processor_singleton
    processor_singleton = proc


def get_medcat_processor(request: Request) -> MedCatProcessor:
    proc = getattr(request.app.state, "medcat", None)
    log.debug("Getting MedCatProcessor from app.state: %s", proc)
    if proc is None:
        raise RuntimeError("MedCatProcessor is not initialised on app.state")
    return proc


def get_global_processor() -> MedCatProcessor:
    if processor_singleton is None:
        raise RuntimeError("MedCatProcessor has not been initialised yet")
    return processor_singleton


SettingsDep = Annotated[Settings, Depends(get_settings)]
MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]
