from typing_extensions import TypedDict

# Duplicates from medcat/data/entities.py


class MetaAnnotation(TypedDict):
    """
    From medcat/data/entities.py
    To fix "pydantic.errors.PydanticUserError: Please use `typing_extensions.TypedDict`
      instead of `typing.TypedDict` on Python < 3.12."
    """

    value: str
    confidence: float
    name: str


class Entity(TypedDict, total=False):
    """
    From medcat/data/entities.py
    To fix "pydantic.errors.PydanticUserError: Please use `typing_extensions.TypedDict`
      instead of `typing.TypedDict` on Python < 3.12."
    """

    pretty_name: str
    cui: str
    type_ids: list[str]
    # types: list[str]# TODO: add back
    source_value: str
    detected_name: str
    acc: float
    context_similarity: float
    start: int
    end: int
    # icd10: list[str]# TODO: add back
    # ontologies: list[str]# TODO: add back
    # snomed: list[str]# TODO: add back
    id: int
    meta_anns: dict[str, MetaAnnotation]
    # optionals:
    context_left: list[str]
    context_center: list[str]
    context_right: list[str]
