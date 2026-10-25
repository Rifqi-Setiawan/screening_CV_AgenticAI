"""Domain capability ontology module (v2.1).

Provides graph representation, YAML loader, PostgreSQL synchronization,
and directed recursive traversal for semantic relations (IMPLIES, PART_OF, etc.).
"""

from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import (
    compute_taxonomy_sha256,
    get_ontology_graph,
    load_taxonomy_from_yaml,
    query_traversal_cte,
    reset_ontology_cache,
    sync_ontology_to_db,
)
from src.domain.ontology.models import (
    Concept,
    ConceptEdge,
    OntologyVersion,
    RelationType,
    TraversalPath,
)

__all__ = [
    "Concept",
    "ConceptEdge",
    "OntologyGraph",
    "OntologyVersion",
    "RelationType",
    "TraversalPath",
    "compute_taxonomy_sha256",
    "get_ontology_graph",
    "load_taxonomy_from_yaml",
    "query_traversal_cte",
    "reset_ontology_cache",
    "sync_ontology_to_db",
]
