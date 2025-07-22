from typing import Annotated

from fastapi import Depends

from medcat_service.nlp_processor.medcat_processor import MedCatProcessor

# Singleton instance
_medcat_processor = MedCatProcessor()


# Dependency function
def get_medcat_processor() -> MedCatProcessor:
    return _medcat_processor


MedCatProcessorDep = Annotated[MedCatProcessor, Depends(get_medcat_processor)]
