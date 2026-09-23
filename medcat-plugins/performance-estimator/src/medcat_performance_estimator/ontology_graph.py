from abc import ABC, abstractmethod

import networkx as nx
from medcat.cdb import CDB
from .common import ConceptInfo

from .utils import method_lru_cache as lru_cache


class AbstractOntologyGraph(ABC):
    """
    Interface for wrapping MedCAT's underlying SNOMED-CT/UMLS graph structure.
    Override these methods to hook into your graph representation (e.g.,
    NetworkX, custom DAG).
    """

    @abstractmethod
    def get_concept_info(self, concept_id: str) -> ConceptInfo:
        """Return the concept's overall information."""

    @abstractmethod
    def get_concept_preferred_name(self, concept_id: str) -> str:
        """Returns the concept's preferred name."""

    @abstractmethod
    def get_concepts_for_name(self, name: str) -> set[str]:
        """Returns all concept IDs that share this specific name/synonym."""

    @abstractmethod
    def get_synonyms_for_concept(self, concept_id: str) -> set[str]:
        """Returns all names/synonyms associated with a given concept ID."""

    @abstractmethod
    def get_shortest_path_distance(
        self, concept_a: str, concept_b: str
    ) -> int:
        """Returns the shortest path edge distance between two concepts."""

    @abstractmethod
    def get_lcs(self, concept_a: str, concept_b: str) -> str:
        """Returns the Least Common Subsumer for two concepts in the DAG."""

    @abstractmethod
    def get_concept_depth(self, concept_id: str) -> int:
        """Returns the depth of a concept from the root.

        Max depth is used if multiple paths exist."""

    @abstractmethod
    def get_max_ontology_depth(self) -> int:
        """Returns the maximum depth ($D$) of the ontology hierarchy."""

    @abstractmethod
    def get_subtree_node_count(self, concept_id: str) -> int:
        """Returns the count of all nodes subsumed by this concept."""

    @abstractmethod
    def get_subtree_leaves_count(self, concept_id: str) -> int:
        """Returns the count of leaf nodes subsumed by this concept."""

    @abstractmethod
    def get_ancestors_count(self, concept_id: str) -> int:
        """Returns the total number of ancestor concepts for this concept."""

    @abstractmethod
    def get_total_leaves_count(self) -> int:
        """Returns the total number of leaf nodes in the whole ontology."""

    @abstractmethod
    def get_total_concepts_count(self) -> int:
        """Returns the total number of concepts in the whole ontology."""


class SnomedGraph(AbstractOntologyGraph):

    def __init__(self, cdb: CDB) -> None:
        self.cdb = cdb
        self.pt2ch = self.cdb.addl_info['pt2ch']
        self.G: nx.DiGraph = nx.DiGraph()
        self.G.add_edges_from(
            (parent, child)
            for parent, children in self.pt2ch.items()
            for child in children
        )
        potential_roots = [cui for cui in self.G if self.G.in_degree(cui) == 0]
        if len(potential_roots) != 1:
            raise ValueError(
                f"Unable to find unique root. Potentials: {potential_roots}")
        self._root_concept = potential_roots[0]
        self._depths = self._compute_all_depths()

    def _compute_all_depths(self) -> dict[str, int]:
        depth = {self._root_concept: 0}
        for node in nx.topological_sort(self.G):
            if node not in depth:
                continue
            for child in self.G.successors(node):
                candidate = depth[node] + 1
                if candidate > depth.get(child, -1):
                    depth[child] = candidate
        return depth

    def get_concept_info(self, concept_id: str) -> ConceptInfo:
        synonyms = self.get_synonyms_for_concept(concept_id)
        return ConceptInfo(
            cui=concept_id,
            preferred_name=self.get_concept_preferred_name(concept_id),
            synonyms=sorted(synonyms),
        )

    def get_concept_preferred_name(self, concept_id: str) -> str:
        return self.cdb.get_name(concept_id)

    def get_concepts_for_name(self, name: str) -> set[str]:
        ni = self.cdb.name2info.get(name)
        if not ni:
            return set()
        return set(ni["per_cui_status"])

    def get_synonyms_for_concept(self, concept_id: str) -> set[str]:
        ci = self.cdb.cui2info.get(concept_id)
        if not ci:
            return set()
        return set(ci['names'])

    def get_shortest_path_distance(
        self, concept_a: str, concept_b: str
    ) -> int:
        common = self.get_lcs(concept_a, concept_b)
        if common in (concept_a, concept_b):
            # ensure correct direction
            other = concept_a if common == concept_b else concept_b
            return int(nx.shortest_path_length(self.G, common, other))
        return int(
            nx.shortest_path_length(self.G, common, concept_a) +
            nx.shortest_path_length(self.G, common, concept_b)
        )

    def get_lcs(self, concept_a: str, concept_b: str) -> str:
        ancestors_a = nx.ancestors(self.G, concept_a) | {concept_a}
        ancestors_b = nx.ancestors(self.G, concept_b) | {concept_b}

        common = ancestors_a & ancestors_b

        # get the deepest one, at least for now
        # TODO: maybe there's a better way?
        return max(common, key=self.get_concept_depth)

    def get_concept_depth(self, concept_id: str) -> int:
        return self._depths.get(concept_id, -1)

    @lru_cache(maxsize=1)
    def get_max_ontology_depth(self) -> int:
        return max(
            self.get_concept_depth(cui) for cui in self.G
        )

    @lru_cache(maxsize=10_000)
    def get_subtree_node_count(self, concept_id: str) -> int:
        return len(nx.descendants(self.G, concept_id))

    @lru_cache(maxsize=10_000)
    def _get_subtree_leaves(self, concept_id: str) -> set[str]:
        # doing this recursively we we don't
        # have to recalculate every time
        children = self.pt2ch.get(concept_id, set())
        leaves = set()
        if not children:
            # this is a leaf!
            return {concept_id}
        for ch in children:
            child_leaves = self._get_subtree_leaves(ch)
            leaves.update(child_leaves)
        return leaves

    @lru_cache(maxsize=10_000)
    def get_subtree_leaves_count(self, concept_id: str) -> int:
        return len(self._get_subtree_leaves(concept_id))

    @lru_cache(maxsize=10_000)
    def get_ancestors_count(self, concept_id: str) -> int:
        return len(nx.ancestors(self.G, concept_id))

    @lru_cache(maxsize=1)
    def get_total_leaves_count(self) -> int:
        # just take away the root concept
        return sum(1 for n in self.G if self.G.out_degree(n) == 0)

    def get_total_concepts_count(self) -> int:
        return len(self.cdb.cui2info)
