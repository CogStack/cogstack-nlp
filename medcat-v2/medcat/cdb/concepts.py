from typing import Optional, TypedDict
from dataclasses import dataclass, field

import numpy as np


class CUIInfo(TypedDict):
    cui: str  # NOTE: we _could_ get away without to save on memory
    preferred_name: str
    names: set[str]
    subnames: set[str]
    type_ids: set[str]
    # optional parts start here
    description: Optional[str]
    original_names: Optional[set[str]]
    tags: Optional[list[str]]
    group: Optional[str]
    in_other_ontology: Optional[set[str]]
    # stuff related to training starts here
    # TODO: separate supervised and unsupervised
    count_train: int
    context_vectors: Optional[dict[str, np.ndarray]]
    average_confidence: float


def get_new_cui_info(cui: str, preferred_name: str,
                     names: set[str] = set(),
                     subnames: set[str] = set(),
                     type_ids: set[str] = set(),
                     description: Optional[str] = None,
                     original_names: Optional[set[str]] = None,
                     tags: Optional[list[str]] = None,
                     group: Optional[str] = None,
                     in_other_ontology: Optional[set[str]] = None,
                     count_train: int = 0,
                     context_vectors: Optional[dict[str, np.ndarray]] = None,
                     average_confidence: float = 0.0) -> CUIInfo:
    return {
        'cui': cui,
        'preferred_name': preferred_name,
        'names': names or names.copy(),
        'subnames': subnames or subnames.copy(),
        'type_ids': type_ids or type_ids.copy(),
        'description': description,
        'original_names': original_names,
        'tags': tags,
        'group': group,
        'in_other_ontology': in_other_ontology,
        'count_train': count_train,
        'context_vectors': context_vectors,
        'average_confidence': average_confidence
    }


def reset_cui_training(cui_info: CUIInfo) -> None:
    cui_info['context_vectors'] = None
    cui_info['count_train'] = 0
    cui_info['average_confidence'] = 0


class NameInfo(TypedDict):
    name: str  # NOTE: we _could_ get away without to save on memory
    per_cui_status: dict[str, str]
    is_upper: bool
    # stuff related to training starts here
    count_train: int


def get_new_name_info(name: str,
                      per_cui_status: dict[str, str] = {},
                      is_upper: bool = False,
                      count_train: int = 0) -> NameInfo:
    return {
        'name': name,
        'per_cui_status': per_cui_status or per_cui_status.copy(),
        'is_upper': is_upper,
        'count_train': count_train
    }


@dataclass
class TypeInfo:
    """Represents all the info regarding a type ID."""
    type_id: str  # NOTE: we _could_ get away without to save on memory
    name: str
    cuis: set[str] = field(default_factory=set)
