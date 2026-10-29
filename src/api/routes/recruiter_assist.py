"""Recruiter assist: interview probes, interview answers (re-score) and Copilot HR tools (v2.2).

All three read results the pipeline already stored; none of them calls an LLM, scores in code, and shows
candidates by short id rather than by file name.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_job_for_tenant, require_role
from src.api.routes.screenings import _fetch_candidate_v2_artifacts
from src.domain.copilot import TOOLS, CopilotStore, check_query, enforce_citations
from src.domain.interview import DEFAULT_BUDGET, InterviewAnswer, apply_interview_answers, build_probes
from src.domain.models import User, UserRole
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger

router = APIRouter(prefix="/api/v1/jobs/{job_id}/screenings/{run_id}", tags=["Recruiter assist"])

ALLOWED = [UserRole.RECRUITER, UserRole.ADMIN, UserRole.HIRING_MANAGER]


class AnswerIn(BaseModel):
    facet_key: str
    rating: str = Field(pattern="^(STRONG|ADEQUATE|WEAK)$")
    answer_text: str = Field(default="", max_length=4000)
    probe_id: str | None = None
    depth: str | None = Field(default=None, pattern="^L[0-4]$")


class AnswersIn(BaseModel):
    answers: list[AnswerIn] = Field(min_length=1, max_length=20)


class CopilotQuery(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    draft_answer: str | None = Field(
        default=None, max_length=8000, description="Optional prose to validate for citations"
    )


# ------------------------------------------------------------------------------------------------ loading
async def _run_requirements(cur: Any, run_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, Any]:
    await cur.execute(
        "SELECT requirement_set_id FROM screening_runs WHERE id = %s AND tenant_id = %s", (run_id, tenant_id)
    )
    run = await cur.fetchone()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
    await cur.execute(
        "SELECT category_weights FROM requirement_sets WHERE id = %s AND tenant_id = %s",
        (run["requirement_set_id"], tenant_id),
    )
    weights = await cur.fetchone()
    await cur.execute(
        """
        SELECT id, requirement_id, description, category, kind, importance, weight, target_domains, duration_policy
        FROM requirements WHERE requirement_set_id = %s AND tenant_id = %s ORDER BY requirement_id
        """,
        (run["requirement_set_id"], tenant_id),
    )
    reqs = []
    for r in await cur.fetchall():
        await cur.execute(
            "SELECT facet_key, hypothesis, core, concepts FROM requirement_facets WHERE requirement_uuid = %s ORDER BY facet_key",
            (r["id"],),
        )
        facets = [dict(f) for f in await cur.fetchall()]
        policy = (
            r["duration_policy"] if isinstance(r["duration_policy"], dict) else json.loads(r["duration_policy"] or "{}")
        )
        reqs.append(
            {
                "requirement_id": r["requirement_id"],
                "description": r["description"],
                "category": r["category"],
                "kind": r["kind"],
                "importance": r["importance"],
                "weight": float(r["weight"]),
                "target_domains": list(r["target_domains"] or []),
                "duration_policy": policy or None,
                "facets": facets,
            }
        )
    return {"category_weights": (weights or {}).get("category_weights") or {}, "requirements": reqs}


async def _candidate_view(cur: Any, run_id: uuid.UUID, candidate_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, Any]:
    await cur.execute(
        """
        SELECT cs.rank, cs.final_score, cs.band, cs.recommendation, cs.flags
        FROM candidate_scores cs WHERE cs.run_id = %s AND cs.candidate_id = %s AND cs.tenant_id = %s
        """,
        (run_id, candidate_id, tenant_id),
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found in this run")
    view = dict(row)
    view["candidate_id"] = str(candidate_id)
    view.update(await _fetch_candidate_v2_artifacts(cur, run_id, candidate_id, tenant_id))
    return view


def _judgments(view: dict[str, Any]) -> list[dict[str, Any]]:
    seen: dict[str, dict[str, Any]] = {}
    for j in view.get("facet_judgments", []):
        seen.setdefault(j["facet_key"], dict(j, verdict=str(j["verdict"]).split(".")[-1]))
    return list(seen.values())


async def _verify(cur: Any, job_id: uuid.UUID, user: User) -> None:
    await get_job_for_tenant(cur, job_id, user.tenant_id)


# ------------------------------------------------------------------------------------------------ probes
@router.get("/candidates/{candidate_id}/probes")
async def get_probes(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    budget: int = Query(default=DEFAULT_BUDGET, ge=0, le=10),
    current_user: User = Depends(require_role(ALLOWED)),
) -> dict[str, Any]:
    """Interview probes ranked by value of information. Same budget for every candidate; recruiter approves."""
    async with get_connection() as conn:
        cur = conn.cursor()
        await _verify(cur, job_id, current_user)
        req_set = await _run_requirements(cur, run_id, current_user.tenant_id)
        view = await _candidate_view(cur, run_id, candidate_id, current_user.tenant_id)
    probes = build_probes(
        req_set,
        _judgments(view),
        str(candidate_id),
        durations=view.get("domain_durations"),
        flags=list(view.get("flags") or []),
        budget=budget,
    )
    return {
        "candidate_id": str(candidate_id),
        "budget": budget,
        "status_note": "Probes are PENDING_APPROVAL: the recruiter must approve before they are used.",
        "probes": [p.to_dict() for p in probes],
    }


@router.post("/candidates/{candidate_id}/interview-answers")
async def record_interview_answers(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    body: AnswersIn,
    current_user: User = Depends(require_role([UserRole.RECRUITER, UserRole.ADMIN])),
) -> dict[str, Any]:
    """Stores the recruiter's rated answers as interview atoms and returns the re-scored result (original untouched)."""
    async with get_connection() as conn:
        cur = conn.cursor()
        await _verify(cur, job_id, current_user)
        req_set = await _run_requirements(cur, run_id, current_user.tenant_id)
        view = await _candidate_view(cur, run_id, candidate_id, current_user.tenant_id)
        known = {f["facet_key"] for r in req_set["requirements"] for f in r["facets"]}
        unknown = sorted({a.facet_key for a in body.answers} - known)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"Unknown facet(s): {unknown}"
            )
        for a in body.answers:
            await cur.execute(
                """
                INSERT INTO interview_answers (tenant_id, run_id, candidate_id, facet_key, probe_id, rating, depth_level, answer_text, recorded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    current_user.tenant_id,
                    run_id,
                    candidate_id,
                    a.facet_key,
                    a.probe_id,
                    a.rating,
                    a.depth,
                    a.answer_text,
                    current_user.id,
                ),
            )
        await conn.commit()
        await cur.execute(
            "SELECT facet_key, probe_id, rating, depth_level, answer_text, recorded_by FROM interview_answers "
            "WHERE run_id = %s AND candidate_id = %s AND tenant_id = %s ORDER BY created_at",
            (run_id, candidate_id, current_user.tenant_id),
        )
        stored = await cur.fetchall()
    answers = [
        InterviewAnswer(
            r["facet_key"],
            r["rating"],
            r["answer_text"],
            r["probe_id"],
            r["depth_level"],
            str(r["recorded_by"]) if r["recorded_by"] else None,
        )
        for r in stored
    ]
    result = apply_interview_answers(
        req_set,
        _judgments(view),
        answers,
        str(candidate_id),
        durations=view.get("domain_durations"),
        flags=list(view.get("flags") or []),
    )
    return {
        "candidate_id": str(candidate_id),
        "before": result.before,
        "after": result.after,
        "requirement_states_before": result.requirement_states_before,
        "requirement_states_after": result.requirement_states_after,
        "adjusted_facets": result.adjusted_facets,
        "interview_atoms": result.interview_atoms,
    }


# ------------------------------------------------------------------------------------------------ copilot
@router.post("/copilot")
async def copilot_query(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    body: CopilotQuery,
    current_user: User = Depends(require_role(ALLOWED)),
) -> dict[str, Any]:
    """Runs one structured Copilot tool; optionally validates draft prose for citation grounding. Every call is audited."""
    allowed, reason = True, ""
    text_to_check = " ".join(str(v) for v in body.args.values()) + " " + (body.draft_answer or "")
    ok, refusal = check_query(text_to_check)
    if not ok:
        allowed, reason = False, refusal
    if allowed and body.tool not in TOOLS:
        allowed, reason = False, f"unknown tool {body.tool!r}; available: {sorted(TOOLS)}"

    async with get_connection() as conn:
        cur = conn.cursor()
        await _verify(cur, job_id, current_user)
        await cur.execute(
            "SELECT 1 FROM screening_runs WHERE id = %s AND tenant_id = %s", (run_id, current_user.tenant_id)
        )
        if not await cur.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
        await cur.execute(
            "INSERT INTO copilot_audit_log (tenant_id, user_id, run_id, tool, args, allowed, reason) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                current_user.tenant_id,
                current_user.id,
                run_id,
                body.tool,
                json.dumps(body.args),
                allowed,
                reason or None,
            ),
        )
        await conn.commit()
        logger.info(
            json.dumps({"event": "copilot_query", "run_id": str(run_id), "tool": body.tool, "allowed": allowed})
        )
        if not allowed:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=reason)

        await cur.execute(
            "SELECT candidate_id FROM candidate_scores WHERE run_id = %s AND tenant_id = %s",
            (run_id, current_user.tenant_id),
        )
        ids = [r["candidate_id"] for r in await cur.fetchall()]
        rows = []
        for cid in ids:
            rows.append(await _candidate_view(cur, run_id, cid, current_user.tenant_id))
        req_set = await _run_requirements(cur, run_id, current_user.tenant_id)

    store = CopilotStore.from_rankings_payload({"rankings": rows}, req_set["requirements"])
    try:
        result = TOOLS[body.tool](store, **body.args)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TypeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"bad arguments: {exc}") from exc

    out: dict[str, Any] = {"tool": body.tool, "result": result}
    if body.draft_answer:
        mentioned = [a for a in (body.args.get("candidate_ids") or [body.args.get("candidate_id")]) if a]
        report = enforce_citations(body.draft_answer, store, mentioned or None)
        out["citation_check"] = {"ok": report.ok, "cleaned": report.cleaned, "violations": report.violations}
    return out
