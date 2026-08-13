import math
from typing import TypedDict

from pydantic import BaseModel

from .graphing import AbstractOntologyGraph


class ConceptDifficulty(TypedDict):
    concept_difficulty: float
    intrinsic_ic: float
    avg_name_confusability: float
    max_name_confusability: float


class EstimationConfig(BaseModel):
    sim_metric: str = "lin"
    ic_type: str = "sanchez"


class OntologyDifficultyEstimator:
    """
    Calculates difficulty metrics for a concept based strictly on ontology properties.
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
        Normalized IC = 1 - (log(leaves(c)) / log(max_leaves))
        Ranges from 0.0 (root/broad) to 1.0 (leaf/specific).
        """
        descendants = self.ontology.get_subtree_node_count(concept_id)
        total_concepts = self.ontology.get_total_concepts_count()

        if total_concepts <= 1 or descendants <= 0:
            return 0.0

        return 1.0 - (math.log(descendants) / math.log(total_concepts))

    def intrinsic_ic_sanchez(self, concept_id: str) -> float:
        """
        Intrinsic IC adapted for biomedical DAGs by Sánchez et al. (2011).
        Takes into account ancestors and leaves to better deal with polyhierarchies.
        IC(c) = -log( (|leaves(c)| / |ancestors(c)| + 1) / (|total_leaves| + 1) )
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

    def intrinsic_ic(self, concept_id: str) -> float:
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
            return self.intrinsic_ic(concept_a)

        lcs = self.ontology.get_lcs(concept_a, concept_b)
        return self.intrinsic_ic(lcs)

    def sim_lin_intrinsic(
        self, concept_a: str, concept_b: str,
    ) -> float:
        """
        Lin (1998) similarity using Intrinsic IC:
        Sim = (2 * IC(LCS)) / (IC(concept_a) + IC(concept_b))
        """
        if concept_a == concept_b:
            return 1.0

        ic_a = self.intrinsic_ic(concept_a)
        ic_b = self.intrinsic_ic(concept_b)
        ic_lcs = self.intrinsic_ic(self.ontology.get_lcs(concept_a, concept_b))

        denom = ic_a + ic_b
        return (2.0 * ic_lcs) / denom if denom > 0 else 0.0

    def sim_metric(
        self, concept_a: str, concept_b: str,
    ) -> float:
        if self.config.sim_metric == "wu_palmer":
            return self.sim_wu_palmer(concept_a, concept_b)
        elif self.config.sim_metric == "resnik":
            return self.sim_resnik_intrinsic(concept_a, concept_b)
        elif self.config.sim_metric == "lin":
            return self.sim_lin_intrinsic(concept_a, concept_b)
        else:
            raise ValueError(
                f"Unknown similarity metric: {self.config.sim_metric}")

    # =========================================================================
    # 3. Overall Concept Difficulty Calculations
    # =========================================================================

    def compute_name_confusability(
        self,
        target_concept: str,
        name: str,
    ) -> float:
        """
        Calculates how ambiguous/confusable a single name is for the target concept.
        Higher score = More ambiguous / harder to disambiguate.
        """
        competing_concepts = self.ontology.get_concepts_for_name(name)
        if len(competing_concepts) <= 1:
            return 0.0  # Name is completely unambiguous

        other_concepts = competing_concepts - {target_concept}

        sim_scores = []

        for other in other_concepts:
            sim = self.sim_metric(target_concept, other)
            sim_scores.append(sim)

        # Average similarity of competing concepts + structural penalty for degree of ambiguity
        avg_similarity = sum(sim_scores) / len(sim_scores)

        # Logarithmic penalty multiplier for the number of competing concepts (N)
        ambiguity_multiplier = math.log2(len(competing_concepts))

        return avg_similarity * ambiguity_multiplier

    def compute_concept_ontology_difficulty(
        self,
        concept_id: str,
    ) -> ConceptDifficulty:
        """
        Computes the complete Stage-1 Ontology-Only Difficulty Profile for a given concept.

        Returns:
            Dict containing raw aggregated scores, IC, and ambiguity bounds.
        """
        synonyms = self.ontology.get_synonyms_for_concept(concept_id)
        if not synonyms:
            return {
                "concept_difficulty": 0.0,
                "intrinsic_ic": 0.0,
                "avg_name_confusability": 0.0,
                "max_name_confusability": 0.0,
            }

        confusability_scores = [
            self.compute_name_confusability(
                concept_id, name
            )
            for name in synonyms
        ]

        avg_confusability = sum(confusability_scores) / len(
            confusability_scores
        )
        max_confusability = max(confusability_scores)

        ic_value = self.intrinsic_ic(concept_id)

        # Combined Difficulty Score:
        # High name ambiguity increases difficulty, high concept specificity (IC) mitigates it.
        overall_difficulty = avg_confusability * (1.01 - ic_value)

        return {
            "concept_difficulty": overall_difficulty,
            "intrinsic_ic": ic_value,
            "avg_name_confusability": avg_confusability,
            "max_name_confusability": max_confusability,
        }
