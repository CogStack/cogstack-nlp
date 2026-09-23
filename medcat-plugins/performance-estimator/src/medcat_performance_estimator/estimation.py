"""
Central entry point for computing concept difficulty estimates.

Wires together the three pipeline stages -- ontology-only (stage 1),
training-aware (stage 2), and calibrated -- behind one function,
`get_estimate`, so calling code picks a stage via `EstimationType` rather
than importing and hand-assembling `OntologyDifficultyEstimator`,
`TrainingAwareDifficultyEstimator` and `CalibratedDifficultyEstimator`
(and their supporting `SnomedGraph` / `CDBTrainingFetcher` plumbing) itself.

`per_stage_configs` lets a caller override any one stage's config while
leaving the rest at their defaults. Note that some `EstimationType`s need
more than one stage under the hood -- `CALIBRATED` wraps a stage-2
estimator, which in turn wraps a stage-1 estimator -- so e.g. requesting
`CALIBRATED` while also passing a `STAGE2` (or `STAGE1`) entry in
`per_stage_configs` is honoured: every stage actually built along the way
looks itself up in `per_stage_configs`, not just the top-level `estim_type`.
"""
from enum import Enum

from medcat.cat import CAT

from .common import ConceptDifficulty, DifficultyEstimator, EstimationBaseConfig
from .stage1_ontology import EstimationConfig, OntologyDifficultyEstimator
from .ontology_graph import SnomedGraph
from .stage2_training_aware import TrainingAwareConfig, TrainingAwareDifficultyEstimator
from .training_fetcher import CDBTrainingFetcher
from .stage3_calibration import CalibratedDifficultyEstimator, CalibratedEstimationConfig


class EstimationType(str, Enum):
    STAGE1 = "stage1"
    STAGE2 = "stage2"
    CALIBRATED = "calibrated"


PerStageConfigs = dict[EstimationType, EstimationBaseConfig]


def _config_for(
    estim_type: EstimationType,
    per_stage_configs: PerStageConfigs | None,
    expected_type: type[EstimationBaseConfig],
) -> EstimationBaseConfig | None:
    config = (per_stage_configs or {}).get(estim_type)
    if config is not None and not isinstance(config, expected_type):
        raise TypeError(
            f"per_stage_configs[{estim_type!r}] must be a {expected_type.__name__}, "
            f"got {type(config).__name__}"
        )
    return config


def build_stage1_estimator(
    cat: CAT,
    per_stage_configs: PerStageConfigs | None = None,
) -> OntologyDifficultyEstimator:
    config = _config_for(EstimationType.STAGE1, per_stage_configs, EstimationConfig)
    graph = SnomedGraph(cat.cdb)
    return OntologyDifficultyEstimator(graph, config=config)


def build_stage2_estimator(
    cat: CAT,
    per_stage_configs: PerStageConfigs | None = None,
    stage1: OntologyDifficultyEstimator | None = None,
) -> TrainingAwareDifficultyEstimator:
    config = _config_for(EstimationType.STAGE2, per_stage_configs, TrainingAwareConfig)
    stage1 = stage1 or build_stage1_estimator(cat, per_stage_configs)
    context_weights = cat.config.components.linking.context_vector_weights
    fetcher = CDBTrainingFetcher(cat.cdb)
    return TrainingAwareDifficultyEstimator(
        ontology_estimator=stage1,
        training=fetcher,
        context_vector_weights=context_weights,
        config=config,
    )


def build_calibrated_estimator(
    cat: CAT,
    per_stage_configs: PerStageConfigs | None = None,
) -> CalibratedDifficultyEstimator:
    config = _config_for(EstimationType.CALIBRATED, per_stage_configs, CalibratedEstimationConfig)
    stage2 = build_stage2_estimator(cat, per_stage_configs)
    curve = config.resolve_curve() if config is not None else None
    return CalibratedDifficultyEstimator(wrapped=stage2, curve=curve)


_BUILDERS = {
    EstimationType.STAGE1: build_stage1_estimator,
    EstimationType.STAGE2: build_stage2_estimator,
    EstimationType.CALIBRATED: build_calibrated_estimator,
}


def build_estimator(
    cat: CAT,
    estim_type: EstimationType = EstimationType.CALIBRATED,
    per_stage_configs: PerStageConfigs | None = None,
) -> DifficultyEstimator:
    """Constructs whichever concrete estimator `estim_type` needs (building
    any stages it depends on internally) and returns it as a plain
    `DifficultyEstimator`. Useful over `get_estimate` when a caller wants to
    call `compute_concept_difficulty` per-CUI itself -- e.g. to isolate
    per-CUI errors rather than aborting the whole batch (see `cli.py`)."""
    try:
        builder = _BUILDERS[estim_type]
    except KeyError:
        raise ValueError(f"Unknown estimation type: {estim_type!r}") from None
    return builder(cat, per_stage_configs)


def get_estimate(
    cat: CAT,
    cuis: set[str],
    estim_type: EstimationType = EstimationType.CALIBRATED,
    per_stage_configs: PerStageConfigs | None = None,
) -> dict[str, ConceptDifficulty]:
    """Computes a full `ConceptDifficulty` for each CUI using the requested
    pipeline stage. This is the one entry point most calling code should
    need -- it hides which concrete estimator classes exist and how they're
    wired together.

    Note this computes every CUI eagerly and doesn't catch per-CUI errors;
    a single bad CUI aborts the whole batch. For per-CUI error isolation,
    build an estimator with `build_estimator` and call
    `compute_concept_difficulty` in your own loop (see `cli.py`).
    """
    estimator = build_estimator(cat, estim_type, per_stage_configs)
    return {cui: estimator.compute_concept_difficulty(cui) for cui in cuis}


def get_estimate_scores(
    cat: CAT,
    cuis: set[str],
    estim_type: EstimationType = EstimationType.CALIBRATED,
    per_stage_configs: PerStageConfigs | None = None,
    score: str = "predicted_accuracy",
) -> dict[str, float]:
    """Same as `get_estimate`, but returns just one float per CUI instead of
    the full `ConceptDifficulty` breakdown, for callers that only want a
    single number. `score` selects which `ConceptDifficulty` field to pull
    -- `predicted_accuracy` (default), `min_predicted_accuracy`, or
    `intrinsic_ic`.
    """
    full = get_estimate(cat, cuis, estim_type, per_stage_configs)
    return {cui: diff[score] for cui, diff in full.items()}  # type: ignore[literal-required]
