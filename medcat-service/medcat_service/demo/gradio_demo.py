from typing import Dict, List

import gradio as gr
from pydantic import BaseModel

from medcat_service.dependencies import get_medcat_processor
from medcat_service.types import ProcessAPIInputContent
from medcat_service.types_entities import Entity


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

    entities: List[EntityAnnotation]
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


def convert_entity_dict_to_annotations(entity_dict_list: List[Dict[str, Entity]]) -> list[EntityAnnotation]:
    annotations: list[EntityAnnotation] = []
    for entity_dict in entity_dict_list:
        for key, entity in entity_dict.items():
            annotations.append(convert_annotation_to_ner_model(entity, index=int(key)))
    return annotations


def convert_entity_dict_to_display_model(entity_dict_list: List[Dict[str, Entity]]) -> list[EntityAnnotationDisplay]:
    annotations: list[EntityAnnotationDisplay] = []
    for entity_dict in entity_dict_list:
        for key, entity in entity_dict.items():
            annotations.append(convert_annotation_to_display_model(entity))
    return annotations


def convert_display_model_to_list_of_lists(entity_display_model: list[EntityAnnotationDisplay]) -> list[list[str]]:
    return [[str(getattr(entity, field)) for field in entity.model_fields] for entity in entity_display_model]


def process_input(input_text: str):
    processor = get_medcat_processor()
    input = ProcessAPIInputContent(text=input_text)

    result = processor.process_content(input.model_dump())

    entity_ner_format: list[EntityAnnotation] = convert_entity_dict_to_annotations(result.annotations)

    annotations_as_display_format = convert_entity_dict_to_display_model(result.annotations)
    response_datatable_format = convert_display_model_to_list_of_lists(annotations_as_display_format)

    response: EntityResponse = EntityResponse(entities=entity_ner_format, text=input_text)
    return response.model_dump(), response_datatable_format


short_example = "Patient had been diagnosed with acute Kidney Failure the week before"


long_example = """
Description: Intracerebral hemorrhage (very acute clinical changes occurred immediately).
CC: Left hand numbness on presentation; then developed lethargy later that day.

HX: On the day of presentation, this 72 y/o RHM suddenly developed generalized weakness and lightheadedness, and could not rise from a chair. Four hours later he experienced sudden left hand numbness lasting two hours. There were no other associated symptoms except for the generalized weakness and lightheadedness. He denied vertigo.

He had been experiencing falling spells without associated LOC up to several times a month for the past year.

MEDS: procardia SR, Lasix, Ecotrin, KCL, Digoxin, Colace, Coumadin.

PMH: 1)8/92 evaluation for presyncope (Echocardiogram showed: AV fibrosis/calcification, AV stenosis/insufficiency, MV stenosis with annular calcification and regurgitation, moderate TR, Decreased LV systolic function, severe LAE. MRI brain: focal areas of increased T2 signal in the left cerebellum and in the brainstem probably representing microvascular ischemic disease. IVG (MUGA scan)revealed: global hypokinesis of the LV and biventricular dysfunction, RV ejection Fx 45% and LV ejection Fx 39%. He was subsequently placed on coumadin severe valvular heart disease), 2)HTN, 3)Rheumatic fever and heart disease, 4)COPD, 5)ETOH abuse, 6)colonic polyps, 7)CAD, 8)CHF, 9)Appendectomy, 10)Junctional tachycardia.
"""  # noqa: E501

article_footer = """
## Disclaimer
This software is intended solely for the testing purposes and non-commercial use. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.

contact@cogstack.com for more information.

Please note this is a limited version of MedCAT and it is not trained or validated by clinicans.
"""  # noqa: E501

io = gr.Interface(
    fn=process_input,
    inputs="text",
    outputs=[
        gr.HighlightedText(label="Processed Text"),
        gr.Dataframe(label="Annotations", headers=headers, interactive=False),
    ],
    examples=[short_example, long_example],
    preload_example=0,
    title="MedCAT Demo",
    description="Enter some text and click Annotate.",
    flagging_mode="never",
    article=article_footer,
)
