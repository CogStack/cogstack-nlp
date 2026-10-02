from typing import TypedDict

from medcat.tokenizing.tokens import MutableEntity


class GoldAnnotation(TypedDict):
    """Validated gold annotation payload after CUI filtering."""

    start: int
    end: int
    cuis: list[str]
    cui: str
    text: str
    raw: object
    document_id: int
    document_name: str
    # context is 60 chars before + after the entity
    context: str


class PredictedAnnotation(TypedDict):
    """Predicted entity payload used for scoring and metrics."""

    start: int
    end: int
    cui: str
    text: str
    confidence: float
    raw: MutableEntity
    no_tokens: int
    document_id: int
    document_name: str
    # context is 60 chars before + after the entity
    context: str
