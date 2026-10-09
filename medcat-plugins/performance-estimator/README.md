
#  MedCAT performance estimator
  
This project aims to estimate MedCAT model performance for a certain set of concepts.

> [!WARNING]
> The estimates produced here are rough, aggregate-level guidance for prioritising where to add training data. They are **not** a measurement or guarantee of how your model will perform on any particular concept or on your data. Please read the [Limitations](#limitations) section before using or presenting any of the numbers.

The process is separated into 3 stages:
1. Ontology based estimation
2. Training aware estimation
3. Calibrated estimation

Each subsequenty stage works (at least to an extent) on the otuput of the previous one. There is also a fari few confic entries that can be used in order to modify the estimation procedure. More information on each specific stage can be seen below.

##  Stage1: Ontology based estimation

Most of the ontology estimation is based on the SnomedCT source information along with the trained name-concept pairs. That is to say, we use the directed graph of the concepts in the underlying SnomedCT ontology alongside the synonyms for each concept. These help us understand how specific a concept we're dealing with, how ambiguous the synonyms are (i.e how many other concepts they could refer to), and so on.

More specifically, these are the main features we extract within this stage:
- The intrinsic information content (IC) of a concept (both are normalised to roughly `[0, 1]`, with higher meaning more specific)
	- [Sanchez (`sanchez`) intrinsic IC for biomedical DAGs](https://www.sciencedirect.com/science/article/abs/pii/S0950705110001619)
		- Effectively `IC(c) = -log((|leaves(c)| / (|ancestors(c)| + 1) + 1) / (|total_leaves| + 1))`
		- Normalised by dividing by the maximum possible IC, `log(|total_leaves| + 1)`
	- [Seco (`seco`) based intrinsic IC](https://www.researchgate.net/profile/Jer-Hayes/publication/220837848_An_Intrinsic_Information_Content_Metric_for_Semantic_Similarity_in_WordNet/links/0fcfd50a2122fa6910000000/An-Intrinsic-Information-Content-Metric-for-Semantic-Similarity-in-WordNet.pdf)
		- Effectively `IC(c) = 1 - (log(hypo(c) + 1) / log(total_concepts))`
		- Where `hypo` is the subtree node count (i.e. the number of descendants), so leaves get an IC of exactly 1
- Pairwise concept similarity, options
	- [Wu & Palmer (`wu_palmer`) similarity](https://aclanthology.org/P94-1019.pdf)
		- Effectively `(2 * depth(LCS)) / (depth(concept_a) + depth(concept_b))`
		- Where `LCS` is Least Common Subsumer (most specific common ancestor)
	- [Resnik (`resnik`) intrinsic similarity](https://arxiv.org/abs/cmp-lg/9511007)
		- Effectively `IC(LCS(concept_a, concept_b))`
		- Where `IC` is the intrinsic IC from above
	- [Lin (`lin`) similarity using intrinsic concept IC](https://scholar.google.com/scholar?hl=en&as_sdt=0%2C5&q=Dekang+Lin+An+Information-Theoretic+Definition+of+Similarity.++1998&btnG=)
		- Effectively `(2 * IC(LCS)) / (IC(concept_a) + IC(concept_b))`

The concept's predicted accuracy (and hence difficulty) is finally calculated as follows:
- For each of the concept's names (synonyms), we find all concepts that share that name
	- If the name is unique to the concept, the predicted accuracy for that name is `1.0`
	- Otherwise, the similarity between the target concept and each competing concept is calculated using `sim_metric`
	- Each similarity is clamped to `[similarity_floor, 1.0]`, so every competitor counts for at least the floor value
	- The name's accuracy is `1 / (1 + sum(sim ** power))` over the competitors
		- With all similarities at `1.0` this is the chance of picking the right concept uniformly at random among all `N` candidates
		- Less similar competitors contribute less, and a higher `power` shrinks their contribution further
- The concept's predicted accuracy is the mean of the per-name accuracies
	- The lowest per-name accuracy is also kept as the worst-case (minimum) predicted accuracy
- Then (if `apply_extrinsic_ic_prior` is set) the mean accuracy is multiplied by the concept's intrinsic IC
	- This is only sensible with `wu_palmer`; combining it with `resnik` or `lin` raises an error since those already build IC into the similarity

The config options used for this stage:
- `sim_metric` (either `lin` (default), `resnik`, or `wu_palmer`)
- `ic_type` (either `sanchez` (default), or `seco`)
- `power` (the power used in the concept-name prediction)
- `similarity_floor` (the similarity floor to use, defualts to `0.3`)

## Stage2: Training aware estimation

This stage has access to the per concept (and per name) training counts on top of what was available for the previous stage. This allows the estimation to take advantage of the train counts where applicable. The idea being that - all else being equal - a concept that has more training will perform better than one that's had less training.

Stage 2 wraps the Stage 1 estimator and reuses its ontology similarity, its `power` and its `similarity_floor`. On top of that it uses the trained context vectors and the training counts. The features it adds are:
- Vector similarity between concepts, corrected for anisotropy
	- Context vectors are first combined into a single vector per concept using the configured `context_vector_weights`
	- The raw cosine similarity of two such vectors is only meaningful relative to what's normal for the embedding space (contextual embeddings tend to sit in a narrow band)
	- So we sample random pairs of trained concepts (up to `vector_baseline_sample_size` pairs, only from concepts with at least `min_train_count` training examples) to get the mean and standard deviation of the "typical" cosine
	- The similarity is then `sigmoid(((cosine - mean) / std) / vector_similarity_temperature)`
	- This gives a value in `(0, 1)` where `0.5` is "about as similar as two typical, unrelated concepts" and higher is unusually close
- Confidence in the vector similarity
	- A function of the *smaller* of the two concepts' training counts (the pairwise comparison is only as trustworthy as its noisier side)
	- Grows with the count, reaching `0.5` at `count_confidence_k`
- Blended pairwise similarity
	- `(ontology_sim + confidence * vector_sim) / (1 + confidence)`
	- Since confidence is below 1, the ontology similarity always keeps at least half of the weight
	- With zero confidence (untrained concepts) this is exactly the Stage 1 similarity
- Relative training mass of a competitor
	- How much more (or less) training a competing concept has compared to the target concept
	- Optionally log-damped (`use_log_damping`) and capped at `max_relative_mass`, so that one heavily trained competitor can't inflate the difficulty without limit
- Per name-concept mass (used to weight names)
	- If the name was never seen in training, the weight is `1.0`
	- Otherwise the name's training count is allocated between the concepts sharing it, in proportion to their (Laplace smoothed, i.e. `+1`) training counts
	- The weight is then `log1p(allocated_count) + 1`, so names the concept has actually been trained on matter more, without completely drowning out the rest

The concept's difficulty is finally calculated as follows:
- Each concept's predicted accuracy is found for each of its names (same idea as Stage 1)
	- If the name is unique to the concept, the predicted accuracy for that name is `1.0`
	- Otherwise, for each competing concept, the blended similarity is clamped to `[similarity_floor, 1.0]`
	- Each competitor then contributes `sim ** power * relative_mass` to the denominator
	- The name's accuracy is `1 / (1 + sum(sim ** power * relative_mass))` over the competitors
	- With all masses at `1` (e.g. no training) this is identical to the Stage 1 per-name accuracy
- The concept's predicted accuracy is the *weighted* mean of the per-name accuracies, using the per name-concept mass above (Stage 1 uses a plain mean)
	- The lowest per-name accuracy is again kept as the worst-case (minimum) predicted accuracy
- Unlike Stage 1, no intrinsic IC prior is applied at this stage (`apply_extrinsic_ic_prior` is not used here)

The config options used for this stage (`TrainingAwareConfig`):
- `min_train_count` (the minimum training count for a concept to be included in the vector similarity baseline, defaults to `10`)
- `count_confidence_k` (the training count at which the vector similarity confidence reaches `0.5`, defaults to `10.0`)
- `use_log_damping` (whether to log-damp the relative training mass of competitors, defaults to `True`)
- `max_relative_mass` (the cap on a single competitor's relative mass, defaults to `5.0`)
- `vector_baseline_sample_size` (the number of random concept pairs used to estimate the baseline cosine, defaults to `2000`)
- `vector_similarity_temperature` (the sigmoid temperature for the normalised vector similarity, defaults to `1.0`)

The `power` and `similarity_floor` options come from the wrapped Stage 1 `EstimationConfig` rather than from this stage's own config.

## Stage3: Calibrated estimate

We find that often the estimate from stage2 (and stage1 to be fair) is higher than the real world performance. Because of that we've developed a calibration curve (and you can provide your own if you wish) that's used to mitigate that somewhat.

Stage 3 doesn't compute anything new about the concepts. It wraps either the Stage 1 or the Stage 2 estimator and rescales their output through a fitted calibration curve. The curve is a monotone mapping from the raw predicted accuracy closer to the accuracy we actually observe in practice. It fixes the *scale* of the estimate rather than the *ranking* (a concept with a higher raw estimate never gets a lower calibrated one).

More specifically, these are the pieces involved:
- The calibration curve (`CalibrationCurve`)
	- A sorted list of `(raw_score, calibrated_score)` breakpoints, where the calibrated scores must be non-decreasing
	- Applied by linear interpolation between the breakpoints; raw scores outside the fitted range are clamped to the nearest endpoint
	- Stored as plain JSON (`raw_scores` and `calibrated_scores` lists), so it's easy to version, diff and swap out
	- Applying a curve needs no scikit-learn; only fitting does
	- There is a bundled default curve (`CalibrationCurve.default()`) and a no-op `identity()` curve (calibrated == raw)
- The fitter (`fit_calibration_curve`)
	- An offline script that fits an isotonic regression of the observed accuracy on the raw estimate (clipped to `[0, 1]`)
	- The fitted function is sampled on an evenly spaced 200-point grid across the raw score range seen in the fit data, and that grid is what's saved as the curve
	- Takes a CSV with a `raw_estimate` column (the `predicted_accuracy` from the stage being calibrated) and an `observed_accuracy` column (the measured real-world accuracy per concept, e.g. recall on an entity linking evaluation set)
	- The data is randomly split, and the curve is fit on the fit split only. The rest (`--holdout-fraction`, default `0.2`) is held out for evaluation
	- Prints holdout diagnostics only, since a curve scored on the data it was fit on looks better than it really is:
		- The correlation between raw estimate and observed accuracy
		- The mean absolute error (MAE) against observed accuracy, before and after calibration
		- A binned reliability error (mean absolute gap between average score and average observed accuracy per 0.1-wide bin), before and after calibration
	- Warns if calibration did not reduce the holdout MAE, which usually means the raw estimate isn't correlated enough with the observed accuracy for the curve to be useful

The calibrated difficulty is finally calculated as follows:
- The wrapped estimator (Stage 1 or Stage 2) computes its `ConceptDifficulty` as normal
- `predicted_accuracy` is passed through the curve
- `min_predicted_accuracy` (the worst-case per-name accuracy) is passed through the same curve
- Everything else (`concept_info`, `intrinsic_ic`, `features` and `explanation`) is passed through untouched
	- `intrinsic_ic` is an ontology property rather than a performance prediction, so there is nothing to calibrate it against

Usage:
- Fit a curve, once per estimator you want to calibrate:
	- `python -m medcat_performance_estimator.fit_calibration_curve --input eval_results.csv --output stage1_calibration.json --holdout-fraction 0.2`
	- Other options: `--raw-column`, `--observed-column` and `--seed` (defaults to `0`)
- Wrap the estimator:
	- `CalibratedDifficultyEstimator(stage1, CalibrationCurve.load("stage1_calibration.json"))`
	- If no curve is given, the bundled default curve is used

The config options used for this stage (`CalibratedEstimationConfig`):
- `calibration_curve` (a `CalibrationCurve` object; takes precedence over the path if both are given)
- `calibration_curve_path` (path to a curve JSON file)
- If neither is set, `resolve_curve()` falls back to the bundled default curve

## Tiers

The estimates are most useful in aggregate, and a single accuracy number per concept invites more precision than it can deliver (see [Limitations](#limitations)). So, to make the estimates actionable, concepts are grouped into three tiers, each answering the practical question "how much fine-tuning is this concept likely to need?":

- **Tier A**: concepts that might not need any fine-tuning
- **Tier B**: concepts that will probably benefit from some fine-tuning
- **Tier C**: concepts that will probably need a lot of (or more) fine-tuning

The tiers are ordered by predicted accuracy: Tier A has the highest scores and Tier C the lowest. A concept's tier is decided by comparing its score against two thresholds, `a_min` and `b_min`. Anything at or above `a_min` is Tier A, anything else at or above `b_min` is Tier B, and everything below that is Tier C.

The tiers are meant to help decide where training effort is best spent on average. They are not a per-concept verdict: a concept in a lower tier can still perform better than one in a higher tier. See the [Usage](#usage) section for how to get the tiers, and how to change the thresholds.

## Usage

There are two ways to run the estimation: the command line (for a quick look at a set of concepts) and the Python API (for building something on top, e.g. a UI that shows which concepts to train on). Both need a MedCAT model pack, since the ontology, synonyms and training counts all come from the model's CDB.

### Command line

```
python -m medcat_performance_estimator.cli \
    --model-pack path/to/model_pack.zip \
	# NOTE: example uses two concepts but this process
	#       is unlikely to have super accurate / valuable
	#       output for such a small number of concepts; we
	#       use a small number of concepts here for brevity
	#       of documentation
    --cuis 195967001,22298006 \
    --output estimates.json
```

The options are:
- `--model-pack` / `-m` (required): path to the MedCAT model pack (`.zip` or folder)
- The concepts to estimate (required; exactly one of):
	- `--cuis` / `-c`: comma-separated list of CUIs
	- `--cui-file` / `-f`: path to a JSON file containing a list of CUIs (e.g. `["195967001", "22298006"]`)
- `--stage` / `-s`: which stage to use: `stage1`, `stage2` or `calibrated` (default)
- `--calibration-curve`: path to your own calibration curve JSON (see Stage 3). Only used with `--stage calibrated`; the bundled default curve is used if omitted
- `--output` / `-o`: where to write the JSON results. If omitted, the JSON is printed to stdout (progress messages go to stderr, so stdout stays clean JSON)

The output is a JSON object keyed by CUI. Each value is that concept's full estimate:

```json
{
  "195967001": {
    "concept_info": { "...": "..." },
    "predicted_accuracy": 0.62,
    "min_predicted_accuracy": 0.41,
    "intrinsic_ic": 0.78,
    "features": {
      "cui_train_count": 120,
      "num_synonyms": 5,
      "max_competitors_per_synonym": 3,
      "max_competitor_mass_ratio": 1.4,
      "intrinsic_ic": 0.78
    },
    "explanation": {
      "primary_penalty_driver": "name_ambiguity",
      "worst_synonym": "...",
      "worst_competitor_cui": "...",
      "feature_breakdown": {}
    }
  },
  "not_a_real_cui": { "error": "..." }
}
```

- `predicted_accuracy` is the headline number (the mean over the concept's names) and `min_predicted_accuracy` is the worst-case name
- Lower means harder, i.e. more likely to need training data
- A CUI that fails (e.g. it isn't in the CDB) is reported inline as `{"error": "..."}` and doesn't stop the rest of the batch
- The numbers shown above are illustrative only

### Python API

Everything lives in `medcat_performance_estimator.estimation`. Load a model pack, pick a stage with `EstimationType` (`STAGE1`, `STAGE2` or `CALIBRATED`, the default), and call one of:

- `get_estimate(cat, cuis)`: a full `ConceptDifficulty` per CUI (the same structure as the CLI output)
- `get_estimate_scores(cat, cuis)`: just one number per CUI. `score` is `predicted_accuracy` (default), `min_predicted_accuracy` or `intrinsic_ic`
- `get_tiered_estimate(cat, cuis)`: the estimates grouped into action tiers (see below)
- `build_estimator(cat, estim_type)`: the underlying estimator, for when you want to call `compute_concept_difficulty(cui)` yourself

```python
from medcat.cat import CAT
from medcat_performance_estimator.estimation import (
    EstimationType, get_estimate, get_tiered_estimate)

cat = CAT.load_model_pack("path/to/model_pack.zip")
cuis = {"195967001", "22298006"}

estimates = get_estimate(cat, cuis)  # calibrated by default
tiers = get_tiered_estimate(cat, cuis)
```

#### Choosing which concepts to train on

`get_tiered_estimate` sorts the concepts into three tiers by comparing a score against two thresholds. `ActionTier.A` is for scores at or above `a_min`, `ActionTier.B` for scores at or above `b_min`, and `ActionTier.C` for everything else. It returns `dict[ActionTier, dict[str, ConceptDifficulty]]`, so each tier holds its concepts along with their full estimates.

- By default the tier is decided by `predicted_accuracy`. Pass `score_key="min_predicted_accuracy"` to tier on the worst-case name instead
- Custom boundaries can be passed as `thresholds={"a_min": ..., "b_min": ...}`. The defaults are `DEFAULT_TIER_THRESHOLDS` in `common`
- If you already have estimates, `group_estimates_by_tier(estimates, thresholds, score_key)` does the grouping without recomputing, and `assign_tier(score)` classifies a single score

For something like a UI (buckets, the concepts in each bucket, and per-concept details), this is the intended shape:

```python
from medcat_performance_estimator.estimation import (
    EstimationType, build_estimator, group_estimates_by_tier)

# Build once and reuse: this constructs the ontology graph, which is the
# expensive part.
estimator = build_estimator(cat, EstimationType.CALIBRATED)

estimates, errors = {}, {}
for cui in cuis:
    try:
        estimates[cui] = estimator.compute_concept_difficulty(cui)
    except Exception as e:
        errors[cui] = str(e)

tiers = group_estimates_by_tier(estimates)
payload = {
    tier.name: {
        cui: dict(diff) for cui, diff in concepts.items()
    }
    for tier, concepts in tiers.items()
}
```

Each concept in a bucket then carries what a UI needs to show:
- The scores: `predicted_accuracy`, `min_predicted_accuracy` and `intrinsic_ic`
- A short reason, in `explanation["primary_penalty_driver"]`, together with the `worst_synonym` and `worst_competitor_cui` behind it
	- Stage 1 drivers: `semantic_overlap`, `name_ambiguity`, `unknown`
	- Stage 2 (and calibrated) also has `training_imbalance` and `zero_training_exposure`
- The documented features, in `features` (e.g. `cui_train_count`, `num_synonyms`, `max_competitors_per_synonym`)

#### Configuring the stages

Any stage's config can be overridden through `per_stage_configs`, a dict from `EstimationType` to that stage's config object. Stages you don't mention keep their defaults.

```python
from medcat_performance_estimator.estimation import EstimationType, get_estimate
from medcat_performance_estimator.stage1_ontology import EstimationConfig
from medcat_performance_estimator.stage2_training_aware import TrainingAwareConfig
from medcat_performance_estimator.stage3_calibration import (
    CalibratedEstimationConfig)

estimates = get_estimate(
    cat, cuis, EstimationType.CALIBRATED,
    per_stage_configs={
        EstimationType.STAGE1: EstimationConfig(sim_metric="wu_palmer"),
        EstimationType.STAGE2: TrainingAwareConfig(min_train_count=20),
        EstimationType.CALIBRATED: CalibratedEstimationConfig(
            calibration_curve_path="my_curve.json"),
    },
)
```

- Requesting a later stage builds the earlier ones underneath it (`CALIBRATED` wraps `STAGE2`, which wraps `STAGE1`), and each of them picks up its own entry from `per_stage_configs`
- A config of the wrong type for its stage raises a `TypeError`


## Limitations

Please keep the following in mind when interpreting the estimates.

### 1. The estimate does not correspond to a specific, measured metric

The predicted accuracy is not an estimate of any specific metric of the full MedCAT pipeline. The closest thing to a well-defined target is the recall of a linker-only setup (i.e. with a perfect NER step), and that is what the calibration is meant to approximate. Even then, the estimates will not be exact. They are a heuristic built from ontology structure, name ambiguity and training exposure, not a model of the real pipeline. End-to-end performance also depends on things not modelled here, such as NER quality, the text being processed, and other config choices. Treat the numbers as a relative signal, not as literal accuracy or recall values.

### 2. The estimates are meaningful in aggregate, not per concept

The estimates say something useful about groups of concepts, but much less about any individual concept. This is the reason for the tiering. On average, concepts in Tier A will perform better than those in Tier B, and those in Tier B will perform better than those in Tier C. However, for a sufficiently large set of concepts there will almost certainly be concepts in a lower tier that perform better than most concepts in a higher tier. The tiers should be used to decide where training effort is best spent on average, not to make claims about a specific concept.

### 3. We do not know what we do not know

One of the main limitations is missing synonyms. The estimate can only reason about the names and concepts that are known to the model. If the text you are about to use MedCAT on is likely to contain synonyms that the model isn't aware of, this cannot be estimated, and the real performance will likely be considerably worse than predicted. Missing names can also hide ambiguity: a name we don't know about can't show up as a competitor for the concepts it would clash with.

The effect on the estimates can also be hard to predict. If some concepts (e.g. those in particular tiers) are missing more synonyms than others, the estimates can end up biased in ways that are not visible from the numbers themselves.

### 4. Per-concept details are best-effort

The output includes per-concept numbers, some feature values and a limited explanation of the estimate (e.g. the primary penalty driver and the worst synonym / competitor). These are provided on a best-effort basis. In isolation they are not very useful, and they should not be read as a reliable account of why a specific concept will perform well or badly. In particular, no specific guarantees are made about any individual concept's estimate or explanation. The point from 2 applies here as well: the value lies in the aggregate picture.
