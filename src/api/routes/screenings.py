"""Screening runs, candidate ranking, comparison, and evaluation export endpoints (M4)."""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user, get_job_for_tenant, require_role
from src.domain.explainer import generate_explanation
from src.domain.models import User, UserRole
from src.domain.scorer import score
from src.domain.screening_service import execute_screening_run
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/jobs/{job_id}/screenings", tags=["Screenings"])


class ScreeningRunCreate(BaseModel):
    as_of: str | None = Field(default=None, description="As-of date for evaluation")
    use_verifier: bool = Field(default=False, description="Enable LLM verification for ambiguous criteria")


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def trigger_screening_run(
    job_id: uuid.UUID,
    payload: ScreeningRunCreate,
    sync: bool = Query(default=False, description="Run synchronously for test/eval parity"),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER, UserRole.HIRING_MANAGER])),
) -> JSONResponse:
    """Enqueues an immutable screening run into jobs_queue asynchronously (FX-30)."""
    effective_as_of = payload.as_of or date.today().isoformat()
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        # 1. Fetch latest approved requirement set for the job
        await cur.execute(
            """
            SELECT id, version, category_weights FROM requirement_sets
            WHERE job_id = %s AND tenant_id = %s AND status = 'APPROVED'
            ORDER BY version DESC LIMIT 1
            """,
            (job_id, current_user.tenant_id),
        )
        req_set = await cur.fetchone()
        if not req_set:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Kriteria belum disetujui. Setujui requirement set terlebih dahulu.",
            )

        # 2. Fetch approved administrative eligibility rules
        await cur.execute(
            """
            SELECT id, rule_type, value, basis_category, reference_date
            FROM eligibility_rules
            WHERE job_id = %s AND tenant_id = %s AND status = 'APPROVED'
            ORDER BY created_at ASC
            """,
            (job_id, current_user.tenant_id),
        )
        approved_rules = [dict(r) for r in await cur.fetchall()]
        elig_snapshot = [
            {
                "id": str(r["id"]),
                "rule_type": r["rule_type"],
                "value": r["value"],
                "basis_category": r["basis_category"],
                "reference_date": str(r["reference_date"]),
            }
            for r in approved_rules
        ]

        # 3. Create immutable screening run record in QUEUED state
        run_id = uuid.uuid4()
        versions_info = {
            "extractor": f"cv-extractor {settings.EXTRACTOR_VERSION}",
            "embedding": settings.EMBEDDING_MODEL,
            "scoring": settings.SCORING_VERSION,
            "scoring_mode": settings.SCORING_MODE,
            "semantic_threshold": settings.SEMANTIC_THRESHOLD,
        }
        await cur.execute(
            """
            INSERT INTO screening_runs (
                id, tenant_id, job_id, requirement_set_id, status, as_of, versions, params, eligibility_snapshot, progress, started_at
            )
            VALUES (%s, %s, %s, %s, 'QUEUED', %s, %s, %s, %s, '{\"done\": 0, \"total\": 0}'::jsonb, now())
            """,
            (
                run_id,
                current_user.tenant_id,
                job_id,
                req_set["id"],
                effective_as_of,
                json.dumps(versions_info),
                json.dumps({"use_verifier": payload.use_verifier, "as_of": effective_as_of}),
                json.dumps(elig_snapshot),
            ),
        )

        # 4. Enqueue background task to jobs_queue
        await cur.execute(
            """
            INSERT INTO jobs_queue (type, payload, status, attempts, max_attempts)
            VALUES ('screening_run', %s, 'PENDING', 0, 3)
            """,
            (json.dumps({"run_id": str(run_id)}),),
        )
        await conn.commit()

        if sync:
            await execute_screening_run(run_id)
            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content={"status": "COMPLETED", "screening_run_id": str(run_id), "run_id": str(run_id)},
            )

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"status": "QUEUED", "screening_run_id": str(run_id), "run_id": str(run_id)},
        )


@router.get("/latest")
async def get_latest_screening(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns the latest completed screening run and its rankings for a job."""
    async with get_connection() as conn:
        cur = conn.cursor()
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            """
            SELECT id, status, as_of, started_at, finished_at
            FROM screening_runs
            WHERE job_id = %s AND tenant_id = %s AND status IN ('DONE', 'COMPLETED')
            ORDER BY COALESCE(finished_at, started_at) DESC NULLS LAST
            LIMIT 1
            """,
            (job_id, current_user.tenant_id),
        )
        latest_run = await cur.fetchone()
        if not latest_run:
            return {"job_id": str(job_id), "latest_run": None, "rankings": []}

        run_id = latest_run["id"]
        await cur.execute(
            """
            WITH req_summary AS (
                SELECT candidate_id, jsonb_object_agg(requirement_id, state) as states
                FROM requirement_scores
                WHERE run_id = %s AND tenant_id = %s
                GROUP BY candidate_id
            )
            SELECT cs.rank, cs.candidate_id as cv_id, cs.candidate_id, d.original_filename as file_name, cs.final_score, cs.raw_score,
                   cs.band, cs.recommendation, cs.category_scores as category_breakdown, cs.flags, d.status as quality_status,
                   d.reasons as document_reasons,
                   COALESCE(rs.states, '{}'::jsonb) as requirement_states,
                   COALESCE(ce.overall_status, 'NOT_APPLICABLE') as eligibility_status,
                   COALESCE(
                       ARRAY(SELECT jsonb_array_elements(ce.details)->>'reason_code'),
                       '{}'::text[]
                   ) as eligibility_reasons
            FROM candidate_scores cs
            JOIN documents d ON cs.document_id = d.id AND d.tenant_id = cs.tenant_id
            LEFT JOIN req_summary rs ON rs.candidate_id = cs.candidate_id
            LEFT JOIN candidate_eligibility ce ON ce.candidate_id = cs.candidate_id AND ce.run_id = cs.run_id AND ce.tenant_id = cs.tenant_id
            WHERE cs.run_id = %s AND cs.tenant_id = %s
            ORDER BY cs.rank ASC NULLS LAST, cs.final_score DESC
            """,
            (run_id, current_user.tenant_id, run_id, current_user.tenant_id),
        )
        rows = await cur.fetchall()
        return {
            "job_id": str(job_id),
            "screening_run_id": str(run_id),
            "latest_run": {
                "id": str(run_id),
                "status": latest_run["status"],
                "as_of": str(latest_run["as_of"]),
                "finished_at": str(latest_run["finished_at"]),
            },
            "rankings": [dict(r) for r in rows],
        }


@router.get("/{run_id}")
async def get_screening_run_status(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns status and progress of a screening run (FX-30)."""
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            "SELECT id, status, progress, started_at, finished_at FROM screening_runs WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (run_id, job_id, current_user.tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
        return {
            "id": str(row["id"]),
            "status": row["status"],
            "progress": row["progress"],
            "started_at": str(row["started_at"]) if row["started_at"] else None,
            "finished_at": str(row["finished_at"]) if row["finished_at"] else None,
        }


@router.get("/{run_id}/rankings")
async def get_rankings(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    eligibility: str = Query(default="all", description="Filter eligibility: all | eligible | eligible_or_unknown"),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns candidate rankings for a completed screening run."""
    async with get_connection() as conn:
        cur = conn.cursor()
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            "SELECT id FROM screening_runs WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (run_id, job_id, current_user.tenant_id),
        )
        if not await cur.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")

        await cur.execute(
            """
            WITH req_summary AS (
                SELECT candidate_id, jsonb_object_agg(requirement_id, state) as states
                FROM requirement_scores
                WHERE run_id = %s AND tenant_id = %s
                GROUP BY candidate_id
            )
            SELECT cs.rank, cs.candidate_id as cv_id, cs.candidate_id, d.original_filename as file_name, cs.final_score, cs.raw_score,
                   cs.band, cs.recommendation, cs.category_scores as category_breakdown, cs.flags, d.status as quality_status,
                   d.reasons as document_reasons,
                   COALESCE(rs.states, '{}'::jsonb) as requirement_states,
                   COALESCE(ce.overall_status, 'NOT_APPLICABLE') as eligibility_status,
                   COALESCE(
                       ARRAY(SELECT jsonb_array_elements(ce.details)->>'reason_code'),
                       '{}'::text[]
                   ) as eligibility_reasons
            FROM candidate_scores cs
            JOIN documents d ON cs.document_id = d.id AND d.tenant_id = cs.tenant_id
            LEFT JOIN req_summary rs ON rs.candidate_id = cs.candidate_id
            LEFT JOIN candidate_eligibility ce ON ce.candidate_id = cs.candidate_id AND ce.run_id = cs.run_id AND ce.tenant_id = cs.tenant_id
            WHERE cs.run_id = %s AND cs.tenant_id = %s
            ORDER BY cs.rank ASC NULLS LAST, cs.final_score DESC
            """,
            (run_id, current_user.tenant_id, run_id, current_user.tenant_id),
        )
        rows = [dict(r) for r in await cur.fetchall()]

        # Filter eligibility if specified while preserving original candidate rank
        if eligibility == "eligible":
            filtered_rows = [r for r in rows if r["eligibility_status"] == "ELIGIBLE"]
        elif eligibility == "eligible_or_unknown":
            filtered_rows = [r for r in rows if r["eligibility_status"] in ("ELIGIBLE", "UNKNOWN")]
        else:
            filtered_rows = rows

        return {
            "job_id": str(job_id),
            "screening_run_id": str(run_id),
            "rankings": filtered_rows,
        }


@router.get("/{run_id}/candidates/{cv_id}")
async def get_candidate_detail(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    cv_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns detailed evaluation, requirement states, evidence quotes, and template reasoning."""
    async with get_connection() as conn:
        cur = conn.cursor()
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            "SELECT id FROM screening_runs WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (run_id, job_id, current_user.tenant_id),
        )
        if not await cur.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")

        # Fetch candidate score
        await cur.execute(
            """
            SELECT cs.rank, cs.final_score, cs.raw_score, cs.band, cs.recommendation,
                   cs.category_scores as category_breakdown, cs.flags, d.original_filename as file_name
            FROM candidate_scores cs
            JOIN documents d ON cs.document_id = d.id AND d.tenant_id = cs.tenant_id
            WHERE cs.run_id = %s AND cs.candidate_id = %s AND cs.tenant_id = %s
            """,
            (run_id, cv_id, current_user.tenant_id),
        )
        cand_score = await cur.fetchone()
        if not cand_score:
            raise HTTPException(status_code=404, detail="Candidate score not found")

        # Fetch requirements and states
        await cur.execute(
            """
            SELECT rs.requirement_id, rs.state, rs.confidence,
                   COALESCE(r.description, rs.requirement_id) as description,
                   COALESCE(r.category, 'HARD_SKILLS') as category,
                   COALESCE(r.kind, 'SKILL') as kind,
                   COALESCE(r.importance, 'MUST_HAVE') as importance,
                   COALESCE(r.weight, 10.0) as weight,
                   r.source_text
            FROM requirement_scores rs
            JOIN screening_runs sr ON sr.id = rs.run_id AND sr.tenant_id = rs.tenant_id
            LEFT JOIN requirements r ON r.requirement_set_id = sr.requirement_set_id AND r.requirement_id = rs.requirement_id AND r.tenant_id = rs.tenant_id
            WHERE rs.run_id = %s AND rs.candidate_id = %s AND rs.tenant_id = %s
            ORDER BY rs.requirement_id
            """,
            (run_id, cv_id, current_user.tenant_id),
        )
        req_rows = await cur.fetchall()

        # Build explanation
        req_states = {r["requirement_id"]: r["state"] for r in req_rows}
        ev_map: dict[str, list[dict[str, Any]]] = {}
        for r in req_rows:
            await cur.execute(
                """
                SELECT quote, context, verified
                FROM evidence
                WHERE run_id = %s AND candidate_id = %s AND requirement_id = %s AND tenant_id = %s
                """,
                (run_id, cv_id, r["requirement_id"], current_user.tenant_id),
            )
            evs = await cur.fetchall()
            ev_map[r["requirement_id"]] = [dict(e) for e in evs]

        # ScoreResult for explainer
        cat_weights = cand_score["category_breakdown"] or {
            "EXPERIENCE": 40,
            "HARD_SKILLS": 30,
            "EDUCATION_CERT": 15,
            "ACHIEVEMENT": 15,
        }
        score_obj = score(
            req_states,
            {
                "category_weights": cat_weights,
                "requirements": [dict(r) for r in req_rows],
            },
        )
        explanation = generate_explanation(
            {"requirements": [dict(r) for r in req_rows]},
            score_obj,
            req_states,
            ev_map,
        )

        # Fetch eligibility details
        await cur.execute(
            """
            SELECT overall_status, details
            FROM candidate_eligibility
            WHERE run_id = %s AND candidate_id = %s AND tenant_id = %s
            """,
            (run_id, cv_id, current_user.tenant_id),
        )
        elig_row = await cur.fetchone()
        elig_data = {
            "overall_status": elig_row["overall_status"] if elig_row else "NOT_APPLICABLE",
            "details": elig_row["details"] if elig_row else [],
        }

        return {
            "cv_id": str(cv_id),
            "file_name": cand_score["file_name"],
            "rank": cand_score["rank"],
            "score": cand_score["final_score"],
            "band": cand_score["band"],
            "recommendation": cand_score["recommendation"],
            "category_breakdown": cand_score["category_breakdown"],
            "metrics": {},
            "flags": cand_score["flags"],
            "requirement_states": req_states,
            "evidence": ev_map,
            "explanation": explanation,
            "eligibility": elig_data,
        }


@router.get("/{run_id}/compare")
async def compare_candidates(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    c1: uuid.UUID = Query(..., description="First CV ID"),
    c2: uuid.UUID = Query(..., description="Second CV ID"),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns side-by-side comparison of two candidates."""
    det1 = await get_candidate_detail(job_id, run_id, c1, current_user)
    det2 = await get_candidate_detail(job_id, run_id, c2, current_user)

    all_req_ids = sorted(list(set(det1["requirement_states"].keys()) | set(det2["requirement_states"].keys())))
    req_comparison = []
    for rid in all_req_ids:
        req_comparison.append(
            {
                "requirement_id": rid,
                "candidate_1_state": det1["requirement_states"].get(rid),
                "candidate_2_state": det2["requirement_states"].get(rid),
                "candidate_1_quote": det1["evidence"].get(rid, [{}])[0].get("quote")
                if det1["evidence"].get(rid)
                else "",
                "candidate_2_quote": det2["evidence"].get(rid, [{}])[0].get("quote")
                if det2["evidence"].get(rid)
                else "",
            }
        )

    return {
        "candidate_1": {
            "cv_id": str(c1),
            "file_name": det1["file_name"],
            "rank": det1["rank"],
            "score": det1["score"],
            "band": det1["band"],
            "recommendation": det1["recommendation"],
        },
        "candidate_2": {
            "cv_id": str(c2),
            "file_name": det2["file_name"],
            "rank": det2["rank"],
            "score": det2["score"],
            "band": det2["band"],
            "recommendation": det2["recommendation"],
        },
        "score_delta": round(det1["score"] - det2["score"], 2),
        "requirement_comparison": req_comparison,
    }


@router.get("/{run_id}/eval-export")
async def export_for_evaluator(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Exports run results matching exact eval_export.schema.json format for evaluate.py."""
    async with get_connection() as conn:
        cur = conn.cursor()
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        await cur.execute(
            "SELECT external_ref as code FROM jobs WHERE id = %s AND tenant_id = %s", (job_id, current_user.tenant_id)
        )
        job_row = await cur.fetchone()
        job_code = job_row["code"] if job_row and job_row["code"] else "JD-01"

        await cur.execute(
            "SELECT as_of FROM screening_runs WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (run_id, job_id, current_user.tenant_id),
        )
        run_row = await cur.fetchone()
        if not run_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run not found")
        as_of = str(run_row["as_of"]) if run_row and run_row.get("as_of") else date.today().isoformat()

        await cur.execute(
            """
            SELECT cs.candidate_id as cv_id, cs.rank, cs.final_score, cs.raw_score, cs.band,
                   cs.recommendation, cs.category_scores as category_breakdown, cs.flags,
                   d.original_filename as file_name, d.status as quality_status, d.reasons
            FROM candidate_scores cs
            JOIN documents d ON cs.document_id = d.id AND d.tenant_id = cs.tenant_id
            WHERE cs.run_id = %s AND cs.tenant_id = %s
            ORDER BY cs.rank ASC NULLS LAST
            """,
            (run_id, current_user.tenant_id),
        )
        score_rows = await cur.fetchall()

        export_results = []
        for r in score_rows:
            # Fetch requirement states
            await cur.execute(
                """
                SELECT requirement_id, state
                FROM requirement_scores
                WHERE run_id = %s AND candidate_id = %s AND tenant_id = %s
                """,
                (run_id, r["cv_id"], current_user.tenant_id),
            )
            req_states = {row["requirement_id"]: row["state"] for row in await cur.fetchall()}

            status_val = r["quality_status"] if r["quality_status"] != "READY" else "SCORED"
            export_results.append(
                {
                    "file": r["file_name"],
                    "status": status_val,
                    "rank": r["rank"],
                    "band": r["band"],
                    "score": float(r["final_score"] or 0),
                    "raw_score": float(r["raw_score"] or 0),
                    "recommendation": r["recommendation"],
                    "requirement_states": req_states,
                    "metrics": {},
                    "flags": r["flags"] or [],
                    "reasons": r["reasons"] or [],
                }
            )

        return {
            "job_id": job_code,
            "run_id": str(run_id),
            "as_of": as_of,
            "results": export_results,
        }
