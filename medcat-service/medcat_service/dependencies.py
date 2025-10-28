import logging
import threading
from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends

from medcat_service.config import Settings
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor

log = logging.getLogger(__name__)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    log.info(f"Starting service using settings: '{settings}'")
    return settings


_def_medcat_processor: Optional[MedCatProcessor] = None
_def_medcat_processor_lock = threading.Lock()


def get_medcat_processor_singleton(settings: Settings) -> MedCatProcessor:
    with _def_medcat_processor_lock:
        global _def_medcat_processor
        if _def_medcat_processor is None:
            log.info("Creating new Medcat Processsor using settings: %s", settings)
            _def_medcat_processor = MedCatProcessor(settings)
        return _def_medcat_processor


@lru_cache
def get_medcat_processor(settings: Annotated[Settings, Depends(get_settings)]) -> MedCatProcessor:
    log.debug("Creating new medcat processor from cache miss")
    return get_medcat_processor_singleton(settings)


MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]
