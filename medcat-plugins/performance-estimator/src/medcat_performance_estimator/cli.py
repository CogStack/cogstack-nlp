"""
CLI entry point for computing concept difficulty estimates using MedCAT model packs.
"""
import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from medcat.cat import CAT

from .calibration import CalibratedDifficultyEstimator, CalibrationCurve
from .estimator import ConceptDifficulty, OntologyDifficultyEstimator
from .graphing import SnomedGraph
from .training_aware_estimator import TrainingAwareDifficultyEstimator
from .training_fetcher import CDBTrainingFetcher


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


def get_difficulty_function(
    stage: str,
    cat: CAT,
    calibration_curve_path: Path | None = None,
) -> Callable[[str], ConceptDifficulty]:
    """Initializes graph, components, and returns the difficulty computation function."""
    graph = SnomedGraph(cat.cdb)
    stage1 = OntologyDifficultyEstimator(graph)

    if stage == "stage1":
        return stage1.compute_concept_ontology_difficulty

    # Determine base estimation callable for stage2 or calibrated
    if stage == "stage2":
        context_weights = cat.config.components.linking.context_vector_weights
        fetcher = CDBTrainingFetcher(cat.cdb)
        stage2 = TrainingAwareDifficultyEstimator(
            ontology_estimator=stage1,
            training=fetcher,
            context_vector_weights=context_weights,
        )
        return stage2.compute_concept_training_difficulty

    if stage == "calibrated":
        # Resolve calibration curve: custom or fallback to default
        if calibration_curve_path:
            curve = CalibrationCurve.load(calibration_curve_path)
        else:
            curve = CalibrationCurve.default()

        # Duck-typed wrapper applies over stage-1 ontology difficulty
        calibrated_estimator = CalibratedDifficultyEstimator(
            difficulty_fn=stage2.compute_concept_training_difficulty,
            curve=curve,
        )
        return calibrated_estimator.compute_concept_difficulty

    raise ValueError(f"Unknown estimation stage: {stage}")


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
        choices=["stage1", "stage2", "calibrated"],
        default="calibrated",
        help="Estimation pipeline stage.",
    )

    # 4. JSON calibration curve
    parser.add_argument(
        "--calibration-curve",
        type=Path,
        default=None,
        help="Path to custom CalibrationCurve JSON file. Defaults to bundled curve if omitted.",
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

    # Resolve stage estimator
    try:
        difficulty_fn = get_difficulty_function(
            stage=args.stage,
            cat=cat,
            calibration_curve_path=args.calibration_curve,
        )
    except Exception as e:
        sys.exit(f"Error configuring estimator: {e}")

    # Compute difficulties
    print(f"Estimating difficulty for {len(cuis)} concept(s) using stage '{args.stage}'...", file=sys.stderr)
    results: dict[str, Any] = {}
    for cui in cuis:
        try:
            diff = difficulty_fn(cui)
            results[cui] = dict(diff)
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
