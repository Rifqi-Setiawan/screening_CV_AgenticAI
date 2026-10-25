"""Matching domain package (v2.1).

Exports S3 Evidence Retriever, S4 Ontology Shortcut, and S7 Aggregator.
"""

from src.domain.matching.aggregator import (
    AggregatedRequirementResult,
    RequirementState,
    aggregate_requirement_facets,
)
from src.domain.matching.ontology_shortcut import (
    check_facet_ontology_shortcut,
    determine_atom_tier,
    partition_facets_by_ontology_shortcut,
)
from src.domain.matching.retriever import (
    expand_facet_terms,
    rank_atoms_in_memory,
    retrieve_facet_evidence,
)

__all__ = [
    "AggregatedRequirementResult",
    "RequirementState",
    "aggregate_requirement_facets",
    "check_facet_ontology_shortcut",
    "determine_atom_tier",
    "expand_facet_terms",
    "partition_facets_by_ontology_shortcut",
    "rank_atoms_in_memory",
    "retrieve_facet_evidence",
]
