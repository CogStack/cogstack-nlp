"""
CLI entry point for computing concept difficulty estimates using MedCAT model packs.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

from medcat.cat import CAT

from .calibration import CalibratedEstimationConfig
from .estimation import EstimationType, PerStageConfigs, build_estimator


def parse_cuis(cui_arg: str | None, cui_file: Path | None) -> list[str]:
    """Resolves CUIs from either comma-separated command line string or a JSON file."""
    cuis: list[str] = []
    if cui_arg:
        cuis.extend([cui.strip() for cui in cui_arg.split(",") if cui.strip()])

    if cui_file:
        if not cui_file.exists():
            raise FileNotFoundError(f"CUI JSON file not found: {cui_file}")
        with open(cui_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON list in {cui_file}, got {type(data).__name__}")
        cuis.extend([str(item).strip() for item in data if str(item).strip()])

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for cui in cuis:
        if cui not in seen:
            seen.add(cui)
            deduped.append(cui)
    return deduped


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estimate concept difficulty scores using MedCAT models.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # 1. Model pack path
    parser.add_argument(
        "--model-pack",
        "-m",
        required=True,
        type=Path,
        help="Path to MedCAT model pack (.zip or folder).",
    )

    # 2. CUIs input (comma-separated OR json-saved-list)
    cui_group = parser.add_mutually_exclusive_group(required=True)
    cui_group.add_argument(
        "--cuis",
        "-c",
        type=str,
        help="Comma-separated list of CUIs (e.g. '195967001,22298006').",
    )
    cui_group.add_argument(
        "--cui-file",
        "-f",
        type=Path,
        help="Path to a JSON file containing a list of CUIs.",
    )

    # 3. Stage of estimation
    parser.add_argument(
        "--stage",
        "-s",
        choices=[t.value for t in EstimationType],
        default=EstimationType.CALIBRATED.value,
        help="Estimation pipeline stage.",
    )

    # 4. JSON calibration curve
    parser.add_argument(
        "--calibration-curve",
        type=Path,
        default=None,
        help="Path to custom CalibrationCurve JSON file. Defaults to bundled curve if omitted. "
             "Only used when --stage=calibrated.",
    )

    # 5. Output JSON path
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional path to write JSON results to. If omitted, results are printed to stdout.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Load CUIs
    try:
        cuis = parse_cuis(args.cuis, args.cui_file)
    except Exception as e:
        sys.exit(f"Error parsing CUIs: {e}")

    if not cuis:
        sys.exit("Error: No CUIs provided.")

    # Load Model Pack
    if not args.model_pack.exists():
        sys.exit(f"Error: Model pack not found at {args.model_pack}")
    print(f"Loading MedCAT model pack from {args.model_pack}...", file=sys.stderr)
    cat = CAT.load_model_pack(str(args.model_pack))

    estim_type = EstimationType(args.stage)
    per_stage_configs: PerStageConfigs = {}
    if args.calibration_curve:
        per_stage_configs[EstimationType.CALIBRATED] = CalibratedEstimationConfig(
            calibration_curve_path=args.calibration_curve,
        )

    # Resolve stage estimator
    try:
        estimator = build_estimator(cat, estim_type, per_stage_configs or None)
    except Exception as e:
        sys.exit(f"Error configuring estimator: {e}")

    # Compute difficulties. Looping (rather than using estimation.get_estimate,
    # which computes the whole batch eagerly) so one bad CUI doesn't abort
    # the rest -- it's reported inline as {"error": ...} instead, as before.
    print(f"Estimating difficulty for {len(cuis)} concept(s) using stage '{args.stage}'...", file=sys.stderr)
    results: dict[str, Any] = {}
    for cui in cuis:
        try:
            results[cui] = dict(estimator.compute_concept_difficulty(cui))
        except Exception as e:
            results[cui] = {"error": str(e)}

    # Output results
    output_json = json.dumps(results, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_json, encoding="utf-8")
        print(f"Saved estimates to {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
