"""
Fits an isotonic calibration curve mapping the estimator's raw
predicted_accuracy to empirically observed real-world accuracy, and saves
it as a CalibrationCurve JSON file for use with CalibratedDifficultyEstimator.

This is an offline/analysis-time script (needs scikit-learn + pandas). It
has no relationship to the runtime `calibration.py` module's dependencies --
that module only needs to *apply* an already-fitted curve, which is why it
doesn't need sklearn at all.

Input: a CSV with (at least) two columns:
    raw_estimate       -- predicted_accuracy from compute_concept_*_difficulty
    observed_accuracy  -- measured real-world accuracy for that concept,
                           e.g. recall from the SNOMED entity linking
                           challenge dataset

Usage (run as a module, like the rest of this package):
    python -m medcat_performance_estimator.fit_calibration_curve \
        --input eval_results.csv \
        --output stage1_calibration.json \
        --holdout-fraction 0.2

IMPORTANT: fit and evaluate on separate splits. With the kind of noisy,
per-concept measurements this is built from, a curve fit and scored on the
same data will look better than it actually is -- it will have partly
memorized noise, especially in score ranges where few concepts sit. This
script always reports holdout metrics; treat the fit-set fit itself as
internal-only, not as a number to report externally.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import train_test_split


from .stage3_calibration import CalibrationCurve


def _mean_abs_calibration_error(
    raw: np.ndarray, observed: np.ndarray,
    bin_edges: np.ndarray = np.linspace(0, 1, 11)
) -> float:
    """Mean absolute difference between average raw score and average
    observed accuracy within each bin of raw scores -- a simple, readable
    reliability metric (lower is better calibrated). This is the same idea
    as a reliability diagram, collapsed to one number."""
    bin_idx = np.digitize(raw, bin_edges[1:-1])
    errors = []
    for b in np.unique(bin_idx):
        mask = bin_idx == b
        if mask.sum() == 0:
            continue
        errors.append(abs(raw[mask].mean() - observed[mask].mean()))
    return float(np.mean(errors)) if errors else float("nan")


def fit_and_evaluate(
    raw_fit: np.ndarray,
    observed_fit: np.ndarray,
    raw_holdout: np.ndarray,
    observed_holdout: np.ndarray,
    curve_resolution: int = 200,
) -> tuple[CalibrationCurve, dict]:
    ir = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    ir.fit(raw_fit, observed_fit)

    # Evaluate the fitted isotonic function on a fine, evenly-spaced grid
    # across the observed raw-score range, then store that grid as our
    # portable, sklearn-free CalibrationCurve. Predicting on a grid (rather
    # than reaching into sklearn's internal step-function attributes) keeps
    # this robust across sklearn versions.
    lo, hi = float(raw_fit.min()), float(raw_fit.max())
    grid = np.linspace(lo, hi, curve_resolution)
    calibrated_grid = ir.predict(grid)
    curve = CalibrationCurve(
        raw_scores=grid.tolist(), calibrated_scores=calibrated_grid.tolist())

    calibrated_holdout = np.array([curve.apply(x) for x in raw_holdout])

    diagnostics = {
        "n_fit": len(raw_fit),
        "n_holdout": len(raw_holdout),
        "holdout_corr_raw_vs_observed": float(np.corrcoef(
            raw_holdout, observed_holdout)[0, 1]),
        "holdout_mae_before_calibration": float(np.mean(np.abs(
            raw_holdout - observed_holdout))),
        "holdout_mae_after_calibration": float(np.mean(np.abs(
            calibrated_holdout - observed_holdout))),
        "holdout_reliability_error_before": _mean_abs_calibration_error(
            raw_holdout, observed_holdout),
        "holdout_reliability_error_after": _mean_abs_calibration_error(
            calibrated_holdout, observed_holdout),
    }
    return curve, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, type=Path,
        help="CSV with raw_estimate, observed_accuracy columns")
    parser.add_argument("--output", required=True, type=Path,
                        help="Where to save the fitted CalibrationCurve JSON")
    parser.add_argument("--raw-column", default="raw_estimate")
    parser.add_argument("--observed-column", default="observed_accuracy")
    parser.add_argument("--holdout-fraction", type=float, default=0.2,
                        help="Fraction of concepts held out for evaluating "
                        "the fitted curve")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    missing = {args.raw_column, args.observed_column} - set(df.columns)
    if missing:
        sys.exit(f"Input is missing required column(s): {sorted(missing)}")

    raw = df[args.raw_column].to_numpy(dtype=float)
    observed = df[args.observed_column].to_numpy(dtype=float)

    raw_fit, raw_holdout, observed_fit, observed_holdout = train_test_split(
        raw, observed, test_size=args.holdout_fraction, random_state=args.seed,
    )

    curve, diagnostics = fit_and_evaluate(
        raw_fit, observed_fit, raw_holdout, observed_holdout)
    curve.save(args.output)

    print(f"Saved calibration curve to {args.output}")
    print(
        "Holdout diagnostics (this is the number that matters -- "
        "never the fit-set score):")
    for key, value in diagnostics.items():
        print(
            f"  {key}: {value:.4f}"
            if isinstance(value, float) else
            f"  {key}: {value}"
        )

    if diagnostics[
        "holdout_mae_after_calibration"] >= diagnostics[
            "holdout_mae_before_calibration"]:
        print(
            "\nWARNING: calibration did not reduce holdout MAE. This usually "
            "means the raw estimate and observed accuracy aren't correlated "
            "enough for isotonic regression to have anything useful to fit -- "
            "check the holdout correlation above before trusting this curve."
        )


if __name__ == "__main__":
    main()
