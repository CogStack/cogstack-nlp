
#  MedCAT performance estimator
  
This project aims to estimate MedCAT model performance for a certain set of concepts.

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

# Limitations
b