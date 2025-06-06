from typing import Iterator, Any, Optional, Union
from typing_extensions import TypedDict
from collections import Counter


class MedCATTrainerExportAnnotationRequired(TypedDict):
    start: int
    end: int
    cui: str
    value: str


class MedCATTrainerExportAnnotation(
        MedCATTrainerExportAnnotationRequired, total=False):
    id: Union[str, int]
    validated: Optional[bool]


class MedCATTrainerExportDocument(TypedDict):
    name: str
    id: Any
    last_modified: str
    text: str
    annotations: list[MedCATTrainerExportAnnotation]


class MedCATTrainerExportProject(TypedDict):
    name: str
    id: Any
    cuis: str
    tuis: Optional[str]
    documents: list[MedCATTrainerExportDocument]


MedCATTrainerExportProjectInfo = tuple[str, Any, str, Optional[str]]
"""The project name, project ID, CUIs str, and TUIs str"""


class MedCATTrainerExport(TypedDict):
    projects: list[MedCATTrainerExportProject]


def iter_projects(export: MedCATTrainerExport
                  ) -> Iterator[MedCATTrainerExportProject]:
    """Iterate over all the projects in the trainer export.

    Args:
        export (MedCATTrainerExport): The trainer export.

    Yields:
        Iterator[MedCATTrainerExportProject]: Project iterator.
    """
    yield from export['projects']


def iter_docs(export: MedCATTrainerExport
              ) -> Iterator[tuple[MedCATTrainerExportProjectInfo,
                                  MedCATTrainerExportDocument]]:
    """Iterate over all the docs in a trainer export.

    Args:
        export (MedCATTrainerExport): The trainer export.

    Yields:
        Iterator[tuple[MedCATTrainerExportProjectInfo,
                       MedCATTrainerExportDocument]]:
            The project info and the document.
    """
    for project in iter_projects(export):
        info: MedCATTrainerExportProjectInfo = (
            project['name'], project['id'], project['cuis'],
            project.get('tuis', None)
        )
        for doc in project['documents']:
            yield info, doc


def iter_anns(export: MedCATTrainerExport
              ) -> Iterator[tuple[MedCATTrainerExportProjectInfo,
                                  MedCATTrainerExportDocument,
                                  MedCATTrainerExportAnnotation]]:
    """Iterate over all the annotations in a trainer export.

    Args:
        export (MedCATTrainerExport): The trainer export.

    Yields:
        Iterator[tuple[MedCATTrainerExportProjectInfo,
                       MedCATTrainerExportDocument,
                       MedCATTrainerExportAnnotation]]:
            The project info, the document, and the annotation.
    """
    for proj_info, doc in iter_docs(export):
        for ann in doc['annotations']:
            yield proj_info, doc, ann


def count_all_annotations(export: MedCATTrainerExport) -> int:
    """Count the number of annotations in a trainer export.

    Args:
        export (MedCATTrainerExport): The trainer export.

    Returns:
        int: The total number of annotations.
    """
    return len(list(iter_anns(export)))


def count_all_docs(export: MedCATTrainerExport) -> int:
    """Count the number of documents in a trainer export.

    Args:
        export (MedCATTrainerExport): The trainer export.

    Returns:
        int: The total number of documents.
    """
    return len(list(iter_docs(export)))


def get_nr_of_annotations(doc: MedCATTrainerExportDocument) -> int:
    """Get the number of annotations for a tariner export document.

    Args:
        doc (MedCATTrainerExportDocument): The trainer export document.

    Returns:
        int: The number of annotations within the document.
    """
    return len(doc['annotations'])


def count_anns_per_concept(export: MedCATTrainerExport) -> dict[str, int]:
    counts: dict[str, int] = Counter()
    for _, _, ann in iter_anns(export):
        counts[ann['cui']] += 1
    return dict(counts)
