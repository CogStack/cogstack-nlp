from typing import TypedDict, Any
from contextlib import contextmanager, nullcontext

from pydantic import BaseModel
from spacy.tokens import Span

from medcat.cdb import CDB
from medcat.config import LinkingFilters

from medcat.stats.mctexport import MedCATTrainerExportProject


class CUIInfo(TypedDict):
    preferred_name: str | None


class _FakeDict:

    def __init__(self, cdb: CDB):
        self.cdb = cdb

    def get(self, cui: str, def_val: Any | None = None) -> CUIInfo | None:
        if cui not in self.cdb.cui2preferred_name:
            return def_val
        return {"preferred_name": self.cdb.cui2preferred_name[cui]}

    def __getitem__(self, cui: str) -> CUIInfo:
        if cui not in self.cdb.cui2preferred_name:
            raise KeyError(cui)
        return {"preferred_name": self.cdb.cui2preferred_name[cui]}

    def __contains__(self, cui: str) -> bool:
        return cui in self.cdb.cui2preferred_name


def from_cdb(cdb: CDB) -> dict[str, 'CUIInfo']:
    return _FakeDict(cdb)


class BaseMutableEntity(BaseModel):
    start_char_index: int
    end_char_index: int
    text: str


class MutableEntity(BaseModel):
    base: BaseMutableEntity
    cui: str
    context_similarity: float

    @classmethod
    def from_spacy(cls, span: Span) -> 'MutableEntity':
        base = BaseMutableEntity(start_char_index=span.start_char,
                                 end_char_index=span.end_char,
                                 text=span.text)
        return cls(base=base,
                   cui=span._.cui,
                   context_similarity=span._.context_similarity)

    @classmethod
    def from_spacy_list(cls, spans: list[Span]) -> list['MutableEntity']:
        return [cls.from_spacy(span) for span in spans]


@contextmanager
def temp_changed_config(config: BaseModel, target: str, value: Any):
    """Context manager to change the config temporarily (within).

    Args:
        config (BaseModel): The config in question.
        target (str): The attribute name to change.
        value (Any): The temporary value to use.

    Raises:
        IllegalConfigPathException: If no previous value is available.
    """
    try:
        prev_value = getattr(config, target)
    except AttributeError as e:
        raise IllegalConfigPathException(target) from e
    setattr(config, target, value)
    try:
        yield
    finally:
        setattr(config, target, prev_value)


class IllegalConfigPathException(ValueError):

    def __init__(self, target_path: str):
        super().__init__(
            f"Config has no target path: {target_path}")


def project_filters(filters: LinkingFilters,
                    project: MedCATTrainerExportProject,
                    extra_cui_filter: set[str] | None,
                    use_project_filters: bool):
    """Context manager with per project filters based on a trainer export.

    Args:
        filters (LinkingFilters): The current config.
        project (MedCATTrainerExportProject): The trainer export.
        extra_cui_filter (Optional[set[str]]): Extra cui filters.
        use_project_filters (bool): Whether to use project filters.
    """
    if extra_cui_filter is not None and not use_project_filters:
        return temp_changed_config(filters, 'cuis', extra_cui_filter)
    if use_project_filters:
        cuis = project.get('cuis', None)
        if cuis is None or not cuis:
            return nullcontext()
        return temp_changed_config(filters, 'cuis', set(cuis.split(",")))
    return temp_changed_config(filters, 'cuis', set())
