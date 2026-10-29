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
from src.domain.score_trace import build_score_trace
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


async def _fetch_candidate_v2_artifacts(
    cur: Any,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> dict[str, Any]:
    """Fetches v2.1 screening artifacts: facet_judgments, domain_durations, critic_reviews, grounding_atoms."""
    # 1. Facet Judgments
    await cur.execute(
        """
        SELECT requirement_id, facet_key, verdict, depth_level,
               support_atom_ids, support_atom_keys, method, analysis, nli_p_entail,
               rationale_code, superseded_by_critic
        FROM facet_judgments
        WHERE run_id = %s AND candidate_id = %s AND tenant_id = %s
        ORDER BY requirement_id, facet_key
        """,
        (run_id, candidate_id, tenant_id),
    )
    fj_rows = await cur.fetchall()
    facet_judgments = [
        {
            "requirement_id": r["requirement_id"],
            "facet_key": r["facet_key"],
            "verdict": r["verdict"],
            "depth_level": r["depth_level"] or "L0",
            "analysis": r["analysis"] or "",
            "support_atom_ids": [str(a) for a in (r["support_atom_ids"] or [])],
            "support_atom_keys": [str(a) for a in (r["support_atom_keys"] or [])],
            "method": r["method"],
            "nli_p_entail": float(r["nli_p_entail"]) if r["nli_p_entail"] is not None else None,
            "rationale_code": r["rationale_code"],
            "superseded_by_critic": r["superseded_by_critic"],
        }
        for r in fj_rows
    ]

    # 2. Domain Durations
    await cur.execute(
        """
        SELECT domain, policy_hash, months_lo, months_hi, month_ledger
        FROM domain_durations
        WHERE run_id = %s AND candidate_id = %s AND tenant_id = %s
        ORDER BY domain
        """,
        (run_id, candidate_id, tenant_id),
    )
    dd_rows = await cur.fetchall()
    domain_durations = [
        {
            "domain": r["domain"],
            "policy_hash": r["policy_hash"],
            "months_lo": float(r["months_lo"]),
            "months_hi": float(r["months_hi"]),
            "month_ledger": r["month_ledger"]
            if isinstance(r["month_ledger"], list)
            else json.loads(r["month_ledger"] or "[]"),
        }
        for r in dd_rows
    ]

    # 3. Critic Reviews
    await cur.execute(
        """
        SELECT facet_key, verdict_action, final_verdict, original_verdict,
               depth_level, analysis, reasoning, support_atoms, is_disagreement, flags
        FROM critic_reviews
        WHERE run_id = %s AND candidate_id = %s AND tenant_id = %s
        ORDER BY facet_key
        """,
        (run_id, candidate_id, tenant_id),
    )
    cr_rows = await cur.fetchall()
    critic_reviews = [
        {
            "facet_key": r["facet_key"],
            "verdict_action": r["verdict_action"],
            "final_verdict": r["final_verdict"],
            "original_verdict": r["original_verdict"],
            "depth_level": r["depth_level"],
            "analysis": r["analysis"],
            "reasoning": r["reasoning"],
            "support_atoms": r["support_atoms"] or [],
            "is_disagreement": r["is_disagreement"],
            "flags": r["flags"] or [],
        }
        for r in cr_rows
    ]

    # 4. Grounding Atoms
    all_supp_ids: set[str] = set()
    for fj in facet_judgments:
        for sid in fj["support_atom_ids"] + fj["support_atom_keys"]:
            all_supp_ids.add(str(sid))
    for cr in critic_reviews:
        for sid in cr["support_atoms"]:
            all_supp_ids.add(str(sid))

    await cur.execute(
        """
        SELECT ea.id, ea.atom_key, ea.kind, ea.visibility, ea.entry_ref, ea.page,
               ea.char_start, ea.char_end, ea.red_start, ea.red_end, ea.bbox, ea.text_redacted
        FROM evidence_atoms ea
        JOIN candidate_profiles cp ON cp.id = ea.profile_id
        JOIN documents d ON d.id = cp.document_id
        WHERE d.candidate_id = %s AND ea.tenant_id = %s
        ORDER BY ea.page, ea.char_start
        """,
        (candidate_id, tenant_id),
    )
    ea_rows = await cur.fetchall()
    grounding_atoms = []
    for r in ea_rows:
        aid_str = str(r["id"])
        akey = r["atom_key"]
        if not all_supp_ids or aid_str in all_supp_ids or akey in all_supp_ids:
            grounding_atoms.append(
                {
                    "id": aid_str,
                    "atom_key": akey,
                    "kind": r["kind"],
                    "visibility": r["visibility"],
                    "entry_ref": r["entry_ref"],
                    "page": r["page"],
                    "char_start": r["char_start"],
                    "char_end": r["char_end"],
                    "red_start": r["red_start"],
                    "red_end": r["red_end"],
                    "bbox": r["bbox"]
                    if isinstance(r["bbox"], dict)
                    else (json.loads(r["bbox"]) if r["bbox"] else None),
                    "text_redacted": r["text_redacted"],
                }
            )

    return {
        "facet_judgments": facet_judgments,
        "domain_durations": domain_durations,
        "critic_reviews": critic_reviews,
        "grounding_atoms": grounding_atoms,
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

        for r in filtered_rows:
            cid = r["candidate_id"]
            v2_data = await _fetch_candidate_v2_artifacts(cur, run_id, cid, current_user.tenant_id)
            r.update(v2_data)

        return {
            "job_id": str(job_id),
            "screening_run_id": str(run_id),
            "rankings": filtered_rows,
        }


async def _build_trace_for_candidate(
    cur: Any,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    tenant_id: uuid.UUID,
    cand_score: dict[str, Any],
    req_states: dict[str, str],
    v2: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None, list[dict[str, Any]]]:
    """Score trace (score -> requirement -> facet -> atom -> CV sentence) plus the redacted CV text it points into."""
    try:
        await cur.execute(
            """
            SELECT sr.requirement_set_id, rset.category_weights
            FROM screening_runs sr
            LEFT JOIN requirement_sets rset ON rset.id = sr.requirement_set_id AND rset.tenant_id = sr.tenant_id
            WHERE sr.id = %s AND sr.tenant_id = %s
            """,
            (run_id, tenant_id),
        )
        run_row = await cur.fetchone()
        if not run_row:
            return None, None, []
        await cur.execute(
            """
            SELECT id, requirement_id, description, kind, category, importance, weight,
                   target_domains, duration_policy, lint_flags
            FROM requirements WHERE requirement_set_id = %s AND tenant_id = %s ORDER BY requirement_id
            """,
            (run_row["requirement_set_id"], tenant_id),
        )
        req_rows = await cur.fetchall()
        await cur.execute(
            "SELECT requirement_uuid, facet_key, hypothesis, core FROM requirement_facets "
            "WHERE requirement_uuid = ANY(%s) ORDER BY facet_key",
            ([r["id"] for r in req_rows],),
        )
        facets_by_req: dict[Any, list[dict[str, Any]]] = {}
        for f in await cur.fetchall():
            facets_by_req.setdefault(f["requirement_uuid"], []).append(
                {"facet_key": f["facet_key"], "hypothesis": f["hypothesis"], "core": f["core"]}
            )
        requirements = []
        for r in req_rows:
            policy = r["duration_policy"]
            if isinstance(policy, str):
                policy = json.loads(policy or "{}")
            requirements.append(
                {
                    "requirement_id": r["requirement_id"],
                    "description": r["description"],
                    "kind": r["kind"],
                    "category": r["category"],
                    "importance": r["importance"],
                    "weight": float(r["weight"]),
                    "target_domains": list(r["target_domains"] or []),
                    "duration_policy": policy or {},
                    "lint_flags": list(r["lint_flags"] or []),
                    "facets": facets_by_req.get(r["id"], []),
                }
            )
        await cur.execute(
            """
            SELECT cp.full_text_redacted
            FROM candidate_profiles cp JOIN documents d ON d.id = cp.document_id
            WHERE d.candidate_id = %s AND d.tenant_id = %s AND cp.full_text_redacted IS NOT NULL
            LIMIT 1
            """,
            (candidate_id, tenant_id),
        )
        text_row = await cur.fetchone()
        full_text = text_row["full_text_redacted"] if text_row else None
        trace = build_score_trace(
            stored={
                "final_score": float(cand_score["final_score"] or 0),
                "raw_score": float(cand_score["raw_score"] or 0),
                "band": cand_score["band"],
                "recommendation": cand_score["recommendation"],
                "flags": list(cand_score["flags"] or []),
                "coverage": float(cand_score["coverage"]) if cand_score.get("coverage") is not None else None,
            },
            requirements=requirements,
            requirement_states=req_states,
            category_weights=(run_row["category_weights"] or {}),
            facet_judgments=v2["facet_judgments"],
            critic_reviews=v2["critic_reviews"],
            domain_durations=v2["domain_durations"],
            atoms=v2["grounding_atoms"],
            full_text=full_text,
        )
    except Exception as exc:  # the trace is additive: never break the existing detail response
        from src.infrastructure.logging import logger

        logger.warning(f"score trace unavailable for candidate {candidate_id}: {exc}")
        return None, None, []

    refs = {
        a["atom_key"]: a for req in trace["requirements"] for f in req["facets"] for a in f["evidence"] if a.get("span")
    }
    highlights = [{"atom_key": k, "start": a["span"][0], "end": a["span"][1]} for k, a in sorted(refs.items())]
    return trace, full_text, highlights


@router.get("/{run_id}/candidates/{candidate_id}")
async def get_candidate_detail(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns detailed evaluation, requirement states, evidence quotes, and template reasoning."""
    cv_id = candidate_id
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
            SELECT cs.rank, cs.final_score, cs.raw_score, cs.band, cs.recommendation, cs.coverage,
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

        v2_artifacts = await _fetch_candidate_v2_artifacts(cur, run_id, cv_id, current_user.tenant_id)
        score_trace, full_text, highlights = await _build_trace_for_candidate(
            cur, run_id, cv_id, current_user.tenant_id, cand_score, req_states, v2_artifacts
        )

        return {
            "cv_id": str(cv_id),
            "candidate_id": str(cv_id),
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
            "facet_judgments": v2_artifacts["facet_judgments"],
            "domain_durations": v2_artifacts["domain_durations"],
            "critic_reviews": v2_artifacts["critic_reviews"],
            "grounding_atoms": v2_artifacts["grounding_atoms"],
            "score_trace": score_trace,
            "full_text": full_text,
            "source_highlights": highlights,
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
