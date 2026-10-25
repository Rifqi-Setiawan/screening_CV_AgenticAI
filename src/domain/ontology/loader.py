"""Taxonomy YAML loader and PostgreSQL database synchronizer for capability ontology (v2.1)."""

from __future__ import annotations

import functools
import hashlib
from pathlib import Path
from typing import Any

import yaml

from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.models import (
    Concept,
    ConceptEdge,
    OntologyVersion,
    RelationType,
)
from src.infrastructure.config import settings
from src.infrastructure.logging import logger


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def compute_taxonomy_sha256(taxonomy_dir: Path) -> str:
    """Computes deterministic SHA256 checksum across all YAML files in taxonomy dir."""
    hasher = hashlib.sha256()
    yaml_files = sorted(taxonomy_dir.glob("*.yaml")) + sorted(taxonomy_dir.glob("*.yml"))
    for yf in yaml_files:
        hasher.update(yf.name.encode("utf-8"))
        hasher.update(yf.read_bytes())
    return hasher.hexdigest()


def load_taxonomy_from_yaml(
    taxonomy_dir: Path | str | None = None,
    version: str | None = None,
) -> tuple[OntologyVersion, list[Concept], list[ConceptEdge], OntologyGraph]:
    """Reads config/taxonomy/*.yaml and compiles concepts and directed edges."""
    tax_dir = Path(taxonomy_dir or settings.TAXONOMY_DIR)
    if not tax_dir.is_absolute():
        tax_dir = Path("/srv/hermes-control/services/cv-screening-agentic") / tax_dir

    if not tax_dir.exists():
        raise FileNotFoundError(f"Taxonomy directory not found at {tax_dir}")

    sha256_sum = compute_taxonomy_sha256(tax_dir)
    ver = version or f"v2.1_{sha256_sum[:8]}"

    ont_version = OntologyVersion(version=ver, sha256=sha256_sum)
    graph = OntologyGraph(version=ver)
    concepts: list[Concept] = []
    edges: list[ConceptEdge] = []

    def _register_concept(c: Concept) -> None:
        concepts.append(c)
        graph.add_concept(c)

    def _register_edge(e: ConceptEdge) -> None:
        edges.append(e)
        graph.add_edge(e)

    # 1. Parse skills.yaml
    skills_data = _load_yaml(tax_dir / "skills.yaml")
    for key, data in skills_data.items():
        if not isinstance(data, dict):
            continue
        label = data.get("label", key)
        kind = data.get("type", "skill")
        aliases = list(data.get("aliases", []))
        concept = Concept(
            version=ver,
            id=key,
            label=label,
            kind=kind,
            aliases=aliases,
        )
        _register_concept(concept)

        # Edges from broader (FastAPI -> Python IMPLIES)
        broader = data.get("broader")
        if broader:
            _register_edge(
                ConceptEdge(
                    version=ver,
                    src=key,
                    dst=broader,
                    relation=RelationType.IMPLIES,
                    weight=1.0,
                )
            )

        # Edges from part_of
        part_of = data.get("part_of")
        if part_of:
            _register_edge(
                ConceptEdge(
                    version=ver,
                    src=key,
                    dst=part_of,
                    relation=RelationType.PART_OF,
                    weight=1.0,
                )
            )

        # Edges from explicit implies list
        for imp in data.get("implies", []):
            _register_edge(
                ConceptEdge(
                    version=ver,
                    src=key,
                    dst=imp,
                    relation=RelationType.IMPLIES,
                    weight=1.0,
                )
            )

    # 2. Parse role_families.yaml
    roles_data = _load_yaml(tax_dir / "role_families.yaml")
    for role_name, data in roles_data.items():
        if isinstance(data, dict):
            titles = data.get("titles", [])
            domain_terms = data.get("domain_terms", [])
            related = data.get("related", [])
        elif isinstance(data, list):
            titles = data
            domain_terms = []
            related = []
        else:
            titles = []
            domain_terms = []
            related = []

        cid = f"role:{role_name}"
        aliases = list(set(titles + domain_terms))
        concept = Concept(
            version=ver,
            id=cid,
            label=role_name.title(),
            kind="role",
            aliases=aliases,
        )
        _register_concept(concept)

        # Also register bare role_name as alias/concept lookup
        if role_name not in graph.concepts:
            bare_concept = Concept(
                version=ver,
                id=role_name,
                label=role_name.title(),
                kind="role",
                aliases=aliases,
            )
            _register_concept(bare_concept)

        for rel in related:
            target_id = f"role:{rel}"
            # fullstack has related backend/frontend -> PARTIAL_OF
            if role_name == "fullstack":
                _register_edge(
                    ConceptEdge(
                        version=ver,
                        src=cid,
                        dst=target_id,
                        relation=RelationType.PARTIAL_OF,
                        weight=0.5,
                    )
                )
                _register_edge(
                    ConceptEdge(
                        version=ver,
                        src=target_id,
                        dst=cid,
                        relation=RelationType.PART_OF,
                        weight=0.5,
                    )
                )
            else:
                _register_edge(
                    ConceptEdge(
                        version=ver,
                        src=cid,
                        dst=target_id,
                        relation=RelationType.PARTIAL_OF,
                        weight=0.5,
                    )
                )

    # 3. Parse certifications.yaml
    certs_data = _load_yaml(tax_dir / "certifications.yaml")
    for key, data in certs_data.items():
        terms = data.get("terms", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        label = key.replace("cert:", "").replace("_", " ").title() + " Certification"
        concept = Concept(
            version=ver,
            id=key,
            label=label,
            kind="certification",
            aliases=terms,
        )
        _register_concept(concept)

    logger.info(f"Taxonomy loaded: version={ver}, concepts={len(concepts)}, edges={len(edges)}")
    return ont_version, concepts, edges, graph


@functools.lru_cache(maxsize=4)
def get_ontology_graph(
    taxonomy_dir: str | None = None,
    version: str | None = None,
) -> OntologyGraph:
    """Returns cached in-memory OntologyGraph."""
    _, _, _, graph = load_taxonomy_from_yaml(taxonomy_dir=taxonomy_dir, version=version)
    return graph


def reset_ontology_cache() -> None:
    get_ontology_graph.cache_clear()


async def sync_ontology_to_db(
    conn: Any,
    taxonomy_dir: Path | str | None = None,
    version: str | None = None,
) -> tuple[OntologyVersion, int, int]:
    """Synchronizes YAML taxonomy concepts and edges into PostgreSQL tables."""
    ont_ver, concepts, edges, _ = load_taxonomy_from_yaml(taxonomy_dir, version)

    async with conn.cursor() as cur:
        # 1. Upsert version
        await cur.execute(
            """
            INSERT INTO ontology_versions (version, sha256, loaded_at)
            VALUES (%s, %s, now())
            ON CONFLICT (version) DO UPDATE
                SET sha256 = EXCLUDED.sha256,
                    loaded_at = now()
            """,
            (ont_ver.version, ont_ver.sha256),
        )

        # 2. Upsert concepts
        for c in concepts:
            await cur.execute(
                """
                INSERT INTO concepts (version, id, label, kind, aliases)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (version, id) DO UPDATE
                    SET label = EXCLUDED.label,
                        kind = EXCLUDED.kind,
                        aliases = EXCLUDED.aliases
                """,
                (c.version, c.id, c.label, c.kind, c.aliases),
            )

        # 3. Upsert concept edges
        for e in edges:
            rel_str = e.relation.value if isinstance(e.relation, RelationType) else str(e.relation)
            await cur.execute(
                """
                INSERT INTO concept_edges (version, src, dst, relation, weight)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (version, src, dst, relation) DO UPDATE
                    SET weight = EXCLUDED.weight
                """,
                (e.version, e.src, e.dst, rel_str, e.weight),
            )

    return ont_ver, len(concepts), len(edges)


async def query_traversal_cte(
    conn: Any,
    version: str,
    start_concept: str,
    relation: str = "IMPLIES",
    max_depth: int = 10,
) -> list[dict[str, Any]]:
    """Directed graph traversal via PostgreSQL recursive CTE.

    Prevents cycles using an array path check and enforces max_depth.
    """
    query = """
    WITH RECURSIVE hierarchy AS (
        SELECT src, dst, relation, weight, 1 AS depth, ARRAY[src] AS path
        FROM concept_edges
        WHERE version = %(version)s AND src = %(start)s AND relation = %(rel)s
        UNION ALL
        SELECT e.src, e.dst, e.relation, e.weight * h.weight, h.depth + 1, h.path || e.src
        FROM concept_edges e
        JOIN hierarchy h ON e.src = h.dst AND e.version = %(version)s AND e.relation = h.relation
        WHERE h.depth < %(max_depth)s AND NOT (e.dst = ANY(h.path))
    )
    SELECT DISTINCT dst, relation, depth, weight
    FROM hierarchy
    ORDER BY depth, dst;
    """
    async with conn.cursor() as cur:
        await cur.execute(
            query,
            {
                "version": version,
                "start": start_concept,
                "rel": relation,
                "max_depth": max_depth,
            },
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
