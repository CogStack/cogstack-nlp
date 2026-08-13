from abc import ABC, abstractmethod

import networkx as nx
from medcat.cdb import CDB


class AbstractOntologyGraph(ABC):
    """
    Interface for wrapping MedCAT's underlying SNOMED-CT/UMLS graph structure.
    Override these methods to hook into your graph representation (e.g., NetworkX, custom DAG).
    """

    @abstractmethod
    def get_concepts_for_name(self, name: str) -> set[str]:
        """Returns all concept IDs that share this specific name/synonym."""

    @abstractmethod
    def get_synonyms_for_concept(self, concept_id: str) -> set[str]:
        """Returns all names/synonyms associated with a given concept ID."""

    @abstractmethod
    def get_shortest_path_distance(self, concept_a: str, concept_b: str) -> int:
        """Returns the shortest path edge distance between two concepts."""

    @abstractmethod
    def get_lcs(self, concept_a: str, concept_b: str) -> str:
        """Returns the Least Common Subsumer (LCS) for two concepts in the DAG."""

    @abstractmethod
    def get_concept_depth(self, concept_id: str) -> int:
        """Returns the depth of a concept from the root (or max depth if multiple paths)."""

    @abstractmethod
    def get_max_ontology_depth(self) -> int:
        """Returns the maximum depth ($D$) of the ontology hierarchy."""

    @abstractmethod
    def get_subtree_leaves_count(self, concept_id: str) -> int:
        """Returns the count of leaf nodes subsumed by this concept (subgraph leaves)."""

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
        self._root_concept = next(
            cui for cui in self.G if self.G.in_degree(cui) == 0)
        self._max_ontology_depth = max(
            self.get_concept_depth(cui) for cui in self.G
        )

    def get_concepts_for_name(self, name: str) -> set[str]:
        """Returns all concept IDs that share this specific name/synonym."""
        ni = self.cdb.name2info.get(name)
        if not ni:
            return set()
        return set(ni["per_cui_status"])

    def get_synonyms_for_concept(self, concept_id: str) -> set[str]:
        """Returns all names/synonyms associated with a given concept ID."""
        ci = self.cdb.cui2info.get(concept_id)
        if not ci:
            return set()
        return set(ci['names'])

    def get_shortest_path_distance(self, concept_a: str, concept_b: str) -> int:
        """Returns the shortest path edge distance between two concepts."""
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
        """Returns the Least Common Subsumer (LCS) for two concepts in the DAG."""
        ancestors_a = nx.ancestors(self.G, concept_a) | {concept_a}
        ancestors_b = nx.ancestors(self.G, concept_b) | {concept_b}

        common = ancestors_a & ancestors_b

        # get the deepest one, at least for now
        # TODO: maybe there's a better way?
        return max(common, key=self.get_concept_depth)

    def get_concept_depth(self, concept_id: str) -> int:
        """Returns the depth of a concept from the root (or max depth if multiple paths)."""
        longest_path = max(
            (path for path in nx.all_simple_paths(
                self.G, self._root_concept, concept_id)),
            key=len
        )
        return len(longest_path) - 1

    def get_max_ontology_depth(self) -> int:
        """Returns the maximum depth ($D$) of the ontology hierarchy."""
        return self._max_ontology_depth

    def get_subtree_leaves_count(self, concept_id: str) -> int:
        """Returns the count of leaf nodes subsumed by this concept (subgraph leaves)."""
        descendants = nx.descendants(self.G, concept_id)

        leaves = {
            n for n in descendants
            if self.G.out_degree(n) == 0
        }

        if self.G.out_degree(concept_id) == 0:
            leaves.add(concept_id)

        return len(leaves)

    def get_ancestors_count(self, concept_id: str) -> int:
        """Returns the total number of ancestor concepts for this concept."""
        return len(nx.ancestors(self.G, concept_id))

    def get_total_leaves_count(self) -> int:
        """Returns the total number of leaf nodes in the whole ontology."""
        # just take away the root concept
        return self.get_total_concepts_count() - 1

    def get_total_concepts_count(self) -> int:
        """Returns the total number of concepts in the whole ontology."""
        return len(self.cdb.cui2info)
