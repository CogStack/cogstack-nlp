import unittest
from unittest.mock import MagicMock
import numpy as np

from medcat_performance_estimator.training_fetcher import CDBTrainingFetcher
from medcat_performance_estimator.stage2_training_aware import (
    VectorSimilarityBaseline,
    TrainingAwareDifficultyEstimator,
)


class TestVectorSimilarityBaseline(unittest.TestCase):

    def test_baseline_initialization_and_normalization(self):
        # Create dummy concept vectors
        cui2vec = {
            "C1": np.array([1.0, 0.0]),
            "C2": np.array([0.0, 1.0]),
            "C3": np.array([0.707, 0.707]),
        }
        baseline = VectorSimilarityBaseline(cui2vec, sample_size=10, seed=42)

        # Verify mean and std are populated
        self.assertIsInstance(baseline.mean, float)
        self.assertIsInstance(baseline.std, float)
        self.assertGreater(baseline.std, 0.0)

        # Test normalized similarity returns a value between 0 and 1
        sim = baseline.normalized_similarity(cui2vec["C1"], cui2vec["C2"])
        self.assertTrue(0.0 <= sim <= 1.0)


class TestCDBTrainingFetcher(unittest.TestCase):

    def test_cdb_training_fetcher_delegation(self):
        mock_cdb = MagicMock()
        mock_cdb.cui2info = {
            "C001": {
                "count_train": 10,
                "context_vectors": {"vec1": np.array([1.0, 2.0])}
            }
        }
        mock_cdb.name2info = {
            "diabetes": {"count_train": 5}
        }
        mock_cdb.get_cui2count_train.return_value = {"C001": 10}
        mock_cdb.get_name2count_train.return_value = {"diabetes": 5}
        mock_cdb.get_cui2context_vectors.return_value = {"C001": {"vec1": np.array([1.0, 2.0])}}

        fetcher = CDBTrainingFetcher(mock_cdb)

        # Test counts and vectors for existing items
        self.assertEqual(fetcher.get_cui_train_count("C001"), 10)
        self.assertEqual(fetcher.get_name_train_count("diabetes"), 5)
        self.assertEqual(fetcher.get_cui_context_vector("C001")["vec1"].tolist(), [1.0, 2.0])

        # Test fallback for missing items
        self.assertEqual(fetcher.get_cui_train_count("UNKNOWN"), 0)
        self.assertEqual(fetcher.get_name_train_count("UNKNOWN"), 0)
        self.assertEqual(fetcher.get_cui_context_vector("UNKNOWN"), {})

        # Test bulk fetch delegations
        self.assertEqual(fetcher.get_cui2count_train(), {"C001": 10})
        self.assertEqual(fetcher.get_name2count_train(), {"diabetes": 5})
        self.assertEqual(list(fetcher.get_cui2context_vector().keys()), ["C001"])


class TestTrainingAwareDifficultyEstimator(unittest.TestCase):

    def setUp(self):
        # Mock Ontology Estimator and Config
        self.mock_ontology_estimator = MagicMock()
        self.mock_ontology_estimator.config.power = 2.0
        self.mock_ontology_estimator.config.similarity_floor = 0.0

        # Mock Ontology Graph
        self.mock_ontology = MagicMock()
        self.mock_ontology.get_concepts_for_name.return_value = {"C1", "C2"}
        self.mock_ontology.get_synonyms_for_concept.return_value = ["test_name"]
        self.mock_ontology_estimator.ontology = self.mock_ontology

        # Mock Training Fetcher
        self.mock_training = MagicMock()

        self.estimator = TrainingAwareDifficultyEstimator(
            ontology_estimator=self.mock_ontology_estimator,
            training=self.mock_training,
            context_vector_weights={"layer1": 1.0}
        )

    def test_zero_counts_reduce_to_ontology_estimator(self):
        """Verifies colleague's assertion: TrainingAwareDifficultyEstimator.predict_accuracy(c, n) 
        == ontology_estimator.predict_accuracy(c, n) when every count is 0.
        """
        target_concept = "C1"
        name = "test_name"

        # Setup zero counts
        self.mock_training.get_cui_train_count.return_value = 0
        cui2cv = {
            "C1": {"layer1": np.array([1.0, 0.0])},
            "C2": {"layer1": np.array([0.0, 1.0])}
        }
        self.mock_training.get_cui_context_vector = lambda cui: cui2cv.get(cui, {})
        self.mock_training.get_cui2context_vector.return_value = cui2cv

        # Mock ontology estimator similarity metric behavior
        ontology_sim = 0.8
        self.mock_ontology_estimator.sim_metric.return_value = ontology_sim
        self.mock_ontology_estimator.get_sim_metric.return_value = ontology_sim

        # Calculate expected result using the standard base formula:
        #   1.0 / (1.0 + (ontology_sim ** power) * mass)
        # With zero counts, mass evaluates to 1.0.
        expected_accuracy = 1.0 / (1.0 + (ontology_sim ** 2.0) * 1.0)

        predicted_accuracy = self.estimator.predict_accuracy(target_concept, name)

        # Assert that the training-aware estimator matches the base ontology math precisely when counts are 0
        self.assertAlmostEqual(predicted_accuracy, expected_accuracy, places=7)

    def test_compute_concept_training_difficulty(self):
        # Mock predict_accuracy behavior indirectly via synonyms
        self.mock_ontology.get_synonyms_for_concept.return_value = ["name1", "name2"]

        # Patch/mock predict_accuracy method on the instance to return fixed values
        self.estimator.predict_accuracy = MagicMock(side_effect=[0.5, 0.7])

        difficulty = self.estimator.compute_concept_training_difficulty("C1")['predicted_accuracy']
        self.assertEqual(difficulty, 0.6)


if __name__ == "__main__":
    unittest.main()
