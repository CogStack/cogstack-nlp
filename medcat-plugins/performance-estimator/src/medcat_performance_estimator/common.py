"""
Shared types for the difficulty-estimation pipeline.

This module exists so that `estimator.py`, `training_aware_estimator.py`
and `calibration.py` can all depend on the *same* result type, config base
class, and estimator protocol without any of them depending on each other.
It should stay a leaf module (no imports from elsewhere in this package).
"""
from enum import Enum
from typing import Protocol, TypedDict, runtime_checkable

from pydantic import BaseModel, ConfigDict


class ActionTier(str, Enum):
    A = "A"  # High performance / Minimal tuning needed
    B = "B"  # Moderate performance / Needs targeted coverage
    C = "C"  # Poor performance / High-priority for annotation & tuning


class TierThresholds(TypedDict):
    a_min: float
    b_min: float


DEFAULT_TIER_THRESHOLDS: TierThresholds = {
    "a_min": 0.80,
    "b_min": 0.50,
}


class TierSummary(TypedDict):
    tier: ActionTier
    count: int
    concept_ids: list[str]
    descriptions: str


class FeatureExplanation(TypedDict):
    value: float | int
    # 0.0 to 1.0 against corpus distribution
    percentile: float
    # "low", "moderate", "high", "critical" (or Q1-Q4)
    impact_level: str
    # "increases_difficulty" | "decreases_difficulty"
    direction: str


class ConceptExplanation(TypedDict):
    # e.g., "training_imbalance", "semantic_overlap", "name_ambiguity"
    primary_penalty_driver: str
    # The name causing the worst accuracy drop
    worst_synonym: str
    # CUI producing the largest competitor mass
    worst_competitor_cui: str | None
    feature_breakdown: dict[str, FeatureExplanation]


class ConceptInfo(TypedDict):
    cui: str
    preferred_name: str
    synonyms: list[str]


class ConceptDifficulty(TypedDict):
    concept_info: ConceptInfo
    predicted_accuracy: float
    min_predicted_accuracy: float
    intrinsic_ic: float
    features: dict[str, float | int]
    explanation: ConceptExplanation


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
