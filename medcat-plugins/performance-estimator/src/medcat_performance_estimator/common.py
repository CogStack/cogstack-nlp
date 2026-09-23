"""
Shared types for the difficulty-estimation pipeline.

This module exists so that `estimator.py`, `training_aware_estimator.py`
and `calibration.py` can all depend on the *same* result type, config base
class, and estimator protocol without any of them depending on each other.
It should stay a leaf module (no imports from elsewhere in this package).
"""
from typing import Protocol, TypedDict, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ConceptDifficulty(TypedDict):
    predicted_accuracy: float
    min_predicted_accuracy: float
    intrinsic_ic: float


class EstimationBaseConfig(BaseModel):
    """Common base for every per-stage config (`EstimationConfig`,
    `TrainingAwareConfig`, `CalibratedEstimationConfig`, ...).

    Existing only so that all of them can be held in a single
    `dict[EstimationType, EstimationBaseConfig]` -- e.g. `per_stage_configs`
    in `estimation.get_estimate` -- and looked up/validated generically,
    regardless of which concrete stage they configure.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)


@runtime_checkable
class DifficultyEstimator(Protocol):
    """Common protocol every stage's estimator implements: given a CUI,
    return its difficulty estimate.

    This is what `estimation.get_estimate` dispatches to, and it's also
    what `CalibratedDifficultyEstimator` wraps -- it doesn't need to know
    which concrete estimator/stage produced the raw score, only that it
    exposes this one method.
    """

    def compute_concept_difficulty(self, concept_id: str) -> ConceptDifficulty:
        pass
