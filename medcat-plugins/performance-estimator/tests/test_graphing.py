from copy import deepcopy
from unittest import TestCase
from unittest.mock import MagicMock

from medcat_performance_estimator.graphing import SnomedGraph


class BaseGraphedTests(TestCase):
    PT2CH: dict[str, set[str]] = {
        "C": {"C1"}
    }

    def get_leaves(self):
        return {
            cui for children in self.PT2CH.values()
            for cui in children
            if cui not in self.PT2CH
        }

    def num_cuis(self):
        cuis = set(self.PT2CH)
        for vals in self.PT2CH.values():
            cuis.update(vals)
        return len(cuis)

    def setUp(self) -> None:
        self.cdb = MagicMock()
        self.cdb.addl_info = {
            "pt2ch": deepcopy(self.PT2CH)
        }
        self.graph = SnomedGraph(self.cdb)

    def test_root_has_depth_0(self):
        root_depth = self.graph.get_concept_depth(self.graph._root_concept)
        self.assertEqual(root_depth, 0)

    def test_all_cuis_in_graph(self):
        all_cuis = set(
            list(self.PT2CH.keys()) +
            [ch for vals in self.PT2CH.values() for ch in vals]
        )
        self.assertEqual(len(all_cuis), self.num_cuis())
        for cui in all_cuis:
            with self.subTest(f"CUI: {cui}"):
                self.assertIn(cui, self.graph.G)

    def test_graph_has_leaves(self):
        leaves =self.get_leaves()
        self.assertTrue(leaves)

    def test_leaves_count_as_leaf_in_subtree(self):
        for leaf in self.get_leaves():
            with self.subTest(leaf):
                self.assertEqual(self.graph.get_subtree_leaves_count(leaf), 1)

    def test_leaves_have_0_nodes_in_subtree(self):
        for leaf in self.get_leaves():
            with self.subTest(leaf):
                self.assertEqual(self.graph.get_subtree_node_count(leaf), 0)

    def test_root_has_all_leaves_in_subtree(self):
        root = self.graph._root_concept
        leaves = self.get_leaves()
        self.assertEqual(
            self.graph.get_subtree_leaves_count(root), len(leaves))


class SimpleGraphTests(BaseGraphedTests):
    ROOT = "C"
    PT2CH = {
        # ROOT is just C
        ROOT: {"C1", "C2"},
        "C1": {"C11", "C12"},
        "C11": {"C111", "C112"},
        "C12": {"C121"},
        "C2": {"C21", "C22", "C23"},
    }
    # 1 x root + 2 x l1 + 5 x l2 + 3 x l3
    NUM_CUIS = 11

    def get_expected_lcs(self, cui_a: str, cui_b: str) -> str:
        # NOTE: not actually traversing, but common part should be it
        if cui_a == cui_b:
            common = cui_a
        elif cui_a.startswith(cui_b):
            common = cui_b
        elif cui_b.startswith(cui_a):
            common = cui_a
        else:
            common_end = min(
                i for i in range(min(len(cui_a), len(cui_b)))
                if cui_a[i] != cui_b[i]
            )
            common = cui_a[:common_end]
        return common

    def expected_shortest_distance(self, cui_a: str, cui_b: str) -> int:
        if cui_a.startswith(cui_b):
            return len(cui_a) - len(cui_b)
        elif cui_b.startswith(cui_a):
            return len(cui_b) - len(cui_a)
        common_start = self.get_expected_lcs(cui_a, cui_b)
        return (
            # A to common
            self.expected_shortest_distance(cui_a, common_start) +
            # common to B
            self.expected_shortest_distance(common_start, cui_b)
        )

    def test_get_shortest_path_distance(self):
        for c1 in self.graph.G:
            for c2 in self.graph.G:
                with self.subTest(f"{c1} <-> {c2}"):
                    dist = self.graph.get_shortest_path_distance(c1, c2)
                    exp = self.expected_shortest_distance(c1, c2)
                    self.assertEqual(dist, exp)

    def test_get_lcs(self):
        for c1 in self.graph.G:
            for c2 in self.graph.G:
                with self.subTest(f"{c1} <-> {c2}"):
                    found_lcs = self.graph.get_lcs(c1, c2)
                    exp_lcs = self.get_expected_lcs(c1, c2)
                    self.assertEqual(found_lcs, exp_lcs)

    def test_get_concept_depth(self):
        for cui in self.graph.G:
            with self.subTest(cui):
                depth = self.graph.get_concept_depth(cui)
                exp = len(cui) - len(self.ROOT)
                self.assertEqual(depth, exp)

    def test_subtree_count_for_root(self):
        root = self.graph._root_concept
        nodes = self.graph.get_subtree_node_count(root)
        # without root?
        self.assertEqual(nodes, self.NUM_CUIS - 1)


class SimpleDiGraphTests(BaseGraphedTests):
    AMBIG = "C21"
    NORMAL = "C12"
    EXPECT_COMMON_PARENT = "C1"
    PT2CH = {
        "C": {EXPECT_COMMON_PARENT, "C2"},
        EXPECT_COMMON_PARENT: {"C11", NORMAL, AMBIG},
        "C2": {AMBIG, "C22"},
    }
    # child -> parent -> child
    AMBIG_TO_NORMAL_DIST = 2
    AMBIG_DEPTH = 2

    def assert_ambbig_normal_lcs(self, reverse: bool = False):
        ambig = self.AMBIG
        normal = self.NORMAL
        # (parent for both)
        if reverse:
            lcs = self.graph.get_lcs(normal, ambig)
        else:
            lcs = self.graph.get_lcs(ambig, normal)
        self.assertEqual(lcs, self.EXPECT_COMMON_PARENT)

    def test_lcs_ambig_normal(self):
        self.assert_ambbig_normal_lcs()

    def test_lcs_ambig_normal_reverse(self):
        self.assert_ambbig_normal_lcs(True)

    def test_get_shortest_path_distance(self):
        ambig, normal = self.AMBIG, self.NORMAL
        dist = self.graph.get_shortest_path_distance(ambig, normal)
        self.assertEqual(dist, self.AMBIG_TO_NORMAL_DIST)

    def test_get_concept_depth(self):
        ambig = self.AMBIG
        depth = self.graph.get_concept_depth(ambig)
        self.assertEqual(depth, self.AMBIG_DEPTH)


class ComplexDiGraphTests(SimpleDiGraphTests):
    # NOTE: here the distance is not consistent
    AMBIG = "C-AMB"
    NORMAL = "C12"
    EXPECT_COMMON_PARENT = "C1"
    PT2CH = {
        "C": {EXPECT_COMMON_PARENT, "C2"},
        EXPECT_COMMON_PARENT: {"C11", NORMAL, AMBIG},
        "C2": {"C22"},
        "C22": {AMBIG},
    }
    # child -> parent -> child
    AMBIG_TO_NORMAL_DIST = 2
    # max depth
    AMBIG_DEPTH = 3


if __name__ == "__main__":
    import unittest
    unittest.main()
