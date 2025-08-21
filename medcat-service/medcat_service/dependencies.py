from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from medcat_service.config import Settings
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    print("Using settings " + str(settings))
    return settings


@lru_cache
def get_medcat_processor(settings: Annotated[Settings, Depends(get_settings)]) -> MedCatProcessor:
    print("Using settings for medcat processor " + str(settings))
    return MedCatProcessor(settings)


MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]
