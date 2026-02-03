"""
This module provides conversion utilities between the MedCAT output format
and the exact format expected by Gradio components, specifically aligning
with the output schema of Hugging Face Transformers pipelines (e.g., for
NER highlighting). Use these definitions and helper functions to bridge
MedCAT's annotation results and Gradio's interactive demo expectations.
"""

import logging

from pydantic import BaseModel

from medcat_service.dependencies import get_medcat_processor, get_settings
from medcat_service.types import ProcessAPIInputContent, ProcessErrorsResult, ProcessResult
from medcat_service.types_entities import Entity

logger = logging.getLogger(__name__)


class EntityAnnotation(BaseModel):
    """
    Expected data format for NER in gradio
    """

    entity: str
    score: float
    index: int
    word: str
    start: int
    end: int


headers = ["Pretty Name", "Identifier", "Confidence Score", "Start Index", "End Index", "ID"]


class EntityAnnotationDisplay(BaseModel):
    """
    DIsplay data format for use in a datatable
    """

    pretty_name: str
    identifier: str
    score: float
    start: int
    end: int
    id: int
    # Misisng Meta Anns


class EntityResponse(BaseModel):
    """
    Expected data format of gradio highlightedtext component
    """

    entities: list[EntityAnnotation]
    text: str


def convert_annotation_to_ner_model(entity: Entity, index: int) -> EntityAnnotation:
    return EntityAnnotation(
        entity=entity.get("cui", "UNKNOWN"),
        score=entity.get("acc", 0.0),
        index=index,
        word=entity.get("detected_name", ""),
        start=entity.get("start", -1),
        end=entity.get("end", -1),
    )


def convert_annotation_to_display_model(entity: Entity) -> EntityAnnotationDisplay:
    return EntityAnnotationDisplay(
        pretty_name=entity.get("pretty_name", ""),
        identifier=entity.get("cui", "UNKNOWN"),
        score=entity.get("acc", 0.0),
        start=entity.get("start", -1),
        end=entity.get("end", -1),
        id=entity.get("id", -1),
        # medcat-demo-app/webapp/demo/views.py
        # if key == 'meta_anns':
        # meta_anns=ent.get("meta_anns", {})
        # if meta_anns:
        # for meta_ann in meta_anns.keys():
        # new_ent[meta_ann]=meta_anns[meta_ann]['value']
    )


def convert_entity_dict_to_annotations(entity_dict_list: list[dict[str, Entity]]) -> list[EntityAnnotation]:
    annotations: list[EntityAnnotation] = []
    for entity_dict in entity_dict_list:
        for key, entity in entity_dict.items():
            annotations.append(convert_annotation_to_ner_model(entity, index=int(key)))
    return annotations


def convert_entity_dict_to_display_model(entity_dict_list: list[dict[str, Entity]]) -> list[EntityAnnotationDisplay]:
    logger.debug("Converting entity dict to display model")
    annotations: list[EntityAnnotationDisplay] = []
    for entity_dict in entity_dict_list:
        for key, entity in entity_dict.items():
            annotations.append(convert_annotation_to_display_model(entity))
    return annotations


def convert_display_model_to_list_of_lists(entity_display_model: list[EntityAnnotationDisplay]) -> list[list[str]]:
    return [
        [str(getattr(entity, field)) for field in EntityAnnotationDisplay.model_fields]
        for entity in entity_display_model
    ]


def perform_named_entity_resolution(input_text: str, redact: bool | None = None):
    """
    Performs clinical coding by processing the input text with MedCAT to extract and
    annotate medical concepts (entities).

    Returns:
      1. A dictionary following the NER response model (EntityResponse), containing the original text
         and the list of detected entities.
      2. A datatable-compatible list of lists, where each sublist represents an entity annotation and
         its attributes for display purposes.

    This method is used as the main function for the Gradio MedCAT demo and MCP server,
    enabling users to input free text and receive automatic annotation and coding of clinical entities.

    Args:
        input_text (str): The input text to be processed and annotated for medical entities by MedCAT.

    Returns:
        Tuple:
            - dict: A dictionary following the NER response model (EntityResponse), containing the
              original text and the list of detected entities.
            - list[list[str]]: A datatable-compatible list of lists, where each sublist represents an
              entity annotation and its attributes for display purposes.

    """
    logger.debug("Performing named entity resolution")
    if not input_text or not input_text.strip():
        return None, None, None

    processor = get_medcat_processor(get_settings())
    input = ProcessAPIInputContent(text=input_text)

    process_result = processor.process_content(input.model_dump(), redact=redact)

    if isinstance(process_result, ProcessErrorsResult):
        error_msg = (
            "; ".join(process_result.errors) if process_result.errors else "Unknown error occurred during processing"
        )
        raise ValueError(f"Processing failed: {error_msg}")
    result: ProcessResult = process_result

    entity_ner_format: list[EntityAnnotation] = convert_entity_dict_to_annotations(result.annotations)

    logger.debug("Converting entity dict to display model")
    annotations_as_display_format = convert_entity_dict_to_display_model(result.annotations)
    response_datatable_format = convert_display_model_to_list_of_lists(annotations_as_display_format)

    response: EntityResponse = EntityResponse(entities=entity_ner_format, text=input_text)
    response_tuple = response.model_dump(), response_datatable_format, result.text
    return response_tuple


def medcat_demo_perform_named_entity_resolution(input_text: str):
    """
    Performs named entity resolution for the MedCAT demo.
    """
    result = perform_named_entity_resolution(input_text)
    return result[0], result[1]


def anoncat_demo_perform_deidentification(input_text: str, redact: bool):
    """
    Performs deidentification for the AnonCAT demo.
    """
    result = perform_named_entity_resolution(input_text, redact=redact)
    return result
