"""Scorer v2: Anti-Keyword Stuffing, Depth Rubric (L0..L4), and Deterministic Ranking Engine.

Implements Blueprint v2.1 Section C2 S9 and Section C5:
- Score formula: weight * state_factor * depth_factor
- Anti-stuffing policy: T0 evidence (skill_list_item, summary_sentence, MENTION_ONLY, self_claim)
  is strictly capped at PARTIAL.
- Supporting atom cap: Maximum 3 supporting atoms evaluated per facet to prevent verbose CV bias.
- Band capping: Band A (<= 100), Band B (<= 74), Band C (<= 49), Band R (MANUAL_CHECK).
- Deterministic tie-breaking: Stable SHA-256 key independent of name/upload date.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from src.agents.schemas.matcher import FacetEvaluationResult
from src.domain.atoms import AtomKind, EvidenceAtom
from src.infrastructure.config import settings

STATE_VALUE: dict[str, float] = {
    "STRONG": 1.0,
    "PARTIAL": 0.5,
    "NOT_DEMONSTRATED": 0.0,
}
# UNKNOWN has no value and is excluded from numerator and denominator

DEFAULT_DEPTH_FACTORS: dict[str, float] = {
    "L0": 0.2,  # Mention only / unproven
    "L1": 0.4,  # Basic / guided
    "L2": 0.7,  # Autonomous practitioner
    "L3": 0.9,  # Specialist / advanced
    "L4": 1.0,  # Principal / architect
}

MAX_SUPPORTING_ATOMS_PER_FACET: int = 3

# A candidate whose score interval straddles this value may or may not be shortlisted.
SHORTLIST_CUTOFF: float = 70.0

BAND_CAP: dict[str, float] = {
    "A": 100.0,
    "B": 74.0,
    "C": 49.0,
}

BAND_ORDER: dict[str, int] = {
    "A": 0,
    "B": 1,
    "C": 2,
    "R": 3,
}

T0_KINDS = {
    AtomKind.SKILL_LIST_ITEM.value,
    AtomKind.SUMMARY_SENTENCE.value,
    "skill_list_item",
    "summary_sentence",
    "self_claim",
    "summary_claim",
    "MENTION_ONLY",
}


@dataclass
class ScoreResultV2:
    """Detailed score result produced by Scorer v2."""

    raw_score: float
    final_score: float
    band: str
    capped: bool
    recommendation: str
    color: str
    category_scores: dict[str, float] = field(default_factory=dict)
    must_have_not_strong: list[str] = field(default_factory=list)
    coverage: float = 1.0
    flags: list[str] = field(default_factory=list)
    scoring_version: str = "v2.2"
    depth_breakdown: dict[str, str] = field(default_factory=dict)
    effective_states: dict[str, str] = field(default_factory=dict)
    anti_stuffing_flags: list[str] = field(default_factory=list)
    score_lo: float = 0.0
    score_hi: float = 0.0
    interval_straddles_boundary: bool = False

    @property
    def category_breakdown(self) -> dict[str, float]:
        return self.category_scores


def tie_break_key(candidate_id: str, run_id: str = "eval") -> str:
    """Stable deterministic tie-breaker independent of candidate name or upload time."""
    return hashlib.sha256(f"{run_id}:{candidate_id}".encode()).hexdigest()


def cap_supporting_atoms(
    support_atoms: list[str],
    max_atoms: int = MAX_SUPPORTING_ATOMS_PER_FACET,
) -> tuple[list[str], bool]:
    """Caps the number of supporting atoms per facet to prevent verbose CV bias (Section C5).

    Returns:
        tuple of (capped_atoms, was_capped)
    """
    if len(support_atoms) > max_atoms:
        return support_atoms[:max_atoms], True
    return support_atoms, False


def is_t0_evidence(
    atom: EvidenceAtom | dict[str, Any] | str,
    atom_lookup: dict[str, Any] | None = None,
) -> bool:
    """Checks whether an evidence atom represents T0 (mention/summary/claim)."""
    if isinstance(atom, str):
        if atom_lookup and atom in atom_lookup:
            return is_t0_evidence(atom_lookup[atom], atom_lookup)
        return False

    kind = getattr(atom, "kind", None) or (atom.get("kind") if isinstance(atom, dict) else "")
    tier = getattr(atom, "tier", None) or (atom.get("tier") if isinstance(atom, dict) else "")
    flags = getattr(atom, "flags", None) or (atom.get("flags") if isinstance(atom, dict) else []) or []

    if kind in T0_KINDS or tier == "T0":
        return True
    return any(f in ("MENTION_ONLY", "CLAIM", "T0") for f in flags)


def score_v2(
    states: dict[str, str],
    requirement_set: dict[str, Any],
    facet_judgments: list[FacetEvaluationResult | dict[str, Any]] | None = None,
    atoms: list[EvidenceAtom | dict[str, Any]] | None = None,
    depth_levels: dict[str, str] | None = None,
    depth_factors_override: dict[str, float] | None = None,
    flags: list[str] | None = None,
    apply_depth: bool = True,
) -> ScoreResultV2:
    """Deterministic Scorer v2 with anti-keyword stuffing and depth weighting.

    Formula:
        Score = sum(weight * state_factor * depth_factor) / sum(weight) * 100

    Rules:
    - T0 Ceiling: If supporting evidence is solely T0 (mention_only, skill_list, summary),
      status is capped at PARTIAL and depth at L0/L1.
    - Atom Cap: Atoms per facet capped at 3.
    - Band capping: A (100), B (74), C (49), R (MANUAL_CHECK).
    - AGENT_DISAGREEMENT or MUST_HAVE UNKNOWN triggers Band R -> MANUAL_CHECK.
    """
    reqs = requirement_set.get("requirements", [])
    depth_map = dict(DEFAULT_DEPTH_FACTORS)
    if depth_factors_override:
        depth_map.update(depth_factors_override)

    # Build atom lookup
    atom_lookup: dict[str, Any] = {}
    if atoms:
        for a in atoms:
            akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else "")
            if akey:
                atom_lookup[str(akey)] = a

    # Map facet judgments by facet_key
    judgments_by_facet: dict[str, Any] = {}
    if facet_judgments:
        for fj in facet_judgments:
            j_dict = fj if isinstance(fj, dict) else fj.model_dump()
            fkey = j_dict.get("facet_key")
            if fkey:
                judgments_by_facet[fkey] = j_dict

    effective_states = dict(states)
    depth_breakdown: dict[str, str] = {}
    anti_stuffing_flags: list[str] = []
    score_flags: list[str] = list(flags or [])

    # Filter out prohibited or administrative requirements
    valid_reqs = []
    skipped_non_scorable = False
    for r in reqs:
        r_flags = r.get("lint_flags", [])
        if any(f.startswith("PROHIBITED_") or f.startswith("ADMIN_ONLY_") for f in r_flags):
            skipped_non_scorable = True
            continue
        valid_reqs.append(r)
    reqs = valid_reqs

    # Evaluate anti-stuffing and depth levels per requirement
    for r in reqs:
        rid = r["requirement_id"]
        req_facets = r.get("facets", [])
        st = effective_states.get(rid, "UNKNOWN")

        # Check facet judgments associated with this requirement
        req_supp_atoms: list[str] = []
        req_depths: list[str] = []

        if req_facets:
            for f in req_facets:
                fkey = f.get("facet_key") if isinstance(f, dict) else getattr(f, "facet_key", "")
                if fkey:
                    j = judgments_by_facet.get(str(fkey))
                    if isinstance(j, dict):
                        supp_atoms = j.get("support_atoms") or j.get("support_atom_ids") or []
                        # Cap supporting atoms at 3 per facet
                        capped_atoms, was_capped = cap_supporting_atoms([str(sa) for sa in supp_atoms])
                        if was_capped and "SUPPORTING_ATOMS_CAPPED" not in anti_stuffing_flags:
                            anti_stuffing_flags.append("SUPPORTING_ATOMS_CAPPED")
                        req_supp_atoms.extend(capped_atoms)

                        depth_val = j.get("depth_level")
                        if depth_val:
                            # enum members (DepthLevel.L2) and plain strings both end up as "L2"
                            req_depths.append(str(getattr(depth_val, "value", depth_val)).upper())

        # Check explicit depth_levels input
        if depth_levels and rid in depth_levels:
            req_depths.append(str(depth_levels[rid]).upper())

        # Determine effective depth for this requirement
        if req_depths:
            # Use max or most representative depth
            chosen_depth = max(req_depths, key=lambda d: depth_map.get(d, 0.5))
        elif depth_levels:
            chosen_depth = "L0"
        else:
            chosen_depth = "L4"  # Default full depth when depth evaluation is omitted

        # Apply T0 Anti-Stuffing Rule:
        # If all supporting atoms are T0 (skill_list_item, summary_sentence, mention_only)
        if req_supp_atoms and atom_lookup:
            all_t0 = all(is_t0_evidence(sa, atom_lookup) for sa in req_supp_atoms)
            if all_t0:
                if st == "STRONG":
                    effective_states[rid] = "PARTIAL"
                    anti_flag = f"T0_CAPPED_AT_PARTIAL:{rid}"
                    if anti_flag not in anti_stuffing_flags:
                        anti_stuffing_flags.append(anti_flag)
                # Cap depth level at L0 / L1
                if depth_map.get(chosen_depth, 1.0) > depth_map.get("L1", 0.4):
                    chosen_depth = "L0"
                    if "T0_DEPTH_FLOOR_ENFORCED" not in anti_stuffing_flags:
                        anti_stuffing_flags.append("T0_DEPTH_FLOOR_ENFORCED")

        depth_breakdown[rid] = chosen_depth

    # Compute numerical scores
    num = den = 0.0
    must_not_strong: list[str] = []
    must_unknown: list[str] = []
    items: list[tuple[str, float, float | None]] = []  # (category, weight, value or None when UNKNOWN)

    for r in reqs:
        rid = r["requirement_id"]
        w = float(r["weight"])
        st = effective_states.get(rid, "UNKNOWN")
        depth_level = depth_breakdown.get(rid, "L4")

        # Depth factor applies to both STRONG and PARTIAL (C5)
        # When depth evaluation is inactive (no depths passed), depth_factor=1.0
        depth_factor = depth_map.get(depth_level, 1.0) if (apply_depth and (facet_judgments or depth_levels)) else 1.0

        if r.get("importance") == "MUST_HAVE":
            if st == "UNKNOWN":
                must_unknown.append(rid)
            elif st != "STRONG":
                must_not_strong.append(rid)

        if st == "UNKNOWN":
            items.append((r.get("category", "GENERAL"), w, None))
            continue

        state_factor = STATE_VALUE.get(st, 0.0)
        item_val = w * state_factor * depth_factor
        items.append((r.get("category", "GENERAL"), w, state_factor * depth_factor))

        num += item_val
        den += w

    raw_cat_weights = requirement_set.get("category_weights") or {}

    def _aggregate(unknown_value: float | None) -> tuple[float, dict[str, float]]:
        """Weighted score; UNKNOWN is excluded (None), or counted as worst (0.0) / best (1.0) case."""
        c_num: dict[str, float] = {}
        c_den: dict[str, float] = {}
        for cat_name, weight, value in items:
            if value is None:
                if unknown_value is None:
                    continue
                value = unknown_value
            c_num[cat_name] = c_num.get(cat_name, 0.0) + weight * value
            c_den[cat_name] = c_den.get(cat_name, 0.0) + weight
        scores = {c: (100.0 * c_num[c] / c_den[c]) if c_den[c] else 0.0 for c in c_den}
        active = {cat: float(w) for cat, w in raw_cat_weights.items() if cat in c_den and c_den[cat] > 0}
        if active:
            total_active = sum(active.values())
            return round(sum(scores[c] * (w / total_active) for c, w in active.items()), 1), scores
        total_den = sum(c_den.values())
        return (round(100.0 * sum(c_num.values()) / total_den, 1) if total_den else 0.0), scores

    raw, cat_scores = _aggregate(None)
    raw_lo, _ = _aggregate(0.0)
    raw_hi, _ = _aggregate(1.0)

    cats = {c: round(score_val, 1) for c, score_val in cat_scores.items()}

    # Agent disagreement is a review signal. v2.1 forced every disagreement into Band R, which pushed
    # 17 of 19 real candidates (including a 92.1 scorer) to MANUAL_CHECK; it is now opt-in.
    has_agent_disagreement = "AGENT_DISAGREEMENT" in score_flags
    disagreement_forces_r = has_agent_disagreement and settings.AGENT_DISAGREEMENT_FORCES_BAND_R

    # Determine Band
    if must_unknown or disagreement_forces_r:
        band = "R"
    elif not must_not_strong:
        band = "A"
    elif len(must_not_strong) == 1:
        band = "B"
    else:
        band = "C"

    # Band Capping
    cap = BAND_CAP.get(band, 100.0)
    final = min(raw, cap)
    capped = final < raw

    # Recommendations
    if band == "R":
        rec = "MANUAL_CHECK"
    elif band == "A" and final >= SHORTLIST_CUTOFF:
        rec = "SHORTLIST"
    elif band in ("A", "B"):
        rec = "REVIEW"
    else:
        rec = "LOW_PRIORITY"

    total_weight = sum(float(r["weight"]) for r in reqs) or 1.0
    coverage = round(den / total_weight, 2)

    if skipped_non_scorable:
        score_flags.append("NON_SCORABLE_REQUIREMENT_SKIPPED")

    if coverage < 0.6:
        score_flags.append("LOW_COVERAGE")
        if rec == "SHORTLIST":
            rec = "MANUAL_CHECK"

    if has_agent_disagreement and not disagreement_forces_r:
        score_flags.append("AGENT_DISAGREEMENT_REVIEW")
        if rec == "SHORTLIST":
            rec = "REVIEW"  # a human confirms before this candidate is shortlisted

    # Score interval: UNKNOWN requirements as worst / best case, under the same band cap.
    score_lo = min(raw_lo, cap)
    score_hi = min(raw_hi, cap)
    straddles = score_lo < SHORTLIST_CUTOFF <= score_hi
    if straddles:
        score_flags.append("SCORE_INTERVAL_STRADDLES_SHORTLIST")

    # Combine flags
    combined_flags = sorted(list(set(score_flags + anti_stuffing_flags)))
    color = "green" if final >= 75.0 else ("yellow" if final >= 50.0 else "red")
    if band == "R":
        color = "gray"

    return ScoreResultV2(
        raw_score=raw,
        final_score=final,
        band=band,
        capped=capped,
        recommendation=rec,
        color=color,
        category_scores=cats,
        must_have_not_strong=must_not_strong,
        coverage=coverage,
        flags=combined_flags,
        scoring_version="v2.2",
        depth_breakdown=depth_breakdown,
        effective_states=effective_states,
        anti_stuffing_flags=anti_stuffing_flags,
        score_lo=score_lo,
        score_hi=score_hi,
        interval_straddles_boundary=straddles,
    )


def rank_v2(items: list[dict[str, Any]], run_id: str = "eval") -> list[dict[str, Any]]:
    """Stable deterministic ranking for Scorer v2.

    Sorting key:
    1. Band order (A: 0, B: 1, C: 2, R: 3)
    2. Final score descending (-final_score)
    3. Raw (uncapped) score descending: band caps (74 / 49) flatten many candidates to the same final score,
       and ordering them by hash instead of by how much evidence they have throws that information away
    4. Strong count descending (-strong_count)
    5. Deterministic SHA-256 tie-breaker key
    """

    def _extract_band(x: dict[str, Any]) -> str:
        res = x.get("result")
        if res is not None:
            b = getattr(res, "band", None) or (res.get("band") if isinstance(res, dict) else None)
            if b:
                return str(b)
        return str(x.get("band", "R"))

    def _extract_score(x: dict[str, Any]) -> float:
        res = x.get("result")
        if res is not None:
            s = getattr(res, "final_score", None) or (res.get("final_score") if isinstance(res, dict) else None)
            if s is not None:
                return float(s)
        return float(x.get("final_score", 0.0))

    def _extract_raw(x: dict[str, Any]) -> float:
        res = x.get("result")
        raw = getattr(res, "raw_score", None) if res is not None else None
        if raw is None and isinstance(res, dict):
            raw = res.get("raw_score")
        return float(raw if raw is not None else _extract_score(x))

    return sorted(
        items,
        key=lambda x: (
            BAND_ORDER.get(_extract_band(x), 99),
            -_extract_score(x),
            -_extract_raw(x),
            -x.get("strong_count", 0),
            tie_break_key(str(x.get("candidate_id") or x.get("cv_id") or ""), run_id),
        ),
    )
