from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from medcat_service.config import Settings
from medcat_service.nlp_processor.medcat_processor import MedCatProcessor


@lru_cache
def get_medcat_processor() -> MedCatProcessor:
    return MedCatProcessor()


@lru_cache
def get_settings() -> Settings:
    return Settings()


MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]
