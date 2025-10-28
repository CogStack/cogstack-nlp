import logging
import threading
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from medcat_service.config import Settings
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor

log = logging.getLogger(__name__)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    log.info(f"Starting service using settings: '{settings}'")
    return settings


_def_medcat_processor: tuple[Settings, MedCatProcessor] | None = None
_def_medcat_processor_lock = threading.Lock()


def get_medcat_processor_singleton(settings: Settings) -> MedCatProcessor:
    with _def_medcat_processor_lock:
        global _def_medcat_processor
        if _def_medcat_processor is None or _def_medcat_processor[0] != settings:
            log.info("Creating new MedCatProcessor using settings: %s", settings)
            _def_medcat_processor = (settings, MedCatProcessor(settings))
        return _def_medcat_processor[1]


@lru_cache
def get_medcat_processor(settings: Annotated[Settings, Depends(get_settings)]) -> MedCatProcessor:
    log.debug("Creating new medcat processor due to cache miss")
    return get_medcat_processor_singleton(settings)


MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]
