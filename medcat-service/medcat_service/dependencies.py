import logging
import threading
from collections.abc import Hashable
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


_def_medcat_processors: dict[Hashable, MedCatProcessor] = {}
_def_medcat_processor_lock = threading.Lock()


def get_medcat_processor_singleton(settings: Settings) -> MedCatProcessor:
    with _def_medcat_processor_lock:
        key = hash(settings)
        if key not in _def_medcat_processors:
            log.warning("Creating new MedCatProcessor using settings: %s", settings)
            _def_medcat_processors[key] = MedCatProcessor(settings)
        return _def_medcat_processors[key]


@lru_cache
def get_medcat_processor(settings: Annotated[Settings, Depends(get_settings)]) -> MedCatProcessor:
    log.debug("Creating new medcat processor from cache miss")
    return get_medcat_processor_singleton(settings)


MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]
