import unittest
import numpy as np

from medcat.cdb import CDB
from medcat.config import Config
from medcat.cdb.concepts import get_new_cui_info, get_new_name_info
from medcat.utils.cdb_utils import (
    merge_cdb, _dedupe_preserve_order, get_all_ch,
    ch2pt_from_pt2ch, snomed_ct_concept_path
)


class CDBUtilsTests(unittest.TestCase):
    """Test cases for medcat.utils.cdb_utils module."""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures."""
        cls.config = Config()
        cls.config.general.log_level = 20  # INFO level

    def setUp(self):
        """Set up for each test."""
        self.cdb1 = self._create_test_cdb("cdb1")
        self.cdb2 = self._create_test_cdb("cdb2")

    def _create_test_cdb(self, name: str) -> CDB:
        """Create a test CDB with sample data."""
        cdb = CDB(self.config)

        if name == "cdb1":
            # CUI1 with training data
            cui_info1 = get_new_cui_info(
                cui="CUI1",
                preferred_name="Test Concept 1",
                names={"test concept 1", "tc1"},
                subnames={"test", "concept", "tc1"},
                type_ids={"T001"},
                description="First test concept",
                count_train=10,
                context_vectors={
                    "long": np.random.rand(300),
                    "short": np.random.rand(300)
                },
                average_confidence=0.8
            )
            cdb.cui2info["CUI1"] = cui_info1

            # CUI2 without training data
            cui_info2 = get_new_cui_info(
                cui="CUI2",
                preferred_name="Test Concept 2",
                names={"test concept 2", "tc2"},
                subnames={"test", "concept", "tc2"},
                type_ids={"T002"},
                description="Second test concept",
                count_train=0,
                context_vectors=None,
                average_confidence=0.0
            )
            cdb.cui2info["CUI2"] = cui_info2

            # Add name info
            name_info1 = get_new_name_info(
                name="test concept 1",
                per_cui_status={"CUI1": "A"},
                is_upper=False,
                count_train=5
            )
            cdb.name2info["test concept 1"] = name_info1

        elif name == "cdb2":
            # CUI1 with different training data (should be merged)
            cui_info1 = get_new_cui_info(
                cui="CUI1",
                preferred_name="Test Concept 1",
                names={"test concept 1", "tc1", "concept one"},
                subnames={"test", "concept", "tc1", "one"},
                type_ids={"T001", "T003"},
                description="First test concept (updated)",
                count_train=15,
                context_vectors={
                    "long": np.random.rand(300),
                    "medium": np.random.rand(300)
                },
                average_confidence=0.9
            )
            cdb.cui2info["CUI1"] = cui_info1

            # CUI3 (new concept)
            cui_info3 = get_new_cui_info(
                cui="CUI3",
                preferred_name="Test Concept 3",
                names={"test concept 3", "tc3"},
                subnames={"test", "concept", "tc3"},
                type_ids={"T003"},
                description="Third test concept",
                count_train=5,
                context_vectors={"short": np.random.rand(300)},
                average_confidence=0.7
            )
            cdb.cui2info["CUI3"] = cui_info3

            # Add name info
            name_info1 = get_new_name_info(
                name="test concept 1",
                per_cui_status={"CUI1": "P"},
                is_upper=False,
                count_train=8
            )
            cdb.name2info["test concept 1"] = name_info1

        # Add token counts
        cdb.token_counts["test"] = 10
        cdb.token_counts["concept"] = 15

        return cdb

    def _assert_cui_merge_results(self, merged_cdb, expected_results):
        """Helper method to assert merge results for multiple CUIs using subTest."""
        for cui, expected in expected_results.items():
            with self.subTest(cui=cui):
                self.assertIn(cui, merged_cdb.cui2info)
                cui_info = merged_cdb.cui2info[cui]

                # Test count_train
                if 'count_train' in expected:
                    self.assertEqual(cui_info['count_train'], expected['count_train'])

                # Test names
                for name in expected.get('names_should_contain', []):
                    self.assertIn(name, cui_info['names'])

                # Test type_ids
                for type_id in expected.get('type_ids_should_contain', []):
                    self.assertIn(type_id, cui_info['type_ids'])

                # Test context vectors
                if expected.get('should_have_context_vectors', True):
                    self.assertIsNotNone(cui_info['context_vectors'])
                    for context_type in expected.get('context_vectors_should_contain', []):
                        self.assertIn(context_type, cui_info['context_vectors'])
                else:
                    self.assertIsNone(cui_info['context_vectors'])

                for context_type in expected.get('context_vectors_should_not_contain', []):
                    if cui_info['context_vectors']:
                        self.assertNotIn(context_type, cui_info['context_vectors'])

    def test_merge_cdb_basic_merge(self):
        """Test basic CDB merging functionality."""
        merged_cdb = merge_cdb(
            self.cdb1, self.cdb2, overwrite_training=0, full_build=True
        )

        # Expected results for each CUI after merging
        expected_results = {
            "CUI1": {
                "count_train": 25,  # 10 + 15
                "names_should_contain": ["concept one"],
                "type_ids_should_contain": ["T003"],
                "context_vectors_should_contain": ["medium"],
                "context_vectors_should_not_contain": [],
                "should_have_context_vectors": True
            },
            "CUI2": {
                "count_train": 0,
                "names_should_contain": [],
                "type_ids_should_contain": [],
                "context_vectors_should_contain": [],
                "context_vectors_should_not_contain": [],
                "should_have_context_vectors": False
            },
            "CUI3": {
                "count_train": 5,
                "names_should_contain": [],
                "type_ids_should_contain": [],
                "context_vectors_should_contain": [],
                "context_vectors_should_not_contain": [],
                "should_have_context_vectors": True
            }
        }

        # Should have 3 concepts total
        self.assertEqual(len(merged_cdb.cui2info), 3)

        # Test each CUI with subTest for better error reporting
        self._assert_cui_merge_results(merged_cdb, expected_results)

    def test_merge_cdb_overwrite_training_cdb1(self):
        """Test CDB merging with overwrite_training=1 (prioritize cdb1)."""
        merged_cdb = merge_cdb(
            self.cdb1, self.cdb2, overwrite_training=1, full_build=True
        )

        # Expected results when prioritizing cdb1
        expected_results = {
            "CUI1": {
                "count_train": 10,  # Only cdb1's count
                "context_vectors_should_contain": ["long", "short"],
                "context_vectors_should_not_contain": ["medium"]
            },
            "CUI2": {
                "count_train": 0,
                "context_vectors_should_contain": [],
                "context_vectors_should_not_contain": [],
                "should_have_context_vectors": False
            },
            "CUI3": {
                "count_train": 5,  # From cdb2 (new concept)
                "context_vectors_should_contain": ["short"],
                "context_vectors_should_not_contain": []
            }
        }

        self._assert_cui_merge_results(merged_cdb, expected_results)

    def test_merge_cdb_overwrite_training_cdb2(self):
        """Test CDB merging with overwrite_training=2 (prioritize cdb2)."""
        merged_cdb = merge_cdb(
            self.cdb1, self.cdb2, overwrite_training=2, full_build=True
        )

        # Expected results when prioritizing cdb2
        expected_results = {
            "CUI1": {
                "count_train": 15,  # Only cdb2's count
                "context_vectors_should_contain": ["long", "medium"],
                "context_vectors_should_not_contain": ["short"]
            },
            "CUI2": {
                "count_train": 0,
                "context_vectors_should_contain": [],
                "context_vectors_should_not_contain": [],
                "should_have_context_vectors": False
            },
            "CUI3": {
                "count_train": 5,  # From cdb2 (new concept)
                "context_vectors_should_contain": ["short"],
                "context_vectors_should_not_contain": []
            }
        }

        self._assert_cui_merge_results(merged_cdb, expected_results)

    def test_merge_cdb_name_info_merging(self):
        """Test that name information is properly merged."""
        merged_cdb = merge_cdb(
            self.cdb1, self.cdb2, overwrite_training=0, full_build=True
        )

        # Name info should be merged
        name_info = merged_cdb.name2info["test concept 1"]
        self.assertEqual(name_info['count_train'], 13)  # 5 + 8
        # Should use cdb2's status (P) since it's more recent
        self.assertEqual(name_info['per_cui_status']['CUI1'], 'P')

    def test_merge_cdb_token_counts(self):
        """Test that token counts are properly merged."""
        merged_cdb = merge_cdb(
            self.cdb1, self.cdb2, overwrite_training=0, full_build=True
        )

        # Token counts should be merged
        self.assertEqual(merged_cdb.token_counts['test'], 20)  # 10 + 10
        self.assertEqual(merged_cdb.token_counts['concept'], 30)  # 15 + 15

    def test_merge_cdb_preserves_original_cdbs(self):
        """Test that original CDBs are not modified."""
        original_cdb1_cui1_count = self.cdb1.cui2info["CUI1"]['count_train']
        original_cdb2_cui1_count = self.cdb2.cui2info["CUI1"]['count_train']

        merged_cdb = merge_cdb(
            self.cdb1, self.cdb2, overwrite_training=0, full_build=True
        )

        # Original CDBs should be unchanged
        self.assertEqual(
            self.cdb1.cui2info["CUI1"]['count_train'], original_cdb1_cui1_count
        )
        self.assertEqual(
            self.cdb2.cui2info["CUI1"]['count_train'], original_cdb2_cui1_count
        )

    def test_merge_cdb_empty_cdb2(self):
        """Test merging with an empty cdb2."""
        empty_cdb = CDB(self.config)
        merged_cdb = merge_cdb(
            self.cdb1, empty_cdb, overwrite_training=0, full_build=True
        )

        # Should be identical to cdb1
        self.assertEqual(len(merged_cdb.cui2info), len(self.cdb1.cui2info))
        self.assertEqual(merged_cdb.cui2info["CUI1"]['count_train'], 10)

    def test_merge_cdb_empty_cdb1(self):
        """Test merging with an empty cdb1."""
        empty_cdb = CDB(self.config)
        merged_cdb = merge_cdb(
            empty_cdb, self.cdb2, overwrite_training=0, full_build=True
        )

        # Should be identical to cdb2
        self.assertEqual(len(merged_cdb.cui2info), len(self.cdb2.cui2info))
        self.assertEqual(merged_cdb.cui2info["CUI1"]['count_train'], 15)

    def test_dedupe_preserve_order(self):
        """Test the _dedupe_preserve_order function."""
        # Test with duplicates
        items = ["a", "b", "a", "c", "b", "d"]
        result = _dedupe_preserve_order(items)
        expected = ["a", "b", "c", "d"]
        self.assertEqual(result, expected)

        # Test with no duplicates
        items = ["a", "b", "c", "d"]
        result = _dedupe_preserve_order(items)
        self.assertEqual(result, items)

        # Test with empty list
        result = _dedupe_preserve_order([])
        self.assertEqual(result, [])

        # Test with single item
        result = _dedupe_preserve_order(["a"])
        self.assertEqual(result, ["a"])

    def test_get_all_ch(self):
        """Test the get_all_ch function."""
        # Create a CDB with parent-child relationships
        cdb = CDB(self.config)
        cdb.addl_info = {
            'pt2ch': {
                'parent1': ['child1', 'child2'],
                'child1': ['grandchild1'],
                'child2': ['grandchild2'],
                'grandchild1': []
            }
        }

        # Test getting all children of parent1
        all_children = get_all_ch('parent1', cdb)
        expected = ['parent1', 'child1', 'grandchild1', 'child2', 'grandchild2']
        self.assertEqual(all_children, expected)

        # Test getting children of a leaf node
        all_children = get_all_ch('grandchild1', cdb)
        self.assertEqual(all_children, ['grandchild1'])

        # Test getting children of a node with no children
        all_children = get_all_ch('nonexistent', cdb)
        self.assertEqual(all_children, ['nonexistent'])

    def test_ch2pt_from_pt2ch(self):
        """Test the ch2pt_from_pt2ch function."""
        # Create a CDB with parent-child relationships
        cdb = CDB(self.config)
        cdb.addl_info = {
            'pt2ch': {
                'parent1': ['child1', 'child2'],
                'parent2': ['child1', 'child3'],
                'child1': ['grandchild1']
            }
        }

        # Test default key
        ch2pt = ch2pt_from_pt2ch(cdb)
        expected = {
            'child1': ['parent1', 'parent2'],
            'child2': ['parent1'],
            'child3': ['parent2'],
            'grandchild1': ['child1']
        }
        self.assertEqual(ch2pt, expected)

        # Test with custom key
        cdb.addl_info['custom_pt2ch'] = {
            'root': ['branch1', 'branch2']
        }
        ch2pt = ch2pt_from_pt2ch(cdb, 'custom_pt2ch')
        expected = {
            'branch1': ['root'],
            'branch2': ['root']
        }
        self.assertEqual(ch2pt, expected)

    def test_snomed_ct_concept_path(self):
        """Test the snomed_ct_concept_path function."""
        # Create a CDB with SNOMED CT hierarchy
        cdb = CDB(self.config)
        cdb.addl_info = {
            'ch2pt': {
                '138875005': [],  # Root
                '123456789': ['138875005'],  # Child of root
                '987654321': ['123456789'],  # Grandchild
                '111222333': ['987654321']   # Great-grandchild
            }
        }

        # Add CUI info for the concepts
        cdb.cui2info = {
            '138875005': get_new_cui_info(
                cui='138875005', preferred_name='SNOMED CT Root'
            ),
            '123456789': get_new_cui_info(
                cui='123456789', preferred_name='Clinical Finding'
            ),
            '987654321': get_new_cui_info(cui='987654321', preferred_name='Disease'),
            '111222333': get_new_cui_info(cui='111222333', preferred_name='Diabetes')
        }

        # Test getting path for a concept
        result = snomed_ct_concept_path('111222333', cdb)

        # Should return a dict with node_path and links
        self.assertIn('node_path', result)
        self.assertIn('links', result)

        # The node_path should contain the root node structure
        self.assertEqual(result['node_path']['cui'], '138875005')
        self.assertEqual(result['node_path']['pretty_name'], 'SNOMED CT Root')

        # Test with non-existent concept
        result = snomed_ct_concept_path('nonexistent', cdb)
        self.assertEqual(result, {'node_path': {}, 'links': []})

    def test_snomed_ct_concept_path_custom_parent(self):
        """Test snomed_ct_concept_path with custom parent node."""
        # Create a CDB with hierarchy
        cdb = CDB(self.config)
        cdb.addl_info = {
            'ch2pt': {
                'root': [],
                'parent': ['root'],
                'child': ['parent']
            }
        }

        # Add CUI info
        cdb.cui2info = {
            'root': get_new_cui_info(cui='root', preferred_name='Root'),
            'parent': get_new_cui_info(cui='parent', preferred_name='Parent'),
            'child': get_new_cui_info(cui='child', preferred_name='Child')
        }

        # Test with custom parent
        result = snomed_ct_concept_path('child', cdb, parent_node='parent')

        # Should return a dict with node_path and links
        self.assertIn('node_path', result)
        self.assertIn('links', result)

        # The node_path should contain the custom parent node structure
        self.assertEqual(result['node_path']['cui'], 'parent')
        self.assertEqual(result['node_path']['pretty_name'], 'Parent')

    def test_merge_cdb_context_vector_weights(self):
        """Test that context vectors are properly weighted during merging."""
        # Create CDBs with known context vectors for testing
        cdb1 = CDB(self.config)
        cdb2 = CDB(self.config)

        # Create known vectors
        vec1_long = np.array([1.0, 2.0, 3.0] + [0.0] * 297)  # 300 dimensions
        vec2_long = np.array([4.0, 5.0, 6.0] + [0.0] * 297)

        cui_info1 = get_new_cui_info(
            cui="CUI1",
            preferred_name="Test",
            names={"test"},
            count_train=10,
            context_vectors={"long": vec1_long}
        )
        cdb1.cui2info["CUI1"] = cui_info1

        cui_info2 = get_new_cui_info(
            cui="CUI1",
            preferred_name="Test",
            names={"test"},
            count_train=20,
            context_vectors={"long": vec2_long}
        )
        cdb2.cui2info["CUI1"] = cui_info2

        # Merge with equal weights (overwrite_training=0)
        merged_cdb = merge_cdb(cdb1, cdb2, overwrite_training=0, full_build=True)

        # Check that the merged vector is properly weighted
        merged_vec = merged_cdb.cui2info["CUI1"]['context_vectors']['long']
        expected_vec = (10/30) * vec1_long + (20/30) * vec2_long

        np.testing.assert_array_almost_equal(merged_vec, expected_vec, decimal=10)

    def test_merge_cdb_tags_merging(self):
        """Test that tags are properly merged."""
        cdb1 = CDB(self.config)
        cdb2 = CDB(self.config)

        cui_info1 = get_new_cui_info(
            cui="CUI1",
            preferred_name="Test",
            names={"test"},
            tags=["tag1", "tag2"]
        )
        cdb1.cui2info["CUI1"] = cui_info1

        cui_info2 = get_new_cui_info(
            cui="CUI1",
            preferred_name="Test",
            names={"test"},
            tags=["tag3", "tag4"]
        )
        cdb2.cui2info["CUI1"] = cui_info2

        merged_cdb = merge_cdb(cdb1, cdb2, overwrite_training=0, full_build=True)

        # Tags should be merged
        merged_tags = merged_cdb.cui2info["CUI1"]['tags']
        expected_tags = ["tag1", "tag2", "tag3", "tag4"]
        self.assertEqual(merged_tags, expected_tags)


if __name__ == '__main__':
    unittest.main()
