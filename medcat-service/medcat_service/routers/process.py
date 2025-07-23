import logging
from typing import Annotated

from fastapi import APIRouter, Body

from medcat_service.dependencies import MedCatProcessorDep
from medcat_service.types import BulkProcessAPIInput, BulkProcessAPIResponse, ProcessAPIInput, ProcessAPIResponse

log = logging.getLogger("API")

router = APIRouter(tags=["Process"])


@router.post("/api/process")
def process(
    payload: Annotated[
        ProcessAPIInput,
        Body(
            openapi_examples={
                "normal": {
                    "summary": "A normal example",
                    "description": "Normal use puts a free text note in the text field",
                    "value": {
                        "content": {
                            "text": "Patient had been diagnosed with acute Kidney Failure the week before",
                        }
                    },
                },
                "complete": {
                    "summary": "A complete example",
                    "description": "Complete use adds a footer and meta annotations filter.",
                    "value": {
                        "content": {
                            "text": "Patient had been diagnosed with acute Kidney Failure the week before",
                            "footer": "string",
                        },
                        "meta_anns_filters": [("Presence", ["True"]), ("Subject", ["Patient", "Family"])],
                    },
                },
            }
        ),
    ],
    medcat_processor: MedCatProcessorDep,
) -> ProcessAPIResponse:
    """
    Returns the annotations extracted from a provided single document
    """
    try:
        process_result = medcat_processor.process_content(
            payload.content.model_dump(), meta_anns_filters=payload.meta_anns_filters
        )
        app_info = medcat_processor.get_app_info()
        return ProcessAPIResponse(result=process_result, medcat_info=app_info)
    except Exception as e:
        log.error("Unable to process data", exc_info=e)
        raise e


@router.post("/api/process_bulk")
def process_bulk(payload: BulkProcessAPIInput, medcat_processor: MedCatProcessorDep) -> BulkProcessAPIResponse:
    """
    Returns the annotations extracted from the provided set of documents
    """
    try:
        result = list(medcat_processor.process_content_bulk(payload.model_dump()["content"]))
        app_info = medcat_processor.get_app_info()
        return BulkProcessAPIResponse(result=result, medcat_info=app_info)
    except Exception as e:
        log.error("Unable to process data", exc_info=e)
        raise e
