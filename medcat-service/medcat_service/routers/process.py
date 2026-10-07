import logging
from typing import Annotated, Union

from fastapi import APIRouter, Body, Query
from fastapi.exceptions import RequestValidationError
from opentelemetry import trace
from pydantic import ValidationError

from medcat_service.config import parse_disabled_components
from medcat_service.dependencies import MedCatProcessorDep
from medcat_service.types import BulkProcessAPIInput, BulkProcessAPIResponse, ProcessAPIInput, ProcessAPIResponse

log = logging.getLogger("API")

router = APIRouter(tags=["Process"])

tracer = trace.get_tracer("medcat_service")


@router.post("/api/process")
@tracer.start_as_current_span("/api/process")
async def process(
    payload: Annotated[
        Union[ProcessAPIInput, dict],
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
    disabled_components: Annotated[
        str | None,
        Query(description=(
            "Comma-separated MedCAT component names to skip for this request. "
            "Omit to use APP_DISABLED_COMPONENTS; pass an empty value to run all components."
        )),
    ] = None,
) -> ProcessAPIResponse:
    """
    Returns the annotations extracted from a provided single document
    """
    try:
        if isinstance(payload, ProcessAPIInput):
            content = payload.content.model_dump()
            meta_filters = payload.meta_anns_filters
        elif isinstance(payload, dict):
            try:
                validated = ProcessAPIInput.model_validate(payload)
                content = validated.content.model_dump()
                meta_filters = validated.meta_anns_filters
            except ValidationError as ve:
                log.error("Invalid payload", exc_info=ve)
                raise RequestValidationError(errors=ve.errors()) from ve

        parsed_disabled_components = (
            parse_disabled_components(disabled_components) if disabled_components is not None else None
        )

        process_result = medcat_processor.process_content(
            content,
            meta_anns_filters=meta_filters,
            disabled_components=parsed_disabled_components,
        )

        app_info = medcat_processor.get_app_info()
        return ProcessAPIResponse(result=process_result, medcat_info=app_info)
    except Exception as e:
        log.error("Unable to process data", exc_info=e)
        raise e


@router.post("/api/process_bulk")
async def process_bulk(payload: BulkProcessAPIInput, medcat_processor: MedCatProcessorDep) -> BulkProcessAPIResponse:
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
