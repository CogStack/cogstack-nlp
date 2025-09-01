import logging
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from medcat_service.config import Settings
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor

log = logging.getLogger(__name__)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    log.debug("Using settings: %s", settings)
    return settings


@lru_cache
def get_medcat_processor(settings: Annotated[Settings, Depends(get_settings)]) -> MedCatProcessor:
    log.debug("Creating new Medcat Processsor using settings: %s", settings)
    return MedCatProcessor(settings)


MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]
