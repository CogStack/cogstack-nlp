"""
Applies a precomputed isotonic calibration curve to the raw output of a
difficulty estimator (stage 1 or stage 2).

Isotonic regression corrects a systematic *scale* problem, not a *ranking*
problem: it doesn't change which concepts the estimator thinks are harder
than which others, it changes what number gets reported for a given raw
score so that number matches what's empirically observed in real-world
performance. See `fit_calibration_curve.py` for how the curve itself is
produced.

This module deliberately has no dependency on scikit-learn. The fitting
script needs sklearn to *find* the isotonic curve; applying an
already-fitted curve is just monotone linear interpolation between a
handful of (raw_score, calibrated_score) breakpoints, so the runtime
estimator doesn't need to carry that dependency (or the fitted model
object) with it. The curve itself is stored as plain JSON, so it's cheap to
version, diff, and swap out ("bring your own calibration curve").
"""
import json
from pathlib import Path
from typing import Any

import numpy as np

from .common import (
    ConceptDifficulty, DifficultyEstimator, EstimationBaseConfig)


class CalibrationCurve:
    """A fitted, monotone (raw_score -> calibrated_score) mapping.

    Stores the curve as a sorted list of breakpoints and applies it via
    linear interpolation, clamping any input outside the fitted range to
    the nearest observed endpoint (the same "out_of_bounds=clip" behaviour
    you'd want from sklearn's IsotonicRegression).
    """

    def __init__(
        self, raw_scores: list[float], calibrated_scores: list[float],
    ) -> None:
        if len(raw_scores) != len(calibrated_scores):
            raise ValueError(
                "raw_scores and calibrated_scores must be the same length")
        if len(raw_scores) < 2:
            raise ValueError(
                "a calibration curve needs at least two breakpoints")

        order = np.argsort(raw_scores)
        self._x = np.asarray(raw_scores, dtype=float)[order]
        self._y = np.asarray(calibrated_scores, dtype=float)[order]

        if np.any(np.diff(self._y) < 0):
            raise ValueError(
                "calibrated_scores must be non-decreasing in raw_score order; "
                "got a curve that isn't monotonic, which shouldn't be "
                "possible from a correctly fitted isotonic regression"
            )

    @classmethod
    def identity(cls) -> "CalibrationCurve":
        """A no-op curve (calibrated_score == raw_score). Useful as a
        default/fallback so callers can wire calibration through the
        pipeline without necessarily having a fitted curve yet."""
        return cls(raw_scores=[0.0, 1.0], calibrated_scores=[0.0, 1.0])

    def apply(self, raw_score: float) -> float:
        return float(np.interp(raw_score, self._x, self._y))

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_scores": self._x.tolist(),
            "calibrated_scores": self._y.tolist()
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationCurve":
        return cls(
            raw_scores=data["raw_scores"],
            calibrated_scores=data["calibrated_scores"]
        )

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationCurve":
        return cls.from_dict(json.loads(Path(path).read_text()))

    @classmethod
    def default(cls) -> "CalibrationCurve":
        from .default_calibration import JSON
        return cls.from_dict(JSON)


class CalibratedEstimationConfig(EstimationBaseConfig):
    """Config for the calibrated stage.

    Exactly one of `calibration_curve` / `calibration_curve_path` is
    normally set; if neither is, `resolve_curve()` falls back to the
    bundled default curve (see `CalibrationCurve.default()`). An explicit
    `calibration_curve` object takes precedence over `calibration_curve_path`
    if somehow both are given.
    """

    calibration_curve: CalibrationCurve | None = None
    calibration_curve_path: Path | None = None

    def resolve_curve(self) -> CalibrationCurve:
        if self.calibration_curve is not None:
            return self.calibration_curve
        if self.calibration_curve_path is not None:
            return CalibrationCurve.load(self.calibration_curve_path)
        return CalibrationCurve.default()


class CalibratedDifficultyEstimator:
    """Wraps any other `DifficultyEstimator` (stage 1 or stage 2) and
    rescales its `predicted_accuracy` / `min_predicted_accuracy` outputs
    through a fitted `CalibrationCurve`. `intrinsic_ic` is passed through
    untouched -- it's an ontology property, not a performance prediction,
    so there's nothing to calibrate against real-world accuracy.

    Itself implements `DifficultyEstimator` (`.common`), so it can be
    nested (calibrating a calibrated estimator is a no-op in practice, but
    nothing stops it structurally) or swapped in anywhere a plain estimator
    is expected.

    Example:
        stage1 = OntologyDifficultyEstimator(ontology)
        curve = CalibrationCurve.load("stage1_calibration.json")
        calibrated = CalibratedDifficultyEstimator(stage1, curve)
        calibrated.compute_concept_difficulty(concept_id)
    """

    def __init__(
        self,
        wrapped: DifficultyEstimator,
        curve: CalibrationCurve | None = None,
    ) -> None:
        self._wrapped = wrapped
        # Resolved lazily via `or` rather than a `CalibrationCurve.default()`
        # default argument, so the (JSON-parsing) default curve is only ever
        # loaded for instances that actually need it.
        self._curve = curve or CalibrationCurve.default()

    def compute_concept_difficulty(self, concept_id: str) -> ConceptDifficulty:
        raw = self._wrapped.compute_concept_difficulty(concept_id)
        return ConceptDifficulty(
            concept_info=raw["concept_info"],
            predicted_accuracy=self._curve.apply(raw["predicted_accuracy"]),
            min_predicted_accuracy=self._curve.apply(
                raw["min_predicted_accuracy"]),
            intrinsic_ic=raw["intrinsic_ic"],
            features=raw.get("features", {}),
            explanation=raw.get("explanation", {}),
        )
