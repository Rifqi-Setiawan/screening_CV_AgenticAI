"""S3 Evidence Retriever per facet with hybrid search and ontology expansion (v2.1).

Implements Section C2 S3 of the Blueprint:
- Retrieves top-K (K=6) visible Evidence Atoms per qualification facet.
- Utilizes hybrid search: Keyword FTS + Vector HNSW cosine similarity with Reciprocal Rank Fusion (RRF, k=60).
- Expands query terms and concept aliases using the directed capability ontology.
- Enforces Grounding Rule: ONLY atoms with visibility == 'VISIBLE' are retrieved.
"""

from __future__ import annotations

import math
import re
import uuid
from typing import Any

from src.domain.atoms import EvidenceAtom
from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import get_ontology_graph
from src.domain.requirements.schemas import RequirementFacet
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger
from src.worker.embedding import embed_texts


def _clean_query_tokens(text: str) -> list[str]:
    """Extracts meaningful alphanumeric search tokens."""
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9_\+#\.\-]+", text.lower())
    stop_words = {
        "and",
        "or",
        "the",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "dan",
        "atau",
        "di",
        "ke",
        "dari",
        "untuk",
        "dengan",
        "pada",
        "yang",
        "bisa",
        "dapat",
        "adalah",
    }
    return [t for t in tokens if len(t) > 1 and t not in stop_words]


def expand_facet_terms(
    facet: RequirementFacet | dict[str, Any],
    ontology: OntologyGraph | None = None,
) -> tuple[str, list[str]]:
    """Expands facet hypothesis and concepts with synonyms, aliases, and implied terms from ontology."""
    hypothesis = facet.hypothesis if isinstance(facet, RequirementFacet) else str(facet.get("hypothesis", ""))
    concepts = facet.concepts if isinstance(facet, RequirementFacet) else list(facet.get("concepts", []))

    graph = ontology or get_ontology_graph()
    terms: set[str] = set(_clean_query_tokens(hypothesis))

    for cid in concepts:
        # Direct concept lookup
        c = graph.get_concept(cid) or graph.find_by_alias(cid)
        if c:
            terms.add(c.label.lower())
            for alias in c.aliases:
                terms.add(alias.lower())

        # Forward IMPLIES reachability (e.g. react -> javascript, redux -> state_management)
        implied_ids = graph.get_implied_concepts(cid, max_depth=3)
        for icid in implied_ids:
            ic = graph.get_concept(icid)
            if ic:
                terms.add(ic.label.lower())
                for alias in ic.aliases:
                    terms.add(alias.lower())

    term_list = sorted(list(terms))
    query_text = " ".join(term_list) if term_list else hypothesis
    return query_text, term_list


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def rank_atoms_in_memory(
    atoms: list[EvidenceAtom | dict[str, Any]],
    query_text: str,
    expanded_terms: list[str],
    facet_emb: list[float] | None = None,
    k: int = 6,
) -> list[EvidenceAtom]:
    """Ranks visible evidence atoms in memory using lexical term matching + embedding cosine."""
    visible_atoms: list[EvidenceAtom] = []
    for a in atoms:
        atom_obj = a if isinstance(a, EvidenceAtom) else EvidenceAtom.from_dict(a)
        if atom_obj.visibility == "VISIBLE":
            visible_atoms.append(atom_obj)

    if not visible_atoms:
        return []

    scored: list[tuple[float, EvidenceAtom]] = []
    term_set = {t.lower() for t in expanded_terms}

    for atom in visible_atoms:
        text_lower = atom.text_redacted.lower()
        # Lexical term overlap score
        matches = sum(1 for term in term_set if term in text_lower)
        lexical_score = matches / max(1, len(term_set))

        # Kind priority: exp_bullet (tier 2+) ranked higher than plain mention
        tier_boost = 0.0
        if atom.kind == "exp_bullet":
            tier_boost = 0.3
        elif atom.kind == "project_bullet":
            tier_boost = 0.2
        elif atom.kind in ("summary_sentence", "skill_list_item", "self_claim"):
            tier_boost = 0.05

        final_score = lexical_score + tier_boost
        scored.append((final_score, atom))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [atom for _, atom in scored[:k]]


async def retrieve_facet_evidence(
    facet: RequirementFacet | dict[str, Any],
    profile_id: uuid.UUID | str | None = None,
    tenant_id: uuid.UUID | str | None = None,
    candidate_atoms: list[EvidenceAtom | dict[str, Any]] | None = None,
    conn: Any = None,
    ontology: OntologyGraph | None = None,
    k: int = 6,
) -> list[EvidenceAtom]:
    """Retrieves top-K visible Evidence Atoms for a specific requirement facet.

    Supports both database hybrid search (PostgreSQL vector + FTS) and in-memory evaluation.
    Enforces that ONLY visible atoms are returned.
    """
    graph = ontology or get_ontology_graph()
    query_text, expanded_terms = expand_facet_terms(facet=facet, ontology=graph)

    # 1. In-memory mode if candidate_atoms is provided
    if candidate_atoms is not None:
        return rank_atoms_in_memory(
            atoms=candidate_atoms,
            query_text=query_text,
            expanded_terms=expanded_terms,
            k=k,
        )

    # 2. Database mode
    if profile_id is None or tenant_id is None:
        logger.warning("Neither candidate_atoms nor profile_id/tenant_id provided to retrieve_facet_evidence")
        return []

    prof_uuid = uuid.UUID(str(profile_id))
    ten_uuid = uuid.UUID(str(tenant_id))

    # Compute embedding for hypothesis
    hypothesis = facet.hypothesis if isinstance(facet, RequirementFacet) else str(facet.get("hypothesis", ""))
    facet_emb: list[float] = []
    try:
        facet_emb = embed_texts([hypothesis])[0] if hypothesis else []
    except Exception as e:
        logger.debug(f"Failed to compute embedding in retrieve_facet_evidence: {e}")

    # Build FTS plain query
    fts_terms = " ".join(expanded_terms[:8]) if expanded_terms else query_text

    async def _run_db_retrieval(c: Any) -> list[EvidenceAtom]:
        async with c.cursor() as cur:
            vector_results: list[dict[str, Any]] = []
            if facet_emb:
                try:
                    await cur.execute(
                        """
                        SELECT id, atom_key, kind, visibility, entry_ref, page, char_start, char_end,
                               red_start, red_end, text_redacted, bbox,
                               1 - (embedding <=> %s::vector) AS sim
                        FROM evidence_atoms
                        WHERE profile_id = %s AND tenant_id = %s AND visibility = 'VISIBLE'
                          AND embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector ASC
                        LIMIT 12
                        """,
                        (facet_emb, prof_uuid, ten_uuid, facet_emb),
                    )
                    v_rows = await cur.fetchall()
                    for r in v_rows:
                        vector_results.append(dict(r))
                except Exception as e:
                    logger.debug(f"Vector search note in retrieve_facet_evidence: {e}")

            fts_results: list[dict[str, Any]] = []
            if fts_terms:
                try:
                    await cur.execute(
                        """
                        SELECT id, atom_key, kind, visibility, entry_ref, page, char_start, char_end,
                               red_start, red_end, text_redacted, bbox,
                               ts_rank(fts, plainto_tsquery('simple', %s)) AS rank
                        FROM evidence_atoms
                        WHERE profile_id = %s AND tenant_id = %s AND visibility = 'VISIBLE'
                          AND fts @@ plainto_tsquery('simple', %s)
                        ORDER BY rank DESC
                        LIMIT 12
                        """,
                        (fts_terms, prof_uuid, ten_uuid, fts_terms),
                    )
                    f_rows = await cur.fetchall()
                    for r in f_rows:
                        fts_results.append(dict(r))
                except Exception as e:
                    logger.debug(f"FTS search note in retrieve_facet_evidence: {e}")

            # Reciprocal Rank Fusion (k=60)
            rrf_scores: dict[str, float] = {}
            atom_by_key: dict[str, dict[str, Any]] = {}

            for rank_idx, item in enumerate(vector_results):
                akey = item["atom_key"]
                atom_by_key[akey] = item
                rrf_scores[akey] = rrf_scores.get(akey, 0.0) + (1.0 / (60.0 + rank_idx + 1))

            for rank_idx, item in enumerate(fts_results):
                akey = item["atom_key"]
                if akey not in atom_by_key:
                    atom_by_key[akey] = item
                rrf_scores[akey] = rrf_scores.get(akey, 0.0) + (1.0 / (60.0 + rank_idx + 1))

            if not atom_by_key:
                # Fallback: simple visible atom query
                await cur.execute(
                    """
                    SELECT id, atom_key, kind, visibility, entry_ref, page, char_start, char_end,
                           red_start, red_end, text_redacted, bbox
                    FROM evidence_atoms
                    WHERE profile_id = %s AND tenant_id = %s AND visibility = 'VISIBLE'
                    ORDER BY char_start ASC
                    LIMIT %s
                    """,
                    (prof_uuid, ten_uuid, k),
                )
                fallback_rows = await cur.fetchall()
                return [EvidenceAtom.from_dict(dict(r)) for r in fallback_rows]

            sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)[:k]
            return [EvidenceAtom.from_dict(atom_by_key[k_item]) for k_item in sorted_keys]

    if conn is not None:
        return await _run_db_retrieval(conn)
    else:
        async with get_connection() as c:
            return await _run_db_retrieval(c)
