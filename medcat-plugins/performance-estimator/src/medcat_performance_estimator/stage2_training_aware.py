import math
import random
from typing import Protocol

import numpy as np
from pydantic import ConfigDict, Field

from .common import (
    ConceptDifficulty, EstimationBaseConfig, ConceptExplanation, ConceptInfo)
from .stage1_ontology import (
    EstimationConfig, MisconfiguredConcept, NoSynonymsForConcept)
from .ontology_graph import AbstractOntologyGraph
from .training_fetcher import TrainingFetcher
from .utils import combine_context_vector, count_confidence, relative_mass

# --- vector similarity, corrected for embedding-space anisotropy -------


class VectorSimilarityBaseline:
    """Estimates the "typical" pairwise cosine similarity between unrelated
    concept vectors, so a raw cosine can be judged relative to what's normal
    for this embedding space rather than taken at face value.

    Contextual embedding spaces are usually anisotropic -- raw cosines
    cluster in a narrow, non-obvious band rather than spanning -1..1 -- so
    e.g. a raw cosine of 0.6 might be unremarkable or might be unusually
    high, and there's no way to know without a reference distribution.
    """

    def __init__(
        self,
        cui2combined_vector: dict[str, np.ndarray],
        sample_size: int = 2000,
        seed: int = 0,
    ) -> None:
        cuis = [
            c for c, v in cui2combined_vector.items()
            if np.linalg.norm(v) > 0]
        rng = random.Random(seed)
        n_pairs = min(sample_size, len(cuis) * (len(cuis) - 1) // 2)
        sims: list[float] = []
        seen_pairs: set[tuple[str, str]] = set()
        attempts = 0
        # Rejection-sample distinct pairs; cheap relative to n_pairs for any
        # reasonably sized concept set.
        while len(sims) < n_pairs and attempts < n_pairs * 20:
            attempts += 1
            a, b = rng.sample(cuis, 2)
            pair = (a, b) if a < b else (b, a)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            sims.append(
                self._raw_cosine(
                    cui2combined_vector[a], cui2combined_vector[b])
            )

        if not sims:
            self.mean, self.std = 0.0, 1.0
        else:
            arr = np.array(sims)
            self.mean = float(arr.mean())
            # guard against a degenerate all-equal sample
            self.std = float(arr.std()) or 1.0

    @staticmethod
    def _raw_cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def normalized_similarity(
        self, a: np.ndarray, b: np.ndarray, temperature: float = 1.0
    ) -> float:
        """Cosine similarity re-expressed relative to the baseline
        distribution, squashed to (0, 1) via a sigmoid so it can be used
        directly wherever stage 1's similarity values are used. 0.5 means
        "about as similar as two typical, unrelated concepts"; higher means
        unusually close."""
        raw = self._raw_cosine(a, b)
        z = (raw - self.mean) / self.std
        return 1.0 / (1.0 + math.exp(-z / temperature))


# --- config --------------------------------------------------------------

class TrainingAwareConfig(EstimationBaseConfig):
    model_config = ConfigDict(frozen=True)

    min_train_count: int = 10
    count_confidence_k: float = Field(
        default=10.0,
        description="Training count at which vector-similarity confidence "
                    "reaches 0.5.",
    )
    use_log_damping: bool = True
    max_relative_mass: float = Field(
        default=5.0,
        description="Caps how much a single overrepresented competitor can "
                    "inflate difficulty.",
    )
    vector_baseline_sample_size: int = 2000
    vector_similarity_temperature: float = 1.0


# --- the estimator itself -------------------------------------------------

class OntologyEstimatorLike(Protocol):

    ontology: AbstractOntologyGraph
    config: EstimationConfig

    def get_sim_metric(self, concept_a: str, concept_b: str) -> float:
        pass

    def get_intrinsic_ic(self, concept_id: str) -> float:
        pass


class TrainingAwareDifficultyEstimator:
    """Stage 2: combines the stage-1 ontology-only estimate with training
    exposure (counts) and learned representations (context vectors).

    Implements the same `DifficultyEstimator` protocol (`.common`) as
    `OntologyDifficultyEstimator` and `CalibratedDifficultyEstimator` --
    just `compute_concept_difficulty(concept_id) -> ConceptDifficulty`.

    Guaranteed to reduce EXACTLY to the wrapped ontology estimator's own
    `predict_accuracy` when a concept and all its competitors have zero
    training count -- this is intentional and worth a unit test, since it's
    the diagnostic property that lets you confirm this stage adds signal
    without changing behaviour on an untrained model.
    """

    def __init__(
        self,
        ontology_estimator: OntologyEstimatorLike,
        training: TrainingFetcher,
        context_vector_weights: dict[str, float],
        config: TrainingAwareConfig | None = None,
    ) -> None:
        self.ontology_estimator = ontology_estimator
        self.training = training
        self.context_vector_weights = context_vector_weights
        self.config = config or TrainingAwareConfig()

        self._combined_vector_cache: dict[str, np.ndarray] = {}
        self._baseline: VectorSimilarityBaseline | None = None

    def _combined_vector(self, cui: str) -> np.ndarray:
        if cui not in self._combined_vector_cache:
            raw = self.training.get_cui_context_vector(cui)
            self._combined_vector_cache[cui] = combine_context_vector(
                raw, self.context_vector_weights
            )
        return self._combined_vector_cache[cui]

    def _get_baseline(self) -> VectorSimilarityBaseline:
        if self._baseline is None:
            all_vectors = self.training.get_cui2context_vector()
            combined = {
                cui: combine_context_vector(vecs, self.context_vector_weights)
                for cui, vecs in all_vectors.items()
                if self.training.get_cui_train_count(
                    cui) >= self.config.min_train_count
            }
            self._baseline = VectorSimilarityBaseline(
                combined, sample_size=self.config.vector_baseline_sample_size
            )
        return self._baseline

    def _vector_similarity_and_confidence(
        self, concept_a: str, concept_b: str
    ) -> tuple[float, float]:
        """Returns (similarity, confidence), both 0.0 if either concept has
        no usable vector -- this naturally makes the confidence term 0 when
        a concept is untrained, since it won't have a meaningful vector yet."""
        vec_a = self._combined_vector(concept_a)
        vec_b = self._combined_vector(concept_b)
        if vec_a is None or vec_b is None:
            return 0.0, 0.0

        count_a = self.training.get_cui_train_count(concept_a)
        count_b = self.training.get_cui_train_count(concept_b)
        # Trust the pairwise comparison only as much as its noisier side.
        confidence = count_confidence(
            min(count_a, count_b), self.config.count_confidence_k)

        similarity = self._get_baseline().normalized_similarity(
            vec_a, vec_b, temperature=self.config.vector_similarity_temperature
        )
        return similarity, confidence

    def blended_pairwise_similarity(
        self, concept_a: str, concept_b: str,
    ) -> float:
        """Ontology similarity, shrunk toward vector similarity in proportion
        to how much we trust the vectors. Reduces to pure ontology similarity
        when confidence is 0 (untrained concepts)."""
        ontology_sim = self.ontology_estimator.get_sim_metric(
            concept_a, concept_b)
        vector_sim, vector_confidence = self._vector_similarity_and_confidence(
            concept_a, concept_b
        )
        return (ontology_sim + vector_confidence * vector_sim) / (
            1.0 + vector_confidence)

    def predict_accuracy_with_diagnostics(
        self, target_concept: str, name: str
    ) -> tuple[float, str | None, float, float]:
        """Returns (accuracy, worst_competitor, max_adversary, max_mass)."""
        ontology = self.ontology_estimator.ontology
        competing_concepts = ontology.get_concepts_for_name(name)
        if len(competing_concepts) <= 1:
            return 1.0, None, 0.0, 1.0
        if target_concept not in competing_concepts:
            raise MisconfiguredConcept(
                f"{target_concept!r} not found among concepts for "
                f"name {name!r}; ontology's name/concept lookups "
                "may be inconsistent"
            )

        other_concepts = competing_concepts - {target_concept}
        cfg = self.ontology_estimator.config
        power = cfg.power
        floor = getattr(cfg, "similarity_floor", 0.0)
        target_count = self.training.get_cui_train_count(target_concept)

        effective_N = 1.0
        worst_competitor = None
        max_adversary_term = -1.0
        max_mass = 1.0

        for other in other_concepts:
            sim = max(min(self.blended_pairwise_similarity(
                target_concept, other), 1.0), floor)
            other_count = self.training.get_cui_train_count(other)
            mass = relative_mass(
                target_count, other_count,
                self.config.use_log_damping, self.config.max_relative_mass
            )
            term = (sim ** power) * mass
            if term > max_adversary_term:
                max_adversary_term = term
                worst_competitor = other
                max_mass = mass

            effective_N += term

        return (
            1.0 / effective_N,
            worst_competitor, max_adversary_term, max_mass
        )

    def _estimate_cui_name_mass(self, cui: str, name: str) -> float:
        name_count = self.training.get_name_train_count(name)
        if name_count == 0:
            return 1.0  # Base unobserved weight

        competing_cuis = (
            self.ontology_estimator.ontology.get_concepts_for_name(name))

        # Laplace-smoothed mass allocation
        cui_count = self.training.get_cui_train_count(cui) + 1.0
        total_competing_count = sum(
            self.training.get_cui_train_count(other) + 1.0
            for other in competing_cuis
        )

        allocated_count = name_count * (cui_count / total_competing_count)

        # Log-damp to prevent dominant mentions from completely zeroing
        # out other synonyms
        return math.log1p(allocated_count) + 1.0

    def compute_concept_difficulty(self, concept_id: str) -> ConceptDifficulty:
        synonyms = self.ontology_estimator.ontology.get_synonyms_for_concept(
            concept_id)
        if not synonyms:
            raise NoSynonymsForConcept(
                f"Concept {concept_id!r} has no synonyms in the CDB; concepts "
                "should always have at least one name, so this indicates an "
                "unexpected CDB state that can't be trusted for estimation"
            )

        diagnostics = [
            (name, *self.predict_accuracy_with_diagnostics(concept_id, name))
            for name in synonyms
        ]

        per_name_accuracy = [d[1] for d in diagnostics]
        weights = [self._estimate_cui_name_mass(
            concept_id, name) for name in synonyms]
        overall_accuracy = sum(w * acc for w, acc in zip(
            weights, per_name_accuracy)) / sum(weights)
        worst_case_accuracy = min(per_name_accuracy)

        raw_ont = self.ontology_estimator.ontology

        # Extract worst case diagnostics
        worst_entry = min(diagnostics, key=lambda d: d[1])
        worst_synonym = worst_entry[0]
        worst_comp_cui = worst_entry[2]
        worst_comp_name = (
            raw_ont.get_concept_preferred_name(worst_comp_cui)
            if worst_comp_cui else "N/A"
        )
        worst_competitor = f"{worst_comp_cui} | {worst_comp_name}"
        worst_mass = worst_entry[4]

        target_train_count = self.training.get_cui_train_count(concept_id)
        max_competitors = max(
            len(self.ontology_estimator.ontology.get_concepts_for_name(name))
            for name in synonyms
        )

        # Determine primary penalty driver
        if worst_mass >= 2.0:
            primary_driver = "training_imbalance"
        elif worst_entry[3] > 0.5:
            primary_driver = "semantic_overlap"
        elif max_competitors > 1:
            primary_driver = "name_ambiguity"
        elif target_train_count == 0:
            primary_driver = "zero_training_exposure"
        else:
            primary_driver = "unknown"

        intrinsic_ic = self.ontology_estimator.get_intrinsic_ic(concept_id)

        features: dict[str, float | int] = {
            "cui_train_count": target_train_count,
            "num_synonyms": len(synonyms),
            "max_competitors_per_synonym": max_competitors,
            "max_competitor_mass_ratio": worst_mass,
            "intrinsic_ic": intrinsic_ic,
        }

        explanation: ConceptExplanation = {
            "primary_penalty_driver": primary_driver,
            "worst_synonym": worst_synonym,
            "worst_competitor_cui": worst_competitor,
            "feature_breakdown": {},
        }

        ci = raw_ont.get_concept_info(concept_id)

        return ConceptDifficulty(
            concept_info=ci,
            predicted_accuracy=overall_accuracy,
            min_predicted_accuracy=worst_case_accuracy,
            intrinsic_ic=intrinsic_ic,
            features=features,
            explanation=explanation,
        )
