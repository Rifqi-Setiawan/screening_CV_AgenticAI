"""Interview probe generator ranked by value of information (v2.2).

For each facet the system could not settle (UNKNOWN / PARTIAL / weak NOT_ENTAILED), estimate how much of the
candidate's achievable score depends on that facet and ask about the facets with the largest contribution first.
A facet's contribution is measured with every other unresolved facet assumed settled in the candidate's favour
(S_all) versus the same world where only this facet stays as it is now: requirements usually need several core
facets at once, so a facet's marginal effect with the others still open would always look like zero.
UNKNOWN is not a penalty here: it is the reason to ask.

Everything is deterministic and LLM-free. Questions come from the facet hypothesis, carry what a strong or
weak answer sounds like and a three-step follow-up ladder, and are screened against a protected-topic
blocklist. Recruiters approve probes before use; every candidate gets the same probe budget. After the
interview the recruiter rates each answer and `apply_interview_answers` re-scores the candidate in code,
keeping the original result intact.
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from src.agents.schemas.matcher import FacetEvaluationResult
from src.domain.matching.aggregator import aggregate_requirement_facets
from src.domain.protected_attributes import scrub_protected_attributes
from src.domain.requirements.facet_narrowing import facet_signature
from src.domain.requirements.schemas import RequirementFacet
from src.domain.scoring.scorer_v2 import SHORTLIST_CUTOFF, score_v2
from src.infrastructure.config import settings

DEFAULT_BUDGET = 5

# Probability that a candidate would give a strong answer, by current verdict (prior for the VOI estimate).
STRONG_ANSWER_PRIOR = {"UNKNOWN": 0.5, "PARTIAL": 0.5, "NOT_ENTAILED": 0.2, "CONTRADICTED": 0.1, "ENTAILED": 0.8}


def _uncertainty_factor(p: float) -> float:
    """1.0 when the answer is a coin flip, lower when the outcome is already fairly predictable."""
    return 1.0 - 0.5 * abs(2.0 * p - 1.0)


RATING_TO_JUDGMENT = {
    "STRONG": ("ENTAILED", "L2"),
    "ADEQUATE": ("PARTIAL", "L1"),
    "WEAK": ("NOT_ENTAILED", "L0"),
}

# Topics an interviewer must never probe, regardless of the facet text.
BLOCKED_TOPICS = (
    "hamil",
    "kehamilan",
    "anak",
    "menikah",
    "pernikahan",
    "pasangan",
    "suami",
    "istri",
    "orang tua",
    "keluarga",
    "agama",
    "ibadah",
    "etnis",
    "suku",
    "ras",
    "partai",
    "politik",
    "disabilitas",
    "penyakit",
    "kesehatan",
    "usia",
    "umur",
    "tahun lahir",
    "orientasi",
    "gender",
    "jenis kelamin",
    "pregnan",
    "marital",
    "religion",
    "ethnic",
    "disabilit",
    "age ",
    "children",
)


@dataclass
class Probe:
    probe_id: str
    candidate_id: str
    facet_key: str
    requirement_ids: list[str]
    hypothesis: str
    current_verdict: str
    target_atom_ids: list[str]
    voi: float
    score_now: float
    score_if_all_resolved: float
    score_without_this: float
    crosses_boundary: bool
    why: str
    question: str
    listen_for_strong: list[str]
    listen_for_weak: list[str]
    follow_ups: list[str]
    status: str = "PENDING_APPROVAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterviewAnswer:
    facet_key: str
    rating: str  # STRONG | ADEQUATE | WEAK
    answer_text: str = ""
    probe_id: str | None = None
    depth: str | None = None  # recruiter may override the default depth for the rating
    recorded_by: str | None = None


@dataclass
class RescoreResult:
    before: dict[str, Any]
    after: dict[str, Any]
    requirement_states_before: dict[str, str]
    requirement_states_after: dict[str, str]
    interview_atoms: list[dict[str, Any]] = field(default_factory=list)
    adjusted_facets: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------------------------- scoring
def _facet_dict(f: Any) -> dict[str, Any]:
    return f.model_dump() if isinstance(f, RequirementFacet) else dict(f)


def _verdict(j: dict[str, Any]) -> str:
    v = j.get("verdict", "UNKNOWN")
    return str(getattr(v, "value", v)).split(".")[-1].upper()


def _norm_judgment(j: Any) -> dict[str, Any]:
    d = j.model_dump() if hasattr(j, "model_dump") else dict(j)
    d["verdict"] = _verdict(d)
    d["depth_level"] = str(getattr(d.get("depth_level"), "value", d.get("depth_level") or "L0")).split(".")[-1]
    d["support_atoms"] = list(d.get("support_atoms") or d.get("support_atom_ids") or [])
    return d


def _duration_for(req: dict[str, Any], durations: list[dict[str, Any]]) -> dict[str, Any] | None:
    policy = req.get("duration_policy")
    domains = req.get("target_domains") or []
    if policy is None and not domains:
        return None
    wanted = domains[0] if domains else "general"
    min_months = float((policy or {}).get("min_months", 0.0)) if isinstance(policy, dict) else 0.0
    for d in durations or []:
        if d.get("domain") == wanted:
            return {
                "domain": wanted,
                "months_lo": float(d.get("months_lo", 0.0)),
                "months_hi": float(d.get("months_hi", 0.0)),
                "min_months": min_months,
            }
    return {"domain": wanted, "months_lo": 0.0, "months_hi": 0.0, "min_months": min_months}


def rescore(
    req_set: dict[str, Any],
    judgments: list[Any],
    durations: list[dict[str, Any]] | None = None,
    flags: list[str] | None = None,
) -> tuple[Any, dict[str, str]]:
    """Aggregate every requirement from facet judgments and score it with Scorer v2 (pure, no LLM)."""
    norm = [_norm_judgment(j) for j in judgments]
    by_key = {j["facet_key"]: j for j in norm}
    states: dict[str, str] = {}
    for req in req_set.get("requirements", []):
        facets = [_facet_dict(f) for f in req.get("facets") or []]
        req_view = dict(req, facets=facets)
        req_judgments: list[FacetEvaluationResult | dict[str, Any]] = [
            by_key[f["facet_key"]] for f in facets if f["facet_key"] in by_key
        ]
        agg = aggregate_requirement_facets(
            requirement=req_view,
            judgments=req_judgments,
            domain_duration=_duration_for(req, durations or []),
        )
        states[req["requirement_id"]] = agg.state.value
    all_judgments: list[FacetEvaluationResult | dict[str, Any]] = list(norm)
    result = score_v2(
        states=states,
        requirement_set=req_set,
        facet_judgments=all_judgments,
        flags=list(flags or []),
        apply_depth=settings.SCORER_DEPTH_FACTORS_ENABLED,
    )
    return result, states


def _with_facet(
    judgments: list[dict[str, Any]], facet_key: str, verdict: str, depth: str, support: list[str]
) -> list[dict[str, Any]]:
    out = [dict(j) for j in judgments if j["facet_key"] != facet_key]
    out.append(
        {
            "facet_key": facet_key,
            "verdict": verdict,
            "depth_level": depth,
            "support_atoms": support,
            "analysis": "interview",
            "method": "interview",
        }
    )
    return out


# --------------------------------------------------------------------------------------------- probes
def _importance_factor(req: dict[str, Any], facet: dict[str, Any]) -> float:
    base = 1.0 if req.get("importance") == "MUST_HAVE" else 0.6
    return base * (1.0 if facet.get("core", True) else 0.8)


def _template(hypothesis: str) -> dict[str, Any]:
    h = hypothesis.strip().rstrip(".")
    return {
        "question": (
            f"Ceritakan satu pekerjaan atau proyek nyata di mana Anda {h}. "
            "Apa peran pribadi Anda (bukan tim), keputusan teknis utama yang Anda ambil, dan hasil terukurnya?"
        ),
        "strong": [
            "menyebut peran dan keputusan pribadi, bukan hanya 'kami'",
            "menyebut sistem, teknologi, dan skala yang spesifik",
            "ada angka dengan pembanding (sebelum/sesudah) atau dampak yang bisa diverifikasi",
            "menjelaskan alternatif yang dipertimbangkan dan alasan memilih",
        ],
        "weak": [
            "jawaban berupa definisi umum atau daftar teknologi tanpa kasus nyata",
            "tidak bisa memisahkan kontribusi pribadi dari kontribusi tim",
            "tidak ada angka, skala, maupun hasil",
            "tidak mampu menjelaskan kegagalan atau trade-off",
        ],
        "follow_ups": [
            "Seberapa besar skalanya (pengguna, data, transaksi) dan berapa lama Anda menanganinya?",
            "Alternatif apa yang Anda pertimbangkan, dan mengapa memilih pendekatan itu?",
            "Apa yang pernah gagal atau berjalan buruk, dan bagaimana Anda memperbaikinya?",
        ],
    }


def blocked_terms_in(text: str) -> list[str]:
    lowered = f" {text.lower()} "
    hits = [t for t in BLOCKED_TOPICS if re.search(r"(?<![a-z])" + re.escape(t.strip()), lowered)]
    _, categories = scrub_protected_attributes(text)
    return sorted(set(hits) | set(categories))


def validate_probe(probe: Probe) -> list[str]:
    """Protected topics found in the probe text (empty list = acceptable)."""
    return blocked_terms_in(
        " ".join([probe.question, *probe.follow_ups, *probe.listen_for_strong, *probe.listen_for_weak])
    )


def build_probes(
    req_set: dict[str, Any],
    judgments: list[Any],
    candidate_id: str,
    durations: list[dict[str, Any]] | None = None,
    flags: list[str] | None = None,
    budget: int = DEFAULT_BUDGET,
    cutoff: float = SHORTLIST_CUTOFF,
) -> list[Probe]:
    """Probes for the facets with the largest expected score/band swing, most valuable first."""
    norm = [_norm_judgment(j) for j in judgments]
    by_key = {j["facet_key"]: j for j in norm}
    now, _ = rescore(req_set, norm, durations, flags)

    # distinct facets, with the requirements that use each
    facets: dict[tuple, dict[str, Any]] = {}
    for req in req_set.get("requirements", []):
        for f in req.get("facets") or []:
            fd = _facet_dict(f)
            entry = facets.setdefault(facet_signature(fd), {"facet": fd, "reqs": []})
            entry["reqs"].append(req)

    # S_all: every unresolved facet settled in the candidate's favour.
    unresolved = [
        e["facet"]["facet_key"]
        for e in facets.values()
        if not (
            _verdict(by_key.get(e["facet"]["facet_key"], {"verdict": "UNKNOWN"})) == "ENTAILED"
            and by_key.get(e["facet"]["facet_key"], {}).get("depth_level", "L0") in ("L2", "L3", "L4")
        )
    ]
    all_resolved = list(norm)
    for fk in unresolved:
        all_resolved = _with_facet(all_resolved, fk, "ENTAILED", "L2", ["INTERVIEW"])
    best_all, _ = rescore(req_set, all_resolved, durations, flags)

    probes: list[Probe] = []
    for entry in facets.values():
        fd, reqs = entry["facet"], entry["reqs"]
        key = fd["facet_key"]
        j = by_key.get(key, {})
        verdict = _verdict(j) if j else "UNKNOWN"
        depth = j.get("depth_level", "L0") if j else "L0"
        if verdict == "ENTAILED" and depth in ("L2", "L3", "L4"):
            continue  # already settled

        # Same world as S_all, but this facet stays as it is now.
        keep_j = by_key.get(key)
        without_this = list(all_resolved)
        without_this = [j for j in without_this if j["facet_key"] != key]
        if keep_j is not None:
            without_this.append(keep_j)
        without, _ = rescore(req_set, without_this, durations, flags)
        p = STRONG_ANSWER_PRIOR.get(verdict, 0.5)
        # Interval bounds: an UNKNOWN requirement is excluded from the point score, so compare best vs worst case.
        contribution = max(0.0, best_all.score_hi - without.score_lo)
        crosses = (without.final_score < cutoff <= best_all.final_score) or (best_all.band != without.band)
        weight = max(_importance_factor(r, fd) for r in reqs)
        voi = round(contribution * _uncertainty_factor(p) * weight * (1.5 if crosses else 1.0), 3)
        if voi <= 0:
            continue

        tpl = _template(fd["hypothesis"])
        support = list(j.get("support_atoms") or []) if j else []
        why = (
            f"Facet '{fd['hypothesis']}' belum terbukti ({verdict}, kedalaman {depth}); "
            f"bila terbukti, skor yang dapat dicapai naik dari {without.final_score:.1f} ke {best_all.final_score:.1f}"
            + (" dan melewati batas band/shortlist." if crosses else ".")
        )
        pid = hashlib.sha256(f"{candidate_id}:{facet_signature(fd)}".encode()).hexdigest()[:12]
        probe = Probe(
            probe_id=pid,
            candidate_id=str(candidate_id),
            facet_key=key,
            requirement_ids=sorted({r["requirement_id"] for r in reqs}),
            hypothesis=fd["hypothesis"],
            current_verdict=verdict,
            target_atom_ids=support,
            voi=voi,
            score_now=now.final_score,
            score_if_all_resolved=best_all.final_score,
            score_without_this=without.final_score,
            crosses_boundary=crosses,
            why=why,
            question=tpl["question"],
            listen_for_strong=tpl["strong"],
            listen_for_weak=tpl["weak"],
            follow_ups=tpl["follow_ups"],
        )
        if validate_probe(probe):
            continue  # a probe touching a protected topic is dropped, never softened
        probes.append(probe)

    probes.sort(key=lambda pr: (-pr.voi, pr.facet_key))
    return probes[: max(0, budget)]


# --------------------------------------------------------------------------------------------- answers
def apply_interview_answers(
    req_set: dict[str, Any],
    judgments: list[Any],
    answers: list[InterviewAnswer],
    candidate_id: str,
    durations: list[dict[str, Any]] | None = None,
    flags: list[str] | None = None,
) -> RescoreResult:
    """Turns rated answers into interview atoms, overrides the matching facet judgments, and re-scores."""
    norm = [_norm_judgment(j) for j in judgments]
    before, states_before = rescore(req_set, norm, durations, flags)

    updated = copy.deepcopy(norm)
    atoms: list[dict[str, Any]] = []
    adjusted: list[str] = []
    for i, ans in enumerate(answers, start=1):
        rating = ans.rating.upper()
        if rating not in RATING_TO_JUDGMENT:
            raise ValueError(f"rating must be one of {sorted(RATING_TO_JUDGMENT)}, got {ans.rating!r}")
        verdict, default_depth = RATING_TO_JUDGMENT[rating]
        depth = (ans.depth or default_depth).upper()
        atom_key = f"INT.{ans.probe_id or ans.facet_key}.{i}"
        atoms.append(
            {
                "atom_key": atom_key,
                "kind": "interview_answer",
                "entry_ref": None,
                "page": 0,
                "char_start": 0,
                "char_end": len(ans.answer_text),
                "text_redacted": scrub_protected_attributes(ans.answer_text)[0],
                "visibility": "VISIBLE",
                "rating": rating,
                "facet_key": ans.facet_key,
                "recorded_by": ans.recorded_by,
            }
        )
        support = [atom_key] if verdict != "NOT_ENTAILED" else []
        updated = _with_facet(updated, ans.facet_key, verdict, depth, support)
        adjusted.append(ans.facet_key)

    after, states_after = rescore(req_set, updated, durations, list(flags or []) + ["INTERVIEW_ADJUSTED"])
    return RescoreResult(
        before=_summary(before),
        after=_summary(after),
        requirement_states_before=states_before,
        requirement_states_after=states_after,
        interview_atoms=atoms,
        adjusted_facets=sorted(set(adjusted)),
    )


def _summary(r: Any) -> dict[str, Any]:
    return {
        "band": r.band,
        "final_score": r.final_score,
        "recommendation": r.recommendation,
        "score_lo": r.score_lo,
        "score_hi": r.score_hi,
        "flags": sorted(r.flags),
    }
