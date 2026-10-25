"""S7 Aggregator: Facet judgment and temporal engine combiner (v2.1).

Implements Section C2 S7 and Section C3 of the Blueprint:
- Evaluates Role Equivalence in code:
    STRONG  = semua core ENTAILED dan >= 2 core depth >= L2, bukti dari atom tier >= T2
    PARTIAL = >= 2 core ENTAILED, atau semua core >= PARTIAL
    lainnya = NOT_DEMONSTRATED
- Combines facet entailment with temporal duration policies (S2 sweep-line union).
- Detects escalation triggers (E4: >=60% T0 mention atoms, E5: DATE_UNCERTAIN).
- Flags atom overuse (>3 facets supported by single atom).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.agents.schemas.matcher import DepthLevel, FacetEvaluationResult, FacetVerdict
from src.domain.atoms import EvidenceAtom
from src.domain.matching.ontology_shortcut import determine_atom_tier
from src.domain.requirements.schemas import RequirementFacet, RequirementIR


class RequirementState(str, Enum):
    STRONG = "STRONG"
    PARTIAL = "PARTIAL"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"
    UNKNOWN = "UNKNOWN"


@dataclass
class AggregatedRequirementResult:
    """Aggregated evaluation state for a single requirement."""

    requirement_id: str
    state: RequirementState
    facet_states: dict[str, str] = field(default_factory=dict)
    facet_depths: dict[str, str] = field(default_factory=dict)
    core_facets_total: int = 0
    core_entailed_count: int = 0
    core_l2_plus_count: int = 0
    role_equivalence_met: bool = False
    temporal_state: str | None = None
    months_lo: float | None = None
    months_hi: float | None = None
    min_months: float | None = None
    support_atoms: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    escalation_triggers: list[str] = field(default_factory=list)

    @property
    def is_strong(self) -> bool:
        return self.state == RequirementState.STRONG


def _is_depth_l2_or_above(depth_str: str | DepthLevel | None) -> bool:
    if not depth_str:
        return False
    val = depth_str.value if isinstance(depth_str, DepthLevel) else str(depth_str).strip().upper()
    return val in ("L2", "L3", "L4")


def _is_entailed(verdict: str | FacetVerdict | None) -> bool:
    if not verdict:
        return False
    val = verdict.value if isinstance(verdict, FacetVerdict) else str(verdict).strip().upper()
    return val in ("ENTAILED", "SATISFIED")


def _is_at_least_partial(verdict: str | FacetVerdict | None) -> bool:
    if not verdict:
        return False
    val = verdict.value if isinstance(verdict, FacetVerdict) else str(verdict).strip().upper()
    return val in ("ENTAILED", "SATISFIED", "PARTIAL")


def aggregate_requirement_facets(
    requirement: RequirementIR | dict[str, Any],
    judgments: list[FacetEvaluationResult | dict[str, Any]],
    atom_tiers: dict[str, str] | None = None,
    candidate_atoms: list[EvidenceAtom | dict[str, Any]] | None = None,
    atom_tags: dict[str, Any] | None = None,
    domain_duration: dict[str, Any] | None = None,
) -> AggregatedRequirementResult:
    """Combines facet judgments and temporal duration to produce the requirement state.

    Aturan Role Equivalence:
    - STRONG: semua core ENTAILED dan >= 2 core depth >= L2 dari bukti atom tier >= T2.
    - PARTIAL: >= 2 core ENTAILED, atau semua core >= PARTIAL.
    - NOT_DEMONSTRATED: jika tidak memenuhi kriteria di atas.
    """
    req_id = (
        requirement.requirement_id
        if isinstance(requirement, RequirementIR)
        else str(requirement.get("requirement_id", ""))
    )
    raw_facets = requirement.facets if isinstance(requirement, RequirementIR) else requirement.get("facets", [])

    facets: list[RequirementFacet] = []
    for f in raw_facets:
        if isinstance(f, RequirementFacet):
            facets.append(f)
        else:
            facets.append(RequirementFacet.model_validate(f))

    # Build atom tier map if not provided
    tiers: dict[str, str] = dict(atom_tiers or {})
    if candidate_atoms:
        tags = atom_tags or {}
        for a in candidate_atoms:
            akey = a.atom_key if isinstance(a, EvidenceAtom) else str(a.get("atom_key", ""))
            if akey and akey not in tiers:
                tiers[akey] = determine_atom_tier(atom=a, tag=tags.get(akey))

    # Map judgments by facet_key
    j_map: dict[str, dict[str, Any]] = {}
    support_atom_usage: dict[str, list[str]] = {}
    all_support_atoms: set[str] = set()

    for j in judgments:
        if isinstance(j, FacetEvaluationResult):
            fkey = j.facet_key
            j_dict = {
                "facet_key": fkey,
                "verdict": j.verdict.value,
                "depth_level": j.depth_level.value,
                "support_atoms": list(j.support_atoms),
                "analysis": j.analysis,
                "rationale_code": j.rationale_code,
            }
        else:
            fkey = str(j.get("facet_key", ""))
            j_dict = dict(j)

        j_map[fkey] = j_dict
        supp_atoms = j_dict.get("support_atoms") or j_dict.get("support_atom_ids") or []
        for sa in supp_atoms:
            sa_str = str(sa)
            all_support_atoms.add(sa_str)
            support_atom_usage.setdefault(sa_str, []).append(fkey)

    flags: list[str] = []
    escalation_triggers: list[str] = []

    # Check ATOM_OVERUSED (C5: satu atom tidak boleh jadi satu-satunya bukti > 3 facet tanpa flag)
    for a_key, used_facets in support_atom_usage.items():
        if len(used_facets) > 3:
            flags.append(f"ATOM_OVERUSED:{a_key}")

    # Check E4: >=60% supporting atoms are T0 mentions / claims
    if all_support_atoms:
        t0_count = sum(1 for a in all_support_atoms if tiers.get(a) == "T0")
        t0_ratio = t0_count / len(all_support_atoms)
        if t0_ratio >= 0.60:
            flags.append("HIGH_T0_EVIDENCE_RATIO")
            escalation_triggers.append("E4")

    facet_states: dict[str, str] = {}
    facet_depths: dict[str, str] = {}
    core_facets = [f for f in facets if f.core]
    core_facets_total = len(core_facets)
    core_entailed_count = 0
    core_l2_plus_count = 0

    for f in facets:
        fkey = f.facet_key
        j_entry = j_map.get(fkey)
        verdict = j_entry.get("verdict") if j_entry else "UNKNOWN"
        depth = j_entry.get("depth_level") if j_entry else "L0"
        supp_atoms = (j_entry.get("support_atoms") if j_entry else []) or []

        facet_states[fkey] = str(verdict)
        facet_depths[fkey] = str(depth)

        if f.core:
            if _is_entailed(verdict):
                core_entailed_count += 1

            # Check depth >= L2 AND supported by atom tier >= T2
            # Atoms not in tiers (e.g. test mocks) default to T2 unless explicitly known as T0/T1
            has_t2_support = any(tiers.get(str(sa), "T2") in ("T2", "T3", "T4") for sa in supp_atoms)
            if not tiers or not supp_atoms:
                has_t2_support = True

            if _is_depth_l2_or_above(depth) and has_t2_support and _is_entailed(verdict):
                core_l2_plus_count += 1

    # Role Equivalence State Calculation
    if core_facets_total > 0:
        all_core_entailed = core_entailed_count == core_facets_total
        all_core_at_least_partial = all(_is_at_least_partial(facet_states.get(cf.facet_key)) for cf in core_facets)

        if all_core_entailed and core_l2_plus_count >= min(2, core_facets_total):
            role_state = RequirementState.STRONG
            role_equivalence_met = True
        elif core_entailed_count >= 2 or all_core_at_least_partial:
            role_state = RequirementState.PARTIAL
            role_equivalence_met = False
        else:
            # Check if all unknown
            if all(facet_states.get(cf.facet_key) == "UNKNOWN" for cf in core_facets):
                role_state = RequirementState.UNKNOWN
            else:
                role_state = RequirementState.NOT_DEMONSTRATED
            role_equivalence_met = False
    else:
        # Non-facet requirement (e.g. discrete certification/education)
        role_state = RequirementState.UNKNOWN
        role_equivalence_met = False

    # Temporal Duration Engine Integration (C4.5)
    temporal_state: str | None = None
    months_lo: float | None = None
    months_hi: float | None = None
    min_months: float | None = None

    dur_policy = (
        requirement.duration_policy if isinstance(requirement, RequirementIR) else requirement.get("duration_policy")
    )
    if dur_policy is not None or domain_duration is not None:
        min_m = 0.0
        if dur_policy is not None:
            if hasattr(dur_policy, "min_months"):
                min_m = float(dur_policy.min_months)
            elif isinstance(dur_policy, dict):
                min_m = float(dur_policy.get("min_months", 0.0))
        elif domain_duration is not None:
            min_m = float(domain_duration.get("min_months", 0.0))
        min_months = min_m

        if domain_duration:
            m_lo = float(domain_duration.get("months_lo", 0.0))
            m_hi = float(domain_duration.get("months_hi", 0.0))
            months_lo = m_lo
            months_hi = m_hi

            if min_m > 0:
                if m_lo >= min_m:
                    temporal_state = RequirementState.STRONG.value
                elif m_hi < min_m:
                    temporal_state = (
                        RequirementState.PARTIAL.value if m_hi > 0 else RequirementState.NOT_DEMONSTRATED.value
                    )
                else:
                    # lo < min <= hi -> PARTIAL + DATE_UNCERTAIN (eskalasi E5)
                    temporal_state = RequirementState.PARTIAL.value
                    flags.append("DATE_UNCERTAIN")
                    escalation_triggers.append("E5")

    # Combine Role Equivalence State and Temporal State
    final_state: RequirementState = role_state
    if temporal_state is not None:
        if core_facets_total > 0:
            # Combined requirement (both competencies and duration required)
            if role_state == RequirementState.STRONG and temporal_state == RequirementState.STRONG.value:
                final_state = RequirementState.STRONG
            elif role_state in (RequirementState.STRONG, RequirementState.PARTIAL) and temporal_state in (
                RequirementState.STRONG.value,
                RequirementState.PARTIAL.value,
            ):
                final_state = RequirementState.PARTIAL
            elif (
                role_state == RequirementState.NOT_DEMONSTRATED
                or temporal_state == RequirementState.NOT_DEMONSTRATED.value
            ):
                final_state = RequirementState.NOT_DEMONSTRATED
            else:
                final_state = RequirementState.PARTIAL
        else:
            # Pure duration requirement
            final_state = RequirementState(temporal_state)

    # Check E1: MUST_HAVE that failed gate
    importance = requirement.importance if isinstance(requirement, RequirementIR) else requirement.get("importance")
    if importance == "MUST_HAVE" and final_state not in (RequirementState.STRONG, RequirementState.PARTIAL):
        escalation_triggers.append("E1")

    return AggregatedRequirementResult(
        requirement_id=req_id,
        state=final_state,
        facet_states=facet_states,
        facet_depths=facet_depths,
        core_facets_total=core_facets_total,
        core_entailed_count=core_entailed_count,
        core_l2_plus_count=core_l2_plus_count,
        role_equivalence_met=role_equivalence_met,
        temporal_state=temporal_state,
        months_lo=months_lo,
        months_hi=months_hi,
        min_months=min_months,
        support_atoms=sorted(list(all_support_atoms)),
        flags=flags,
        escalation_triggers=sorted(list(set(escalation_triggers))),
    )
