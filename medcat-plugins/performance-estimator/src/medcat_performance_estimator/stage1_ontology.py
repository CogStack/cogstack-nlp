import math

from .ontology_graph import AbstractOntologyGraph
from .common import (
    ConceptDifficulty, EstimationBaseConfig, ConceptExplanation, ConceptInfo)
from .utils import method_lru_cache as lru_cache


class EstimationConfig(EstimationBaseConfig):
    # options: lin, or resnik, or wu_palmer
    sim_metric: str = "lin"
    # options: # sanchez, or seco
    ic_type: str = "sanchez"
    power: float = 1.0
    # similarities below this are treated as exactly 0
    similarity_floor: float = 0.30
    # only sensible with sim_metric="wu_palmer";
    # double-counts IC if combined with resnik
    apply_extrinsic_ic_prior: bool = False


class OntologyDifficultyEstimator:
    """
    Calculates difficulty metrics for a concept based strictly on ontology.
    """

    def __init__(
        self,
        ontology: AbstractOntologyGraph,
        config: EstimationConfig | None = None
    ):
        self.ontology = ontology
        self.config = config or EstimationConfig()

    # =========================================================================
    # 1. Intrinsic Information Content (IC) Formulations
    # =========================================================================

    def intrinsic_ic_seco(self, concept_id: str) -> float:
        """
        Intrinsic IC according to Seco et al. (2004).
        Normalized IC = 1 - (log(hypo(c) + 1) / log(total_concepts))
        Ranges from 0.0 (root/broad) to 1.0 (leaf/specific).

        Uses log1p(descendants) rather than log(descendants) so that leaves
        (hypo(c) == 0, no descendants) correctly get the maximum IC of 1.0
        instead of needing (and mishandling) a special zero-descendants case.
        """
        descendants = self.ontology.get_subtree_node_count(concept_id)
        total_concepts = self.ontology.get_total_concepts_count()
        if total_concepts <= 1:
            return 0.0
        return 1.0 - (math.log1p(descendants) / math.log(total_concepts))

    def intrinsic_ic_sanchez(self, concept_id: str) -> float:
        """
        Intrinsic IC adapted for biomedical DAGs by Sánchez et al. (2011).
        Takes into account ancestors and leaves to better deal with
        polyhierarchies.
        IC(c) = -log( (|leaves(c)| / |ancestors(c)| + 1) / (
                      |total_leaves| + 1) )
        """
        leaves_c = self.ontology.get_subtree_leaves_count(concept_id)
        ancestors_c = self.ontology.get_ancestors_count(concept_id)
        total_leaves = self.ontology.get_total_leaves_count()

        numerator = (leaves_c / (ancestors_c + 1.0)) + 1.0
        denominator = total_leaves + 1.0

        raw_ic = -math.log(numerator / denominator)
        # Normalize by max possible IC for comparative scale
        max_ic = math.log(denominator)
        return raw_ic / max_ic if max_ic > 0 else 0.0

    def get_intrinsic_ic(self, concept_id: str) -> float:
        return (
            self.intrinsic_ic_sanchez(concept_id)
            if self.config.ic_type == "sanchez"
            else self.intrinsic_ic_seco(concept_id)
        )

    # =========================================================================
    # 2. Concept Pair Similarity Measures
    # =========================================================================

    def sim_wu_palmer(self, concept_a: str, concept_b: str) -> float:
        """
        Wu & Palmer (1994) similarity measure:
        Sim = (2 * depth(LCS)) / (depth(concept_a) + depth(concept_b))
        Returns value in range [0, 1].
        """
        if concept_a == concept_b:
            return 1.0

        lcs = self.ontology.get_lcs(concept_a, concept_b)
        depth_lcs = self.ontology.get_concept_depth(lcs)
        depth_a = self.ontology.get_concept_depth(concept_a)
        depth_b = self.ontology.get_concept_depth(concept_b)

        denom = depth_a + depth_b
        return (2.0 * depth_lcs) / denom if denom > 0 else 0.0

    def sim_resnik_intrinsic(
        self, concept_a: str, concept_b: str,
    ) -> float:
        """
        Resnik (1995) similarity using Intrinsic IC:
        Sim = IC(LCS(concept_a, concept_b))
        """
        if concept_a == concept_b:
            return self.get_intrinsic_ic(concept_a)

        lcs = self.ontology.get_lcs(concept_a, concept_b)
        return self.get_intrinsic_ic(lcs)

    def sim_lin_intrinsic(
        self, concept_a: str, concept_b: str,
    ) -> float:
        """
        Lin (1998) similarity using Intrinsic IC:
        Sim = (2 * IC(LCS)) / (IC(concept_a) + IC(concept_b))
        """
        if concept_a == concept_b:
            return 1.0

        ic_a = self.get_intrinsic_ic(concept_a)
        ic_b = self.get_intrinsic_ic(concept_b)
        ic_lcs = self.get_intrinsic_ic(self.ontology.get_lcs(
            concept_a, concept_b))

        denom = ic_a + ic_b
        return (2.0 * ic_lcs) / denom if denom > 0 else 0.0

    @lru_cache(maxsize=10_000)
    def get_sim_metric(
        self, concept_a: str, concept_b: str,
    ) -> float:
        if self.config.sim_metric == "wu_palmer":
            return self.sim_wu_palmer(concept_a, concept_b)
        elif self.config.sim_metric == "resnik":
            return self.sim_resnik_intrinsic(concept_a, concept_b)
        elif self.config.sim_metric == "lin":
            return self.sim_lin_intrinsic(concept_a, concept_b)
        else:
            raise UnknownSimilarityMetric(
                f"Unknown similarity metric: {self.config.sim_metric}")

    # =========================================================================
    # 3. Overall Concept Difficulty Calculations
    # =========================================================================

    def predict_accuracy_with_diagnostics(
        self, target_concept: str, name: str
    ) -> tuple[float, str | None, float]:
        """Returns (accuracy, worst_competitor_cui, max_competitor_sim)."""
        competing_concepts = self.ontology.get_concepts_for_name(name)
        if len(competing_concepts) <= 1:
            return 1.0, None, 0.0

        if target_concept not in competing_concepts:
            raise MisconfiguredConcept(
                f"{target_concept!r} not found among concepts for name "
                f"{name!r}; ontology's name/concept lookups may be "
                "inconsistent"
            )

        other_concepts = competing_concepts - {target_concept}
        power = self.config.power
        floor = self.config.similarity_floor

        worst_competitor = None
        max_sim = -1.0
        effective_N = 1.0

        for other in other_concepts:
            sim = max(min(
                self.get_sim_metric(target_concept, other), 1.0), floor)
            if sim > max_sim:
                max_sim = sim
                worst_competitor = other
            effective_N += sim ** power

        return 1.0 / effective_N, worst_competitor, max_sim

    def compute_concept_difficulty(self, concept_id: str) -> ConceptDifficulty:
        synonyms = self.ontology.get_synonyms_for_concept(concept_id)
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
        overall_accuracy = sum(per_name_accuracy) / len(per_name_accuracy)
        worst_case_accuracy = min(per_name_accuracy)
        if self.config.apply_extrinsic_ic_prior:
            if self.config.sim_metric in ("resnik", "lin"):
                raise MisconfiguredSimMetric(
                    "apply_extrinsic_ic_prior double-counts IC when combined "
                    f"with sim_metric={self.config.sim_metric!r}")
            # NOTE: multiplying accuracy, not difficulty now
            overall_accuracy *= self.get_intrinsic_ic(concept_id)

        # Identify the worst performing synonym and top competing CUI
        worst_entry = min(diagnostics, key=lambda d: d[1])
        worst_synonym = worst_entry[0]
        worst_competitor = worst_entry[2]

        # Calculate max competitors sharing any single synonym
        max_competitors = max(
            len(self.ontology.get_concepts_for_name(name)) for name in synonyms
        )

        intrinsic_ic = self.get_intrinsic_ic(concept_id)

        features: dict[str, float | int] = {
            "num_synonyms": len(synonyms),
            "max_competitors_per_synonym": max_competitors,
            "intrinsic_ic": intrinsic_ic,
        }

        primary_driver = (
            "semantic_overlap" if worst_entry[3] > 0.7
            else "name_ambiguity" if max_competitors > 1
            else "unknown"
        )

        explanation: ConceptExplanation = {
            "primary_penalty_driver": primary_driver,
            "worst_synonym": worst_synonym,
            "worst_competitor_cui": worst_competitor,
            "feature_breakdown": {},  # Can be populated if quantiles are wired
        }

        return ConceptDifficulty(
            concept_info=self.ontology.get_concept_info(concept_id),
            predicted_accuracy=overall_accuracy,
            min_predicted_accuracy=worst_case_accuracy,
            intrinsic_ic=intrinsic_ic,
            features=features,
            explanation=explanation,
        )


class UnknownSimilarityMetric(ValueError):
    pass


class MisconfiguredSimMetric(ValueError):
    pass


class MisconfiguredConcept(ValueError):
    pass


class NoSynonymsForConcept(ValueError):
    pass
