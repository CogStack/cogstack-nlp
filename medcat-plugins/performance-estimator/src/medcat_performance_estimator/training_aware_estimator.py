import math
import random
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from .estimator import ConceptDifficulty, EstimationConfig, MisconfiguredConcept, NoSynonymsForConcept
from .graphing import AbstractOntologyGraph
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
                self._raw_cosine(cui2combined_vector[a], cui2combined_vector[b])
            )

        if not sims:
            self.mean, self.std = 0.0, 1.0
        else:
            arr = np.array(sims)
            self.mean = float(arr.mean())
            self.std = float(arr.std()) or 1.0  # guard against a degenerate all-equal sample

    @staticmethod
    def _raw_cosine(a: np.ndarray, b: np.ndarray) -> float:
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def normalized_similarity(
        self, a: np.ndarray, b: np.ndarray, temperature: float = 1.0
    ) -> float:
        """Cosine similarity re-expressed relative to the baseline distribution,
        squashed to (0, 1) via a sigmoid so it can be used directly wherever
        stage 1's similarity values are used. 0.5 means "about as similar as
        two typical, unrelated concepts"; higher means unusually close."""
        raw = self._raw_cosine(a, b)
        z = (raw - self.mean) / self.std
        return 1.0 / (1.0 + math.exp(-z / temperature))


# --- config --------------------------------------------------------------

@dataclass(frozen=True)
class TrainingAwareConfig:
    min_train_count: int = 10
    count_confidence_k: float = 20.0
    """Training count at which vector-similarity confidence reaches 0.5."""
    use_log_damping: bool = True
    max_relative_mass: float = 5.0
    """Caps how much a single overrepresented competitor can inflate difficulty."""
    vector_baseline_sample_size: int = 2000
    vector_similarity_temperature: float = 1.0


# --- the estimator itself -------------------------------------------------

class OntologyEstimatorLike(Protocol):
    """Minimal surface this module needs from your stage-1 estimator --
    swap in whatever your resolved dispatch method is actually called if it
    doesn't match `sim_metric` exactly."""

    ontology: AbstractOntologyGraph
    config: EstimationConfig

    def sim_metric(self, concept_a: str, concept_b: str) -> float:
        pass

    def get_intrinsic_ic(self, concept_id: str) -> float:
        pass


class TrainingAwareDifficultyEstimator:
    """Stage 2: combines the stage-1 ontology-only estimate with training
    exposure (counts) and learned representations (context vectors).

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
                if self.training.get_cui_train_count(cui) >= self.config.min_train_count
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
        confidence = count_confidence(min(count_a, count_b), self.config.count_confidence_k)

        similarity = self._get_baseline().normalized_similarity(
            vec_a, vec_b, temperature=self.config.vector_similarity_temperature
        )
        return similarity, confidence

    def blended_pairwise_similarity(self, concept_a: str, concept_b: str) -> float:
        """Ontology similarity, shrunk toward vector similarity in proportion
        to how much we trust the vectors. Reduces to pure ontology similarity
        when confidence is 0 (untrained concepts)."""
        ontology_sim = self.ontology_estimator.get_sim_metric(concept_a, concept_b)
        vector_sim, vector_confidence = self._vector_similarity_and_confidence(
            concept_a, concept_b
        )
        return (ontology_sim + vector_confidence * vector_sim) / (1.0 + vector_confidence)

    def predict_accuracy(self, target_concept: str, name: str) -> float:
        ontology = self.ontology_estimator.ontology
        competing_concepts = ontology.get_concepts_for_name(name)
        if len(competing_concepts) <= 1:
            return 1.0
        if target_concept not in competing_concepts:
            raise MisconfiguredConcept(
                f"{target_concept!r} not found among concepts for name {name!r}; "
                "ontology's name/concept lookups may be inconsistent"
            )

        other_concepts = competing_concepts - {target_concept}
        cfg = self.ontology_estimator.config
        power = cfg.power
        floor = getattr(cfg, "similarity_floor", 0.0)
        target_count = self.training.get_cui_train_count(target_concept)

        effective_N = 1.0
        for other in other_concepts:
            similarity = self.blended_pairwise_similarity(target_concept, other)
            similarity = max(min(similarity, 1.0), floor)
            other_count = self.training.get_cui_train_count(other)
            mass = relative_mass(
                target_count, other_count,
                self.config.use_log_damping, self.config.max_relative_mass,
            )
            effective_N += (similarity ** power) * mass

        return 1.0 / effective_N

    def compute_concept_training_difficulty(self, concept_id: str) -> ConceptDifficulty:
        synonyms = self.ontology_estimator.ontology.get_synonyms_for_concept(concept_id)
        if not synonyms:
            raise NoSynonymsForConcept(
                f"Concept {concept_id!r} has no synonyms in the CDB; concepts "
                "should always have at least one name, so this indicates an "
                "unexpected CDB state that can't be trusted for estimation"
            )

        per_name_accuracy = [self.predict_accuracy(concept_id, name) for name in synonyms]
        overall_accuracy = sum(per_name_accuracy) / len(per_name_accuracy)
        worst_case_accuracy = min(per_name_accuracy)

        return ConceptDifficulty(
            predicted_accuracy=overall_accuracy,
            min_predicted_accuracy=worst_case_accuracy,
            intrinsic_ic=self.ontology_estimator.get_intrinsic_ic(concept_id),
        )
