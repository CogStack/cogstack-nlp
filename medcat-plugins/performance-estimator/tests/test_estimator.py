from typing import Dict, Set, Tuple
import unittest

from medcat_performance_estimator.graphing import AbstractOntologyGraph
from medcat_performance_estimator.estimator import (
    MisconfiguredConcept, MisconfiguredSimMetric, OntologyDifficultyEstimator,
    EstimationConfig, UnknownSimilarityMetric
)


# =============================================================================
# 1. Mock AbstractOntologyGraph Implementation
# =============================================================================

class InMemoryOntologyGraph(AbstractOntologyGraph):
    """
    In-memory test double for AbstractOntologyGraph.
    Allows declarative setup of concepts, synonyms, parent-child links, and leaves.
    """

    def __init__(self):
        self.name_to_concepts: Dict[str, Set[str]] = {}
        self.concept_to_names: Dict[str, Set[str]] = {}
        self.depths: Dict[str, int] = {}
        self.lcs_map: Dict[Tuple[str, str], str] = {}
        self.leaves_count: Dict[str, int] = {}
        self.ancestors_count: Dict[str, int] = {}
        self.subtree_nodes_count: Dict[str, int] = {}
        self.total_leaves: int = 1
        self.total_concepts: int = 1

    def add_concept(
        self,
        concept_id: str,
        synonyms: list[str],
        depth: int = 1,
        leaves: int = 1,
        ancestors: int = 0,
        subtree_nodes: int = 1,
    ):
        self.concept_to_names[concept_id] = set(synonyms)
        for name in synonyms:
            if name not in self.name_to_concepts:
                self.name_to_concepts[name] = set()
            self.name_to_concepts[name].add(concept_id)

        self.depths[concept_id] = depth
        self.leaves_count[concept_id] = leaves
        self.ancestors_count[concept_id] = ancestors
        self.subtree_nodes_count[concept_id] = subtree_nodes

    def set_lcs(self, concept_a: str, concept_b: str, lcs: str):
        self.lcs_map[(concept_a, concept_b)] = lcs
        self.lcs_map[(concept_b, concept_a)] = lcs

    def get_concepts_for_name(self, name: str) -> Set[str]:
        return self.name_to_concepts.get(name, set())

    def get_synonyms_for_concept(self, concept_id: str) -> Set[str]:
        return self.concept_to_names.get(concept_id, set())

    def get_lcs(self, concept_a: str, concept_b: str) -> str:
        if concept_a == concept_b:
            return concept_a
        return self.lcs_map.get((concept_a, concept_b), "ROOT")

    def get_shortest_path_distance(self, concept_a: str, concept_b: str) -> int:
        """Returns the shortest path edge distance between two concepts."""
        return abs(
            self.depths.get(concept_a, 0) -
            self.depths.get(concept_a, 0)
        )

    def get_concept_depth(self, concept_id: str) -> int:
        return self.depths.get(concept_id, 0)

    def get_subtree_leaves_count(self, concept_id: str) -> int:
        return self.leaves_count.get(concept_id, 1)

    def get_ancestors_count(self, concept_id: str) -> int:
        return self.ancestors_count.get(concept_id, 0)

    def get_subtree_node_count(self, concept_id: str) -> int:
        return self.subtree_nodes_count.get(concept_id, 1)

    def get_total_leaves_count(self) -> int:
        return self.total_leaves

    def get_total_concepts_count(self) -> int:
        return self.total_concepts

    def get_max_ontology_depth(self) -> int:
        return max(self.depths.values())


# =============================================================================
# 2. Edge Case Tests
# =============================================================================

class TestEdgeCases(unittest.TestCase):

    def test_unambiguous_name_returns_perfect_accuracy(self):
        graph = InMemoryOntologyGraph()
        graph.add_concept("C1", ["unique_term"])

        estimator = OntologyDifficultyEstimator(graph)
        accuracy = estimator.predict_accuracy("C1", "unique_term")

        self.assertEqual(accuracy, 1.0)

    def test_concept_without_synonyms_returns_default_difficulty(self):
        graph = InMemoryOntologyGraph()
        # C1 registered in ontology structure, but no name mapping
        graph.total_concepts = 10

        estimator = OntologyDifficultyEstimator(graph)
        result = estimator.compute_concept_ontology_difficulty("C1")

        self.assertEqual(result["predicted_accuracy"], 1.0)
        self.assertEqual(result["min_predicted_accuracy"], 1.0)

    def test_missing_target_concept_in_name_lookup_raises_value_error(self):
        graph = InMemoryOntologyGraph()
        graph.add_concept("C1", ["shared_term"])
        # C2 shares term, but lookup for C3 which doesn't own 'shared_term'
        graph.add_concept("C2", ["shared_term"])

        estimator = OntologyDifficultyEstimator(graph)

        with self.assertRaises(MisconfiguredConcept):
            estimator.predict_accuracy("C3", "shared_term")

    def test_invalid_similarity_metric_raises_value_error(self):
        graph = InMemoryOntologyGraph()
        config = EstimationConfig(sim_metric="invalid_metric")
        estimator = OntologyDifficultyEstimator(graph, config=config)

        with self.assertRaises(UnknownSimilarityMetric):
            estimator.get_sim_metric("C1", "C2")

    def test_double_counting_ic_guard_raises_value_error(self):
        graph = InMemoryOntologyGraph()
        graph.add_concept("C1", ["term_a"])

        config = EstimationConfig(sim_metric="lin", apply_extrinsic_ic_prior=True)
        estimator = OntologyDifficultyEstimator(graph, config=config)

        with self.assertRaises(MisconfiguredSimMetric):
            estimator.compute_concept_ontology_difficulty("C1")

    def test_identity_similarity_equals_one(self):
        graph = InMemoryOntologyGraph()
        graph.add_concept("C1", ["term"], depth=3, leaves=2, ancestors=1)
        graph.total_leaves = 10
        graph.total_concepts = 10

        estimator = OntologyDifficultyEstimator(graph)

        self.assertEqual(estimator.sim_wu_palmer("C1", "C1"), 1.0)
        self.assertEqual(estimator.sim_lin_intrinsic("C1", "C1"), 1.0)


# =============================================================================
# 3. Integration & Property-Based Tests over Dummy Ontologies
# =============================================================================

class TestDummyOntologies(unittest.TestCase):

    def test_uniform_ambiguity_power_zero(self):
        """
        When power=0, similarity is ignored, and effective_N = 1 + (N-1) = N.
        Accuracy for 4 competing concepts sharing a term should be exactly 1/4 = 0.25.
        """
        graph = InMemoryOntologyGraph()
        concepts = ["C1", "C2", "C3", "C4"]
        for c in concepts:
            graph.add_concept(c, ["ambiguous_name"])

        config = EstimationConfig(power=0.0)
        estimator = OntologyDifficultyEstimator(graph, config=config)

        acc = estimator.predict_accuracy("C1", "ambiguous_name")
        self.assertAlmostEqual(acc, 0.25, places=4)

    def test_power_scaling_behavior(self):
        """
        Test that increasing power reduces the effect of distant/dissimilar competitors.
        """
        graph = InMemoryOntologyGraph()
        graph.total_leaves = 100
        graph.total_concepts = 100

        # C1 is the target. C_near is structurally close. C_far is structurally distant.
        graph.add_concept("ROOT", [], depth=1, leaves=100, ancestors=0)
        graph.add_concept("PARENT", [], depth=2, leaves=10, ancestors=1)
        graph.add_concept("C1", ["term"], depth=3, leaves=2, ancestors=2)
        graph.add_concept("C_near", ["term"], depth=3, leaves=2, ancestors=2)
        graph.add_concept("C_far", ["term"], depth=2, leaves=50, ancestors=1)

        graph.set_lcs("C1", "C_near", "PARENT")
        graph.set_lcs("C1", "C_far", "ROOT")

        # Power = 1.0 baseline
        est_low_power = OntologyDifficultyEstimator(graph, EstimationConfig(power=1.0))
        acc_low = est_low_power.predict_accuracy("C1", "term")

        # Power = 5.0 (heavy penalization of lower similarity items)
        est_high_power = OntologyDifficultyEstimator(graph, EstimationConfig(power=5.0))
        acc_high = est_high_power.predict_accuracy("C1", "term")

        # Higher power filters out C_far, making effective_N smaller and predicted accuracy HIGHER
        self.assertGreater(acc_high, acc_low)

    def test_hierarchical_dag_sanchez_ic(self):
        """
        Test Sanchez IC monotonic decay from leaf to root in a small 3-level tree.
        Leaf concepts should have HIGHER IC than ancestor concepts.
        """
        graph = InMemoryOntologyGraph()
        graph.total_leaves = 4
        graph.total_concepts = 7

        # Root: covers 4 leaves, 0 ancestors
        graph.add_concept("ROOT", ["entity"], depth=1, leaves=4, ancestors=0)
        # Mid node: covers 2 leaves, 1 ancestor
        graph.add_concept("MID", ["organism"], depth=2, leaves=2, ancestors=1)
        # Leaf node: covers 1 leaf, 2 ancestors
        graph.add_concept("LEAF", ["bacterium"], depth=3, leaves=1, ancestors=2)

        config = EstimationConfig(ic_type="sanchez")
        estimator = OntologyDifficultyEstimator(graph, config=config)

        ic_root = estimator.get_intrinsic_ic("ROOT")
        ic_mid = estimator.get_intrinsic_ic("MID")
        ic_leaf = estimator.get_intrinsic_ic("LEAF")

        self.assertGreater(ic_leaf, ic_mid)
        self.assertGreater(ic_mid, ic_root)

    def test_multi_synonym_averaging_and_worst_case(self):
        """
        A concept with one easy name (unambiguous) and one hard name (shared with 3 others).
        Verify overall_accuracy is average, and worst_case_accuracy tracks the hard name.
        """
        graph = InMemoryOntologyGraph()
        graph.total_concepts = 10

        # C1 has 'easy_name' (unique) and 'hard_name' (shared with C2)
        graph.add_concept("C1", ["easy_name", "hard_name"])
        graph.add_concept("C2", ["hard_name"])

        config = EstimationConfig(power=0.0) # Power=0 simplifies math to exact fractions
        estimator = OntologyDifficultyEstimator(graph, config=config)

        res = estimator.compute_concept_ontology_difficulty("C1")

        # 'easy_name' acc = 1.0; 'hard_name' acc = 0.5 (shared 2 ways)
        expected_avg = (1.0 + 0.5) / 2.0  # 0.75
        expected_min = 0.5

        self.assertAlmostEqual(
            res["predicted_accuracy"], expected_avg, places=4)
        self.assertAlmostEqual(
            res["min_predicted_accuracy"], expected_min, places=4)
