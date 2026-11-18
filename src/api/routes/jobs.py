"""Create and manage TIG job openings for the authenticated tenant."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.types.json import Jsonb

from src.api.dependencies import get_current_user
from src.domain.models import JobCreate, JobResponse, JobUpdate, User
from src.domain.tig import TigConfig
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/jobs", tags=["Lowongan TIG"])

JOB_FIELDS = """
    SELECT j.id, j.title, j.status, j.location, j.employment_type, j.created_at,
           (SELECT count(*) FROM tig_applications a WHERE a.job_id = j.id) AS application_count
    FROM jobs j JOIN tig_configs c ON c.job_id = j.id
    WHERE j.tenant_id = %s
"""


async def fetch_job(cur, tenant_id: UUID, job_id: UUID) -> JobResponse:
    await cur.execute(JOB_FIELDS + " AND j.id = %s", (tenant_id, job_id))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Lowongan TIG tidak ditemukan.")
    return JobResponse.model_validate(row)


@router.get("", response_model=list[JobResponse])
async def list_jobs(user: User = Depends(get_current_user)) -> list[JobResponse]:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(JOB_FIELDS + " ORDER BY j.created_at DESC", (user.tenant_id,))
        return [JobResponse.model_validate(row) for row in await cur.fetchall()]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: UUID, user: User = Depends(get_current_user)) -> JobResponse:
    async with get_connection() as conn, conn.cursor() as cur:
        return await fetch_job(cur, user.tenant_id, job_id)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    req: JobCreate,
    user: User = Depends(get_current_user),
) -> JobResponse:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jobs (tenant_id, title, jd_text, location, employment_type, created_by)
            VALUES (%s, %s, '', %s, %s, %s) RETURNING id
            """,
            (user.tenant_id, req.title, req.location, req.employment_type, user.id),
        )
        job_id = (await cur.fetchone())["id"]
        config = TigConfig()
        if config.regular:
            config.regular.location = req.location or ""
        await cur.execute(
            "INSERT INTO tig_configs (job_id, config) VALUES (%s, %s)",
            (job_id, Jsonb(config.model_dump())),
        )
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'JOB_CREATE', 'job', %s, %s)
            """,
            (user.tenant_id, user.id, str(job_id), Jsonb({"title": req.title})),
        )
        return await fetch_job(cur, user.tenant_id, job_id)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: UUID,
    req: JobUpdate,
    user: User = Depends(get_current_user),
) -> JobResponse:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE jobs
            SET title = COALESCE(%s, title), location = COALESCE(%s, location),
                employment_type = COALESCE(%s, employment_type)
            WHERE id = %s AND tenant_id = %s
              AND EXISTS (SELECT 1 FROM tig_configs WHERE job_id = jobs.id)
            """,
            (req.title, req.location, req.employment_type, job_id, user.tenant_id),
        )
        return await fetch_job(cur, user.tenant_id, job_id)
