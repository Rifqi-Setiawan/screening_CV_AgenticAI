"""Unit tests for capability ontology YAML loader, in-memory graph, and PostgreSQL recursive CTE (v2.1)."""

from __future__ import annotations

import pytest

from src.domain.ontology import (
    Concept,
    ConceptEdge,
    OntologyGraph,
    RelationType,
    load_taxonomy_from_yaml,
    query_traversal_cte,
    sync_ontology_to_db,
)
from src.infrastructure.database import get_connection


def test_load_taxonomy_from_yaml():
    """Verify loading taxonomy YAML files correctly populates concepts, edges, and sha256."""
    ont_ver, concepts, edges, graph = load_taxonomy_from_yaml()

    assert ont_ver.version.startswith("v2.1_")
    assert len(ont_ver.sha256) == 64
    assert len(concepts) > 50
    assert len(edges) > 0

    # Verify skill concepts exist
    py_concept = graph.get_concept("skill:python")
    assert py_concept is not None
    assert py_concept.label == "Python"
    assert "py" in py_concept.aliases

    # Verify alias lookup
    fastapi_concept = graph.find_by_alias("fast api")
    assert fastapi_concept is not None
    assert fastapi_concept.id == "skill:fastapi"


def test_ontology_graph_traversal_implies_and_part_of():
    """Verify in-memory directed traversal for IMPLIES and PART_OF relations."""
    graph = OntologyGraph(version="test_v1")

    # Setup concepts
    graph.add_concept(Concept("test_v1", "skill:react", "React", "framework", ["reactjs"]))
    graph.add_concept(Concept("test_v1", "skill:javascript", "JavaScript", "language", ["js"]))
    graph.add_concept(Concept("test_v1", "skill:web", "Web Development", "domain", []))

    graph.add_concept(Concept("test_v1", "skill:fastapi", "FastAPI", "framework", []))
    graph.add_concept(Concept("test_v1", "skill:python", "Python", "language", []))
    graph.add_concept(Concept("test_v1", "skill:backend", "Backend", "domain", []))

    # Add directed edges:
    # FastAPI -> Python (IMPLIES)
    # Python -> Backend (PART_OF)
    # React -> JavaScript (IMPLIES)
    # JavaScript -> Web (PART_OF)
    graph.add_edge(ConceptEdge("test_v1", "skill:fastapi", "skill:python", RelationType.IMPLIES, 1.0))
    graph.add_edge(ConceptEdge("test_v1", "skill:python", "skill:backend", RelationType.PART_OF, 1.0))
    graph.add_edge(ConceptEdge("test_v1", "skill:react", "skill:javascript", RelationType.IMPLIES, 1.0))
    graph.add_edge(ConceptEdge("test_v1", "skill:javascript", "skill:web", RelationType.PART_OF, 1.0))

    # 1. Test IMPLIES traversal
    implied_fastapi = graph.get_implied_concepts("skill:fastapi")
    assert implied_fastapi == {"skill:python"}

    implied_react = graph.get_implied_concepts("skill:react")
    assert implied_react == {"skill:javascript"}

    # 2. Test PART_OF traversal
    part_of_python = graph.get_part_of_concepts("skill:python")
    assert part_of_python == {"skill:backend"}

    # 3. Transitive IMPLIES chain
    graph.add_concept(Concept("test_v1", "skill:advanced_fastapi", "Adv FastAPI", "skill", []))
    graph.add_edge(ConceptEdge("test_v1", "skill:advanced_fastapi", "skill:fastapi", RelationType.IMPLIES, 1.0))

    transitive_implied = graph.get_implied_concepts("skill:advanced_fastapi")
    assert transitive_implied == {"skill:fastapi", "skill:python"}


def test_ontology_graph_cycle_prevention():
    """Verify that cycles in directed edges do not cause infinite recursion."""
    graph = OntologyGraph(version="test_v1")
    graph.add_concept(Concept("test_v1", "c_a", "A", "skill", []))
    graph.add_concept(Concept("test_v1", "c_b", "B", "skill", []))
    graph.add_concept(Concept("test_v1", "c_c", "C", "skill", []))

    # Cyclic edges: A -> B -> C -> A
    graph.add_edge(ConceptEdge("test_v1", "c_a", "c_b", RelationType.IMPLIES, 1.0))
    graph.add_edge(ConceptEdge("test_v1", "c_b", "c_c", RelationType.IMPLIES, 1.0))
    graph.add_edge(ConceptEdge("test_v1", "c_c", "c_a", RelationType.IMPLIES, 1.0))

    paths = graph.traverse("c_a", relations=[RelationType.IMPLIES], max_depth=10)
    targets = {p.target for p in paths}
    # Traversal should discover B and C without crashing or infinite-looping
    assert "c_b" in targets
    assert "c_c" in targets


@pytest.mark.asyncio
async def test_sync_ontology_and_recursive_cte_postgres():
    """Verify loading into PostgreSQL and running directed recursive CTE queries."""
    async with get_connection() as conn:
        test_version = "v2.1_test_cte"
        ont_ver, num_concepts, num_edges = await sync_ontology_to_db(
            conn=conn,
            version=test_version,
        )
        assert ont_ver.version == test_version
        assert num_concepts > 50
        assert num_edges > 0

        # Query recursive CTE for FastAPI implies Python
        results = await query_traversal_cte(
            conn=conn,
            version=test_version,
            start_concept="skill:fastapi",
            relation="IMPLIES",
            max_depth=5,
        )

        assert len(results) >= 1
        targets = [r["dst"] for r in results]
        assert "skill:python" in targets
