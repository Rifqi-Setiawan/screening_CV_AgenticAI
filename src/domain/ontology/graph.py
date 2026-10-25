"""In-memory ontology graph and directed traversal engine (v2.1)."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Sequence

from src.domain.ontology.models import Concept, ConceptEdge, RelationType, TraversalPath


class OntologyGraph:
    """Directed knowledge graph representing concepts and semantic relations."""

    def __init__(self, version: str = "v1"):
        self.version = version
        self.concepts: dict[str, Concept] = {}
        # Forward edges: src -> list[ConceptEdge]
        self.forward_edges: dict[str, list[ConceptEdge]] = defaultdict(list)
        # Reverse edges: dst -> list[ConceptEdge]
        self.reverse_edges: dict[str, list[ConceptEdge]] = defaultdict(list)
        # Fast alias lookup: alias_lowercase -> concept_id
        self.alias_to_id: dict[str, str] = {}

    def add_concept(self, concept: Concept) -> None:
        self.concepts[concept.id] = concept
        self.alias_to_id[concept.id.lower()] = concept.id
        self.alias_to_id[concept.label.lower()] = concept.id
        for alias in concept.aliases:
            self.alias_to_id[alias.lower().strip()] = concept.id

    def add_edge(self, edge: ConceptEdge) -> None:
        self.forward_edges[edge.src].append(edge)
        self.reverse_edges[edge.dst].append(edge)

    def get_concept(self, concept_id: str) -> Concept | None:
        return self.concepts.get(concept_id)

    def find_by_alias(self, text: str) -> Concept | None:
        cid = self.alias_to_id.get(text.lower().strip())
        if cid:
            return self.concepts.get(cid)
        return None

    def get_implied_concepts(self, concept_id: str, max_depth: int = 10) -> set[str]:
        """Returns all concept IDs reachable from concept_id via IMPLIES edges."""
        paths = self.traverse(
            start_concept=concept_id,
            relations=[RelationType.IMPLIES.value],
            direction="forward",
            max_depth=max_depth,
        )
        return {p.target for p in paths}

    def get_part_of_concepts(self, concept_id: str, max_depth: int = 10) -> set[str]:
        """Returns all concepts that concept_id is PART_OF (transitive containers)."""
        paths = self.traverse(
            start_concept=concept_id,
            relations=[RelationType.PART_OF.value],
            direction="forward",
            max_depth=max_depth,
        )
        return {p.target for p in paths}

    def traverse(
        self,
        start_concept: str,
        relations: Sequence[str | RelationType] | None = None,
        direction: str = "forward",
        max_depth: int = 10,
    ) -> list[TraversalPath]:
        """Traverses directed graph starting from start_concept.

        Args:
            start_concept: Source concept ID to traverse from.
            relations: Set or list of relation types to follow (e.g. ['IMPLIES']).
            direction: 'forward' (follows edge src -> dst) or 'reverse' (follows dst -> src).
            max_depth: Maximum path length.

        Returns:
            List of TraversalPath items with target, relation, depth, accumulated weight, and full path.
        """
        allowed_relations = None
        if relations:
            allowed_relations = {r.value if isinstance(r, RelationType) else str(r) for r in relations}

        results: list[TraversalPath] = []
        # Queue item: (current_id, depth, accumulated_weight, last_relation, path_list)
        queue: deque[tuple[str, int, float, str, list[str]]] = deque([(start_concept, 0, 1.0, "", [start_concept])])

        while queue:
            curr_id, depth, acc_weight, last_rel, path = queue.popleft()

            if depth > 0:
                results.append(
                    TraversalPath(
                        target=curr_id,
                        relation=last_rel,
                        depth=depth,
                        weight=acc_weight,
                        path=list(path),
                    )
                )

            if depth >= max_depth:
                continue

            edges = (
                self.forward_edges.get(curr_id, []) if direction == "forward" else self.reverse_edges.get(curr_id, [])
            )

            for edge in edges:
                rel_str = edge.relation.value if isinstance(edge.relation, RelationType) else str(edge.relation)
                if allowed_relations and rel_str not in allowed_relations:
                    continue

                next_id = edge.dst if direction == "forward" else edge.src
                if next_id in path:
                    # Prevent cycles along the current branch
                    continue

                new_weight = acc_weight * edge.weight
                new_path = path + [next_id]
                queue.append((next_id, depth + 1, new_weight, rel_str, new_path))

        return results
