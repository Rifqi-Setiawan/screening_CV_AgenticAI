"""Job openings management routes with role-based access control."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.dependencies import get_current_user, get_job_for_tenant, require_role
from src.domain.models import JobCreate, JobResponse, JobUpdate, User, UserRole
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(current_user: User = Depends(get_current_user)) -> list[JobResponse]:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT j.id, j.tenant_id, j.title, j.jd_text, j.status, j.location, j.employment_type, j.external_ref, j.created_at,
                       count(d.id) as cv_count
                FROM jobs j
                LEFT JOIN documents d ON d.job_id = j.id
                WHERE j.tenant_id = %s
                GROUP BY j.id, j.tenant_id, j.title, j.jd_text, j.status, j.location, j.employment_type, j.external_ref, j.created_at
                ORDER BY j.created_at DESC
                """,
            (current_user.tenant_id,),
        )
        rows = await cur.fetchall()
        return [
            JobResponse(
                id=r["id"],
                tenant_id=r["tenant_id"],
                title=r["title"],
                status=r["status"],
                location=r["location"],
                employment_type=r["employment_type"],
                external_ref=r["external_ref"],
                jd_text=r["jd_text"],
                created_at=r["created_at"],
                cv_count=r["cv_count"],
            )
            for r in rows
        ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.id, j.tenant_id, j.title, j.jd_text, j.status, j.location, j.employment_type, j.external_ref, j.created_at,
                   count(d.id) as cv_count
            FROM jobs j
            LEFT JOIN documents d ON d.job_id = j.id
            WHERE j.id = %s AND j.tenant_id = %s
            GROUP BY j.id, j.tenant_id, j.title, j.jd_text, j.status, j.location, j.employment_type, j.external_ref, j.created_at
            """,
            (job_id, current_user.tenant_id),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        return JobResponse(
            id=row["id"],
            tenant_id=row["tenant_id"],
            title=row["title"],
            status=row["status"],
            location=row["location"],
            employment_type=row["employment_type"],
            external_ref=row["external_ref"],
            jd_text=row["jd_text"],
            created_at=row["created_at"],
            cv_count=row["cv_count"],
        )


@router.get("/{job_id}/requirements")
async def get_job_requirements(
    job_id: UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        # Find latest requirement_set for this job
        await cur.execute(
            """
            SELECT id, status, version, category_weights
            FROM requirement_sets
            WHERE job_id = %s AND tenant_id = %s
            ORDER BY version DESC
            LIMIT 1
            """,
            (job_id, current_user.tenant_id),
        )
        rs = await cur.fetchone()
        if not rs:
            return []

        if rs.get("category_weights"):
            response.headers["X-Category-Weights"] = json.dumps(rs["category_weights"])
        if rs.get("version"):
            response.headers["X-Requirements-Version"] = str(rs["version"])
        response.headers["Access-Control-Expose-Headers"] = "X-Category-Weights, X-Requirements-Version"

        await cur.execute(
            """
            SELECT id, requirement_id, description, category, kind, importance, weight, concepts, params, hard_filter, source_text, lint_flags
            FROM requirements
            WHERE requirement_set_id = %s AND tenant_id = %s
            ORDER BY requirement_id
            """,
            (rs["id"], current_user.tenant_id),
        )
        rows = await cur.fetchall()
        return [
            {
                "id": str(r["id"]),
                "requirement_id": r["requirement_id"],
                "description": r["description"],
                "category": r["category"],
                "kind": r["kind"],
                "importance": r["importance"],
                "weight": float(r["weight"]) if r["weight"] is not None else 1.0,
                "concepts": r["concepts"] or [],
                "params": r["params"] or {},
                "hard_filter": r["hard_filter"],
                "source_text": r["source_text"],
                "lint_flags": r["lint_flags"] or [],
            }
            for r in rows
        ]


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    req: JobCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> JobResponse:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                INSERT INTO jobs (tenant_id, title, jd_text, location, employment_type, external_ref, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, tenant_id, title, status, location, employment_type, external_ref, created_at
                """,
            (
                current_user.tenant_id,
                req.title,
                req.jd_text,
                req.location,
                req.employment_type,
                req.external_ref,
                current_user.id,
            ),
        )
        row = await cur.fetchone()

        # Record audit log
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'JOB_CREATE', 'job', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                str(row["id"]),
                f'{{"title": "{req.title}", "external_ref": "{req.external_ref}"}}',
            ),
        )

        await conn.commit()
        return JobResponse(
            id=row["id"],
            tenant_id=row["tenant_id"],
            title=row["title"],
            status=row["status"],
            location=row["location"],
            employment_type=row["employment_type"],
            external_ref=row["external_ref"],
            created_at=row["created_at"],
        )


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: UUID,
    req: JobUpdate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> JobResponse:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, tenant_id, title, status, location, employment_type, external_ref, created_at
            FROM jobs
            WHERE id = %s AND tenant_id = %s
            """,
            (job_id, current_user.tenant_id),
        )
        existing = await cur.fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        updates: list[str] = []
        params: list[object] = []
        if req.title is not None and req.title.strip():
            updates.append("title = %s")
            params.append(req.title.strip())
        if req.location is not None:
            updates.append("location = %s")
            params.append(req.location.strip())
        if req.employment_type is not None:
            updates.append("employment_type = %s")
            params.append(req.employment_type.strip())
        if req.status is not None:
            updates.append("status = %s")
            params.append(req.status.strip())

        if updates:
            params.extend([job_id, current_user.tenant_id])
            await cur.execute(
                f"""
                UPDATE jobs
                SET {", ".join(updates)}
                WHERE id = %s AND tenant_id = %s
                RETURNING id, tenant_id, title, status, location, employment_type, external_ref, created_at
                """,
                tuple(params),
            )
            row = await cur.fetchone()
        else:
            row = existing

        await cur.execute(
            "SELECT count(id) as count FROM documents WHERE job_id = %s AND tenant_id = %s",
            (job_id, current_user.tenant_id),
        )
        doc_row = await cur.fetchone()
        cv_count = doc_row["count"] if doc_row else 0

        await conn.commit()
        return JobResponse(
            id=row["id"],
            tenant_id=row["tenant_id"],
            title=row["title"],
            status=row["status"],
            location=row["location"],
            employment_type=row["employment_type"],
            external_ref=row["external_ref"],
            created_at=row["created_at"],
            cv_count=cv_count,
        )


@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
async def delete_job(
    job_id: UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id, title FROM jobs WHERE id = %s AND tenant_id = %s",
            (job_id, current_user.tenant_id),
        )
        existing = await cur.fetchone()
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

        # 1. Delete reviews associated with screening_runs of this job
        await cur.execute(
            """
            DELETE FROM reviews
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id),
        )

        # 2. Delete screening_runs for this job (child scores/evidence cascade)
        await cur.execute(
            "DELETE FROM screening_runs WHERE job_id = %s AND tenant_id = %s", (job_id, current_user.tenant_id)
        )

        # 3. Delete the job (documents & requirement_sets cascade)
        await cur.execute(
            "DELETE FROM jobs WHERE id = %s AND tenant_id = %s",
            (job_id, current_user.tenant_id),
        )

        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'JOB_DELETE', 'job', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                str(job_id),
                f'{{"title": "{existing["title"]}"}}',
            ),
        )

        await conn.commit()
        return {"message": "Job deleted successfully", "id": str(job_id), "title": existing["title"]}
