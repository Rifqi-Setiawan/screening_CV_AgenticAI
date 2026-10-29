"""S4 Ontology Shortcut for fast, deterministic facet satisfaction (v2.1).

Implements Section C2 S4 of the Blueprint:
- Checks if any candidate Evidence Atom from tier >= T2 (exp_bullet USAGE, OWNERSHIP, or LEADERSHIP)
  has an ontology concept that equals or has an IMPLIES chain to a facet concept.
- If satisfied: immediately returns SATISFIED / ENTAILED with method='ontology' and depth_level='L2'
  without invoking expensive LLM calls.
"""

from __future__ import annotations

import re
from typing import Any

from src.agents.schemas.matcher import DepthLevel, FacetEvaluationResult, FacetVerdict
from src.domain.atoms import EvidenceAtom
from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import get_ontology_graph
from src.domain.requirements.schemas import RequirementFacet


def determine_atom_tier(
    atom: EvidenceAtom | dict[str, Any],
    tag: Any | None = None,
) -> str:
    """Determines evidence tier T0..T4 per Blueprint Section C5."""
    kind = atom.kind if isinstance(atom, EvidenceAtom) else atom.get("kind", "")
    vis = atom.visibility if isinstance(atom, EvidenceAtom) else atom.get("visibility", "VISIBLE")

    if vis != "VISIBLE":
        return "T0"

    # T0: mentions, self claims, skill lists
    if kind in ("skill_list_item", "summary_sentence", "self_claim"):
        return "T0"

    # Interview answers carry their own provenance: spoken and probed, not documentary. The recruiter's rating
    # decides the tier (STRONG -> T2, anything else -> T1); they never reach T3/T4 on a rating alone.
    if kind == "interview_answer":
        rating = atom.get("rating", "") if isinstance(atom, dict) else getattr(atom, "rating", "")
        return "T2" if str(rating).upper() == "STRONG" else "T1"

    evidence_type = None
    impact_quantified = False

    if tag is not None:
        if hasattr(tag, "evidence_type"):
            evidence_type = str(tag.evidence_type.value if hasattr(tag.evidence_type, "value") else tag.evidence_type)
        elif isinstance(tag, dict):
            evidence_type = tag.get("evidence_type")

        if hasattr(tag, "impact_quantified"):
            impact_quantified = bool(tag.impact_quantified)
        elif isinstance(tag, dict):
            impact_quantified = bool(tag.get("impact_quantified", False))

    if evidence_type == "MENTION_ONLY":
        return "T0"

    if kind == "project_bullet":
        return "T4" if impact_quantified else "T1"

    if kind == "exp_bullet":
        if impact_quantified:
            return "T4"
        if evidence_type in ("OWNERSHIP", "LEADERSHIP"):
            return "T3"
        return "T2"

    return "T0"


def _extract_concepts_from_atom(
    atom: EvidenceAtom | dict[str, Any],
    tag: Any | None,
    ontology: OntologyGraph,
) -> set[str]:
    """Extracts ontology concept IDs from atom tag or text matching."""
    concepts: set[str] = set()

    # 1. From tag
    if tag is not None:
        tag_concepts = getattr(tag, "concepts", None) or (tag.get("concepts") if isinstance(tag, dict) else None)
        if tag_concepts:
            for c in tag_concepts:
                c_str = str(c)
                if not c_str.startswith("unmapped:"):
                    concepts.add(c_str)

    # 2. Text keyword scan
    text = (atom.text_redacted if isinstance(atom, EvidenceAtom) else str(atom.get("text_redacted", ""))).lower()
    for alias, cid in ontology.alias_to_id.items():
        if len(alias) >= 3:
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, text):
                concepts.add(cid)

    return concepts


def check_facet_ontology_shortcut(
    facet: RequirementFacet | dict[str, Any],
    candidate_atoms: list[EvidenceAtom | dict[str, Any]],
    atom_tags: dict[str, Any] | None = None,
    ontology: OntologyGraph | None = None,
) -> FacetEvaluationResult | None:
    """Checks whether an atomic facet is directly satisfied via an ontology IMPLIES chain

    from a candidate Evidence Atom of tier >= T2.

    Returns:
        FacetEvaluationResult with verdict=ENTAILED and method='ontology' if satisfied, else None.
    """
    graph = ontology or get_ontology_graph()
    tags = atom_tags or {}

    facet_key = facet.facet_key if isinstance(facet, RequirementFacet) else str(facet.get("facet_key", ""))
    facet_concepts = facet.concepts if isinstance(facet, RequirementFacet) else list(facet.get("concepts", []))

    if not facet_concepts:
        return None

    for atom in candidate_atoms:
        atom_key = atom.atom_key if isinstance(atom, EvidenceAtom) else str(atom.get("atom_key", ""))
        tag = tags.get(atom_key)

        tier = determine_atom_tier(atom=atom, tag=tag)
        # S4 requires tier >= T2 (T2, T3, T4)
        if tier not in ("T2", "T3", "T4"):
            continue

        atom_concepts = _extract_concepts_from_atom(atom=atom, tag=tag, ontology=graph)
        if not atom_concepts:
            continue

        for ac in atom_concepts:
            # Direct match
            if ac in facet_concepts:
                analysis = f"Atom {atom_key} (tier {tier}) langsung memuaskan konsep facet {ac} via ontologi."
                return FacetEvaluationResult(
                    facet_key=facet_key,
                    analysis=analysis[:120],
                    verdict=FacetVerdict.ENTAILED,
                    support_atoms=[atom_key],
                    depth_level=DepthLevel.L2,
                    rationale_code="ONTOLOGY_SHORTCUT_EXACT",
                    needs_more_context=False,
                )

            # Transitive IMPLIES chain (e.g. skill:react IMPLIES skill:javascript)
            implied = graph.get_implied_concepts(ac, max_depth=5)
            for fc in facet_concepts:
                if fc in implied:
                    analysis = (
                        f"Atom {atom_key} (tier {tier}) berkonsep {ac} yang mengimplikasikan facet {fc} via ontologi."
                    )
                    return FacetEvaluationResult(
                        facet_key=facet_key,
                        analysis=analysis[:120],
                        verdict=FacetVerdict.ENTAILED,
                        support_atoms=[atom_key],
                        depth_level=DepthLevel.L2,
                        rationale_code="ONTOLOGY_SHORTCUT_IMPLIES",
                        needs_more_context=False,
                    )

    return None


def partition_facets_by_ontology_shortcut(
    facets: list[RequirementFacet | dict[str, Any]],
    candidate_atoms: list[EvidenceAtom | dict[str, Any]],
    atom_tags: dict[str, Any] | None = None,
    ontology: OntologyGraph | None = None,
) -> tuple[dict[str, FacetEvaluationResult], list[RequirementFacet]]:
    """Partitions incoming facets into those satisfied via S4 ontology shortcut

    and remaining facets that require LLM Matcher evaluation.
    """
    graph = ontology or get_ontology_graph()
    tags = atom_tags or {}

    satisfied: dict[str, FacetEvaluationResult] = {}
    remaining: list[RequirementFacet] = []

    for f in facets:
        f_obj = f if isinstance(f, RequirementFacet) else RequirementFacet.model_validate(f)
        shortcut_res = check_facet_ontology_shortcut(
            facet=f_obj,
            candidate_atoms=candidate_atoms,
            atom_tags=tags,
            ontology=graph,
        )
        if shortcut_res is not None:
            satisfied[f_obj.facet_key] = shortcut_res
        else:
            remaining.append(f_obj)

    return satisfied, remaining
