"""Requirement sets compilation, manual editing, importing, and approval endpoints."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_job_for_tenant, require_role
from src.api.middleware.rate_limiter import check_rate_limit
from src.domain.jd_compiler import compile_job_requirements
from src.domain.models import User, UserRole
from src.domain.policy_linter import lint_text
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger

router = APIRouter(prefix="/api/v1/jobs/{job_id}/requirements", tags=["Requirements"])


class ManualRequirementCreate(BaseModel):
    requirement_id: str
    description: str
    category: str = "HARD_SKILLS"
    kind: str = "SKILL"
    importance: str = "MUST_HAVE"
    weight: float = 10.0
    concepts: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    source_text: str | None = None


class ImportApprovedRequest(BaseModel):
    requirement_set_version: int = 1
    category_weights: dict[str, float]
    requirements: list[dict[str, Any]]
    status: str = "APPROVED"


@router.post("/compile", status_code=status.HTTP_201_CREATED)
async def compile_requirements(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        job = await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        # Compile JD requirements
        compiled = await compile_job_requirements(job["jd_text"], tenant_id=current_user.tenant_id)

        # Get next version
        await cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 as next_ver FROM requirement_sets WHERE job_id = %s AND tenant_id = %s",
            (job_id, current_user.tenant_id),
        )
        ver_row = await cur.fetchone()
        next_ver = ver_row["next_ver"]

        set_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights)
            VALUES (%s, %s, %s, %s, 'DRAFT', %s)
            RETURNING id, version, status
            """,
            (set_id, current_user.tenant_id, job_id, next_ver, json.dumps(compiled["category_weights"])),
        )

        created_reqs = []
        for r in compiled["requirements"]:
            r_id = uuid.uuid4()
            await cur.execute(
                """
                INSERT INTO requirements (
                    id, tenant_id, requirement_set_id, requirement_id, description, category, kind,
                    importance, weight, concepts, params, source_text, lint_flags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    r_id,
                    current_user.tenant_id,
                    set_id,
                    r["requirement_id"],
                    r["description"],
                    r["category"],
                    r["kind"],
                    r["importance"],
                    r["weight"],
                    r["concepts"],
                    json.dumps(r["params"]),
                    r["source_text"],
                    r["lint_flags"],
                ),
            )
            created_reqs.append({**r, "id": str(r_id)})

        await conn.commit()

        return {
            "requirement_set_id": str(set_id),
            "version": next_ver,
            "status": "DRAFT",
            "category_weights": compiled["category_weights"],
            "requirements": created_reqs,
            "is_valid": compiled["is_valid"],
            "prohibited_flags": compiled["prohibited_flags"],
            "risky_flags": compiled["risky_flags"],
        }


@router.post("/import-approved", status_code=status.HTTP_201_CREATED)
async def import_approved_requirements(
    job_id: uuid.UUID,
    req: ImportApprovedRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        set_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO requirement_sets (
                id, tenant_id, job_id, version, status, category_weights, approved_by, approved_at
            )
            VALUES (%s, %s, %s, %s, 'APPROVED', %s, %s, now())
            ON CONFLICT (job_id, version) DO UPDATE SET
                status = 'APPROVED', category_weights = EXCLUDED.category_weights, approved_at = now()
            RETURNING id, version, status
            """,
            (
                set_id,
                current_user.tenant_id,
                job_id,
                req.requirement_set_version,
                json.dumps(req.category_weights),
                current_user.id,
            ),
        )
        set_row = await cur.fetchone()
        actual_set_id = set_row["id"]

        # Clear existing requirements if overwriting version
        await cur.execute(
            "DELETE FROM requirements WHERE requirement_set_id = %s AND tenant_id = %s",
            (actual_set_id, current_user.tenant_id),
        )

        for r in req.requirements:
            await cur.execute(
                """
                INSERT INTO requirements (
                    id, tenant_id, requirement_set_id, requirement_id, description, category, kind,
                    importance, weight, concepts, params, source_text, lint_flags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid.uuid4(),
                    current_user.tenant_id,
                    actual_set_id,
                    r["requirement_id"],
                    r["description"],
                    r["category"],
                    r["kind"],
                    r["importance"],
                    r["weight"],
                    r.get("concepts", []),
                    json.dumps(r.get("params", {})),
                    r.get("source_text"),
                    r.get("lint_flags", []),
                ),
            )

        await conn.commit()
        return {
            "requirement_set_id": str(actual_set_id),
            "version": req.requirement_set_version,
            "status": "APPROVED",
            "total_requirements": len(req.requirements),
        }


@router.post("/manual", status_code=status.HTTP_201_CREATED)
async def add_manual_requirement(
    job_id: uuid.UUID,
    req: ManualRequirementCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    """Allows recruiter to manually add/edit criteria without LLM."""
    lint_res = lint_text(req.description)
    if lint_res.get("admin_flags"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "MOVE_TO_ELIGIBILITY",
                "message": "Kriteria usia/gender tidak boleh menjadi kriteria penilaian. Pindahkan ke Syarat Administratif.",
                "flags": lint_res["admin_flags"],
            },
        )
    if lint_res["prohibited_flags"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "CANNOT_ADD_PROHIBITED_CRITERIA",
                "message": "Kriteria ditolak: mengandung kriteria terlarang.",
                "flags": lint_res["prohibited_flags"],
            },
        )
    flags = lint_res["risky_flags"]

    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        # Check latest requirement set for this job within tenant
        await cur.execute(
            """
            SELECT id, version, status, category_weights FROM requirement_sets
            WHERE job_id = %s AND tenant_id = %s
            ORDER BY version DESC LIMIT 1
            """,
            (job_id, current_user.tenant_id),
        )
        latest_set = await cur.fetchone()
        if not latest_set:
            set_id = uuid.uuid4()
            version = 1
            await cur.execute(
                """
                INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights)
                VALUES (%s, %s, %s, 1, 'DRAFT', '{"EXPERIENCE": 40, "HARD_SKILLS": 30, "EDUCATION_CERT": 15, "ACHIEVEMENT": 15}'::jsonb)
                RETURNING id
                """,
                (set_id, current_user.tenant_id, job_id),
            )
        elif latest_set["status"] == "APPROVED":
            # Immutable previous version preservation: create next DRAFT version!
            version = latest_set["version"] + 1
            set_id = uuid.uuid4()
            await cur.execute(
                """
                INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights)
                VALUES (%s, %s, %s, %s, 'DRAFT', %s)
                RETURNING id
                """,
                (set_id, current_user.tenant_id, job_id, version, json.dumps(latest_set["category_weights"])),
            )
            # Copy previous requirements to new version
            await cur.execute(
                """
                INSERT INTO requirements (
                    id, tenant_id, requirement_set_id, requirement_id, description, category, kind,
                    importance, weight, concepts, params, source_text, lint_flags
                )
                SELECT gen_random_uuid(), tenant_id, %s, requirement_id, description, category, kind,
                       importance, weight, concepts, params, source_text, lint_flags
                FROM requirements
                WHERE requirement_set_id = %s
                """,
                (set_id, latest_set["id"]),
            )
        else:
            set_id = latest_set["id"]
            version = latest_set["version"]

        r_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO requirements (
                id, tenant_id, requirement_set_id, requirement_id, description, category, kind,
                importance, weight, concepts, params, source_text, lint_flags
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (requirement_set_id, requirement_id) DO UPDATE SET
                description = EXCLUDED.description, category = EXCLUDED.category, kind = EXCLUDED.kind,
                importance = EXCLUDED.importance, weight = EXCLUDED.weight, concepts = EXCLUDED.concepts,
                params = EXCLUDED.params, lint_flags = EXCLUDED.lint_flags
            RETURNING id, requirement_id, description, lint_flags
            """,
            (
                r_id,
                current_user.tenant_id,
                set_id,
                req.requirement_id,
                req.description,
                req.category,
                req.kind,
                req.importance,
                req.weight,
                req.concepts,
                json.dumps(req.params),
                req.source_text or req.description,
                flags,
            ),
        )
        saved = await cur.fetchone()
        await conn.commit()

        return {
            "id": str(saved["id"]),
            "requirement_id": saved["requirement_id"],
            "description": saved["description"],
            "lint_flags": saved["lint_flags"],
        }


@router.post("/approve")
async def approve_requirements(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    """Approves the requirement set. Strictly blocks approval if any PROHIBITED criteria are present."""
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            """
            SELECT id, version, status FROM requirement_sets
            WHERE job_id = %s AND tenant_id = %s AND status = 'DRAFT'
            ORDER BY version DESC LIMIT 1
            """,
            (job_id, current_user.tenant_id),
        )
        set_row = await cur.fetchone()
        if not set_row:
            await cur.execute(
                """
                SELECT id, version, status, approved_at FROM requirement_sets
                WHERE job_id = %s AND tenant_id = %s AND status = 'APPROVED'
                ORDER BY version DESC LIMIT 1
                """,
                (job_id, current_user.tenant_id),
            )
            approved_existing = await cur.fetchone()
            if approved_existing:
                return {
                    "requirement_set_id": str(approved_existing["id"]),
                    "version": approved_existing["version"],
                    "approved_at": str(approved_existing["approved_at"]),
                    "status": "APPROVED",
                    "embedded_count": 0,
                }
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="No draft requirement set found to approve"
            )

        set_id = set_row["id"]

        # Check for any prohibited flags across requirements and raw JD text
        await cur.execute("SELECT jd_text FROM jobs WHERE id = %s AND tenant_id = %s", (job_id, current_user.tenant_id))
        job_row = await cur.fetchone()
        prohibited_violations = []

        if job_row and job_row["jd_text"]:
            jd_lint = lint_text(job_row["jd_text"])
            for f in jd_lint["prohibited_flags"]:
                prohibited_violations.append(
                    {
                        "requirement_id": "JD_TEXT",
                        "description": job_row["jd_text"][:100],
                        "flags": [f],
                    }
                )

        await cur.execute(
            """
            SELECT requirement_id, description, lint_flags
            FROM requirements
            WHERE requirement_set_id = %s AND tenant_id = %s
            """,
            (set_id, current_user.tenant_id),
        )
        req_rows = await cur.fetchall()

        admin_violations = []

        for r in req_rows:
            flags = r["lint_flags"] or []
            proh = [f for f in flags if f.startswith("PROHIBITED_")]
            if proh:
                prohibited_violations.append(
                    {
                        "requirement_id": r["requirement_id"],
                        "description": r["description"],
                        "flags": proh,
                    }
                )
            adm = [f for f in flags if f.startswith("ADMIN_ONLY_")]
            if adm:
                admin_violations.append(r["requirement_id"])

        if admin_violations:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "MOVE_TO_ELIGIBILITY",
                    "requirement_ids": admin_violations,
                    "message": "Kriteria usia/gender tidak boleh menjadi kriteria penilaian. Pindahkan ke Syarat Administratif.",
                },
            )

        if prohibited_violations:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "CANNOT_APPROVE_PROHIBITED_CRITERIA",
                    "message": "Persetujuan ditolak: terdapat kriteria terlarang (diskriminatif/ilegal) dalam lowongan.",
                    "violations": prohibited_violations,
                },
            )

        # Mark APPROVED
        await cur.execute(
            """
            UPDATE requirement_sets
            SET status = 'APPROVED', approved_by = %s, approved_at = now()
            WHERE id = %s AND tenant_id = %s
            RETURNING id, version, status, approved_at
            """,
            (current_user.id, set_id, current_user.tenant_id),
        )
        approved_row = await cur.fetchone()

        # Embed requirements for hybrid retrieval (FX-32)
        try:
            from src.worker.embedding import embed_texts

            req_descs = [r["description"] for r in req_rows]
            if req_descs:
                embeddings = embed_texts(req_descs)
                for r_item, emb in zip(req_rows, embeddings):
                    await cur.execute(
                        "UPDATE requirements SET embedding = %s WHERE requirement_set_id = %s AND requirement_id = %s AND tenant_id = %s",
                        (emb, set_id, r_item["requirement_id"], current_user.tenant_id),
                    )
        except Exception as e:
            logger.warning(f"Failed to embed approved requirements: {e}")

        await conn.commit()

        return {
            "status": "APPROVED",
            "requirement_set_id": str(approved_row["id"]),
            "version": approved_row["version"],
            "approved_at": str(approved_row["approved_at"]),
        }


class CompilePreviewRequest(BaseModel):
    jd_text: str


preview_router = APIRouter(prefix="/api/v1/requirements", tags=["Requirements"])


@preview_router.post(
    "/compile-preview",
    dependencies=[Depends(check_rate_limit(max_requests=10, window_seconds=60))],
)
async def compile_preview_endpoint(
    req: CompilePreviewRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER, UserRole.HIRING_MANAGER])),
) -> dict[str, Any]:
    """Compile raw Job Description text into structured requirements with concept mapping and policy linter."""
    if not req.jd_text or len(req.jd_text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Teks Job Description minimal 10 karakter.",
        )
    compiled = await compile_job_requirements(req.jd_text, tenant_id=current_user.tenant_id)
    return compiled
