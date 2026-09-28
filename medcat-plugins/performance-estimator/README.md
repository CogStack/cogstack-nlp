
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
a


# Limitations
b