"""Template-based explanation generator (02_SCORING Section 10)."""

from __future__ import annotations

from typing import Any

from src.domain.scorer import ScoreResult


def generate_explanation(
    requirement_set: dict[str, Any],
    score_res: ScoreResult,
    req_states: dict[str, str],
    evidence_map: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Generates structured template-based explanations for candidate evaluation."""
    reqs_by_id = {r["requirement_id"]: r for r in requirement_set.get("requirements", [])}

    # 1. Kelebihan (STRONG requirements sorted by weight desc)
    strengths = []
    for rid, st in req_states.items():
        if st == "STRONG" and rid in reqs_by_id:
            r = reqs_by_id[rid]
            evs = evidence_map.get(rid, [])
            quote = evs[0].get("quote", "") if evs else ""
            strengths.append(
                {
                    "requirement_id": rid,
                    "description": r.get("description", ""),
                    "weight": r.get("weight", 0),
                    "quote": quote,
                }
            )
    strengths.sort(key=lambda x: x["weight"], reverse=True)

    # 2. Belum Terbukti (NOT_DEMONSTRATED & PARTIAL sorted by weight desc)
    unproven = []
    for rid, st in req_states.items():
        if st in ("NOT_DEMONSTRATED", "PARTIAL") and rid in reqs_by_id:
            r = reqs_by_id[rid]
            status_text = "Sebagian terpenuhi" if st == "PARTIAL" else "Tidak tercantum di CV"
            unproven.append(
                {
                    "requirement_id": rid,
                    "description": r.get("description", ""),
                    "state": st,
                    "weight": r.get("weight", 0),
                    "note": f"{status_text} ({r.get('importance', '')})",
                }
            )
    unproven.sort(key=lambda x: x["weight"], reverse=True)

    # 3. Pertanyaan Interview (1 question for each must_have or strong_preference that is not strong)
    questions = []
    for u in unproven:
        r = reqs_by_id.get(u["requirement_id"], {})
        imp = r.get("importance", "")
        if imp in ("MUST_HAVE", "STRONG_PREFERENCE"):
            questions.append(
                {
                    "requirement_id": u["requirement_id"],
                    "focus": r.get("description", ""),
                    "question": f"Bisa ceritakan pengalaman atau pemahaman Anda terkait {r.get('description', '')}?",
                }
            )

    return {
        "band": score_res.band,
        "recommendation": score_res.recommendation,
        "final_score": score_res.final_score,
        "strengths": strengths,
        "unproven": unproven,
        "interview_questions": questions,
    }
