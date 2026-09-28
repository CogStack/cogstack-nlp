
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

# Limitations
b