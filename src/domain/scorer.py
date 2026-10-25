"""Deterministic scoring and ranking engine ported from reference_scorer.py."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

STATE_VALUE = {"STRONG": 1.0, "PARTIAL": 0.5, "NOT_DEMONSTRATED": 0.0}
# UNKNOWN has no value: excluded from numerator AND denominator.

BAND_CAP = {"A": 100.0, "B": 74.0, "C": 49.0}
BAND_ORDER = {"A": 0, "B": 1, "C": 2, "R": 3}  # R = needs manual check


@dataclass
class ScoreResult:
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

    @property
    def category_breakdown(self) -> dict[str, float]:
        return self.category_scores


def score(states: dict[str, str], requirement_set: dict[str, Any]) -> ScoreResult:
    reqs = requirement_set["requirements"]
    num = den = 0.0
    cat_num: dict[str, float] = {}
    cat_den: dict[str, float] = {}
    must_not_strong: list[str] = []
    must_unknown: list[str] = []
    skipped_non_scorable = False

    valid_reqs = []
    for r in reqs:
        flags = r.get("lint_flags", [])
        if any(f.startswith("PROHIBITED_") or f.startswith("ADMIN_ONLY_") for f in flags):
            skipped_non_scorable = True
            continue
        valid_reqs.append(r)
    reqs = valid_reqs

    for r in reqs:
        rid = r["requirement_id"]
        w = float(r["weight"])
        st = states.get(rid, "UNKNOWN")
        if r["importance"] == "MUST_HAVE":
            if st == "UNKNOWN":
                must_unknown.append(rid)
            elif st != "STRONG":
                must_not_strong.append(rid)
        if st == "UNKNOWN":
            continue
        v = STATE_VALUE[st]
        num += w * v
        den += w
        cat_num[r["category"]] = cat_num.get(r["category"], 0.0) + w * v
        cat_den[r["category"]] = cat_den.get(r["category"], 0.0) + w

    cat_scores = {c: (100.0 * cat_num[c] / cat_den[c]) if cat_den[c] else 0.0 for c in cat_den}

    # Two-layer normalization using category_weights if provided
    raw_cat_weights = requirement_set.get("category_weights") or {}
    active_weights = {cat: float(w) for cat, w in raw_cat_weights.items() if cat in cat_den and cat_den[cat] > 0}

    if active_weights:
        total_active_weight = sum(active_weights.values())
        raw_val = sum(cat_scores[c] * (w / total_active_weight) for c, w in active_weights.items())
        raw = round(raw_val, 1)
    else:
        raw = round(100.0 * num / den, 1) if den else 0.0

    cats = {c: round(score_val, 1) for c, score_val in cat_scores.items()}

    if must_unknown:
        band = "R"
    elif not must_not_strong:
        band = "A"
    elif len(must_not_strong) == 1:
        band = "B"
    else:
        band = "C"

    cap = BAND_CAP.get(band, 100.0)
    final = min(raw, cap)
    capped = final < raw

    if band == "R":
        rec = "MANUAL_CHECK"
    elif band == "A" and final >= 70:
        rec = "SHORTLIST"
    elif band in ("A", "B"):
        rec = "REVIEW"
    else:
        rec = "LOW_PRIORITY"

    total_weight = sum(float(r["weight"]) for r in reqs) or 1.0
    coverage = round(den / total_weight, 2)
    score_flags = []
    if skipped_non_scorable:
        score_flags.append("NON_SCORABLE_REQUIREMENT_SKIPPED")

    if coverage < 0.6:
        score_flags.append("LOW_COVERAGE")
        if rec == "SHORTLIST":
            rec = "MANUAL_CHECK"

    color = "green" if final >= 75 else ("yellow" if final >= 50 else "red")
    return ScoreResult(raw, final, band, capped, rec, color, cats, must_not_strong, coverage, score_flags)


def tie_break_key(candidate_id: str, run_id: str) -> str:
    """Stable deterministic tie-breaker independent of candidate name or upload time."""
    return hashlib.sha256(f"{run_id}:{candidate_id}".encode()).hexdigest()


def rank(items: list[dict[str, Any]], run_id: str = "eval") -> list[dict[str, Any]]:
    """items: [{'candidate_id': ..., 'result': ScoreResult, 'strong_count': int, ...}]"""
    return sorted(
        items,
        key=lambda x: (
            BAND_ORDER[x["result"].band],
            -x["result"].final_score,
            -x.get("strong_count", 0),
            tie_break_key(str(x.get("candidate_id") or x.get("cv_id")), run_id),
        ),
    )
