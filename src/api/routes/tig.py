"""TIG applications from signed-in applicants and tenant-scoped staff review."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from src.api.dependencies import get_current_user, get_job_for_tenant
from src.api.middleware.rate_limiter import check_rate_limit
from src.api.routes.applicant import Applicant, get_current_applicant
from src.domain.models import User
from src.domain.tig import Application, ApplicationSubmission, Stage, StrictModel, TigConfig, score_category
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.worker.tig_prefill import prefill_form

router = APIRouter(tags=["TIG"])
public = "/api/v1/tig/apply/{job_id}"
staff = "/api/v1/jobs/{job_id}/tig"


class StageUpdate(StrictModel):
    stage: Stage


def encryption_key() -> str:
    if not settings.PII_ENCRYPTION_KEY:
        raise HTTPException(503, "Layanan lamaran belum siap.")
    return settings.PII_ENCRYPTION_KEY


async def get_public_job(cur, job_id: UUID, *, lock: bool = False):
    sql = """
        SELECT j.id, j.title, j.location, c.config
        FROM jobs j JOIN tig_configs c ON c.job_id = j.id
        WHERE j.id = %s AND j.status = 'OPEN' AND c.config->'published' = 'true'::jsonb
    """
    if lock:
        sql += " FOR SHARE OF j, c"
    await cur.execute(sql, (job_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Lowongan ini belum dibuka untuk lamaran.")
    return row


async def audit(cur, user: User, action: str, target_type: str, target_id: Any, metadata: dict) -> None:
    await cur.execute(
        """
        INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (user.tenant_id, user.id, action, target_type, str(target_id), Jsonb(metadata)),
    )


async def enqueue(cur, application_id: UUID) -> int:
    await cur.execute(
        "INSERT INTO jobs_queue (type, payload) VALUES ('tig_assessment', %s) RETURNING id",
        (Jsonb({"application_id": str(application_id)}),),
    )
    return (await cur.fetchone())["id"]


def assessment_fields(row):
    assessment = row["assessment"]
    score = assessment["score"] if assessment is not None else None
    return {
        "id": row["id"],
        "stage": row["stage"],
        "created_at": row["created_at"],
        "assessed_at": row["assessed_at"],
        "score": score,
        "category": score_category(score),
        "assessment_status": row["assessment_status"],
    }


@router.get("/api/v1/tig/jobs", dependencies=[Depends(check_rate_limit(60))])
async def open_jobs(response: Response):
    """Openings that accept applications, for the applicant portal."""
    response.headers["Cache-Control"] = "no-store"
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT j.id, j.title, j.location, j.employment_type, c.config
            FROM jobs j JOIN tig_configs c ON c.job_id = j.id
            WHERE j.status = 'OPEN' AND c.config->'published' = 'true'::jsonb
            ORDER BY j.created_at DESC
            """
        )
        rows = await cur.fetchall()
    return [
        {
            "id": row["id"],
            "title": row["title"],
            "location": row["location"],
            "employment_type": row["employment_type"],
            "options": [option.title for option in TigConfig.model_validate(row["config"]).program],
        }
        for row in rows
    ]


@router.get(public, dependencies=[Depends(check_rate_limit(60))])
async def public_job(job_id: UUID, response: Response):
    response.headers["Cache-Control"] = "no-store"
    async with get_connection() as conn, conn.cursor() as cur:
        row = await get_public_job(cur, job_id)
    config = TigConfig.model_validate(row["config"])
    return {"title": row["title"], "location": row["location"], "options": [option.title for option in config.program]}


_prefill_slots = asyncio.Semaphore(2)


@router.post(public + "/prefill", dependencies=[Depends(check_rate_limit(5))])
async def prefill(
    job_id: UUID,
    response: Response,
    file: UploadFile = File(...),
    applicant: Applicant = Depends(get_current_applicant),
):
    response.headers["Cache-Control"] = "no-store"
    async with get_connection() as conn, conn.cursor() as cur:
        await get_public_job(cur, job_id)
    limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if (file.size is not None and file.size > limit) or len(content := await file.read(limit + 1)) > limit:
        raise HTTPException(413, f"Ukuran CV maksimal {settings.MAX_UPLOAD_SIZE_MB} MB.")
    if _prefill_slots.locked():
        raise HTTPException(503, "Pembacaan CV sedang sibuk. Coba lagi atau isi formulir manual.")
    async with _prefill_slots:
        return await asyncio.to_thread(prefill_form, content)


ALREADY_APPLIED = "Anda sudah mengirim lamaran untuk lowongan ini. Pantau statusnya di halaman Lamaran saya."


@router.post(public, status_code=202, dependencies=[Depends(check_rate_limit(8))])
async def submit(job_id: UUID, submission: ApplicationSubmission, applicant: Applicant = Depends(get_current_applicant)):
    key = encryption_key()
    application = Application.model_validate(
        {**submission.model_dump(exclude={"consent", "fresh_graduate"}), "consent_at": datetime.now(timezone.utc).isoformat()}
    )
    application_id = uuid4()
    try:
        async with get_connection() as conn, conn.cursor() as cur:
            row = await get_public_job(cur, job_id, lock=True)
            config = TigConfig.model_validate(row["config"])
            options = {option.title for option in config.program}
            priority = application.priority
            if len(set(priority)) != len(priority) or set(priority) - options:
                raise HTTPException(422, "Urutan prioritas posisi tidak valid.")
            await cur.execute(
                "SELECT 1 FROM tig_applications WHERE job_id = %s AND applicant_id = %s", (job_id, applicant.id)
            )
            if await cur.fetchone():
                raise HTTPException(409, ALREADY_APPLIED)
            queue_id = await enqueue(cur, application_id)
            await cur.execute(
                """
                INSERT INTO tig_applications (id, job_id, form, assessment_config, queue_id, applicant_id)
                VALUES (%s, %s, pgp_sym_encrypt(%s, %s), %s, %s, %s)
                """,
                (
                    application_id,
                    job_id,
                    application.model_dump_json(),
                    key,
                    Jsonb(row["config"]),
                    queue_id,
                    applicant.id,
                ),
            )
    except UniqueViolation as error:
        raise HTTPException(409, ALREADY_APPLIED) from error
    return {"application_id": application_id, "stage": "Seleksi"}


CV_TYPES = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"),
    (b"\xd0\xcf\x11\xe0", "application/msword", ".doc"),
)


def cv_type(content: bytes) -> tuple[str, str] | None:
    """(content type, extension) from the file's own signature, never from the name or header the client sent."""
    return next(((kind, ext) for magic, kind, ext in CV_TYPES if content.startswith(magic)), None)


def clean_filename(name: str | None, extension: str) -> str:
    base = re.split(r"[\\/]", name or "")[-1]
    base = re.sub(r'[\x00-\x1f\x7f"<>|:*?]', "", base).strip(" .")[:120]
    if not base.lower().endswith(extension):
        base = (base.rsplit(".", 1)[0] if "." in base else base) or "cv"
        base += extension
    return base


@router.put(public + "/cv", dependencies=[Depends(check_rate_limit(5))])
async def upload_cv(
    job_id: UUID,
    response: Response,
    file: UploadFile = File(...),
    applicant: Applicant = Depends(get_current_applicant),
):
    """Keep the original file of the applicant's own application, encrypted; one file per application."""
    response.headers["Cache-Control"] = "no-store"
    key = encryption_key()
    limit = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if (file.size is not None and file.size > limit) or len(content := await file.read(limit + 1)) > limit:
        raise HTTPException(413, f"Ukuran CV maksimal {settings.MAX_UPLOAD_SIZE_MB} MB.")
    kind = cv_type(content)
    if not kind:
        raise HTTPException(415, "Berkas harus berupa PDF atau Word (.doc, .docx).")
    filename = clean_filename(file.filename, kind[1])
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id FROM tig_applications WHERE job_id = %s AND applicant_id = %s", (job_id, applicant.id)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Kirim lamaran untuk lowongan ini terlebih dahulu.")
        await cur.execute(
            """
            INSERT INTO tig_application_cvs (application_id, filename, content_type, size_bytes, content)
            VALUES (%s, %s, %s, %s, pgp_sym_encrypt_bytea(%s, %s))
            ON CONFLICT (application_id) DO UPDATE
            SET filename = EXCLUDED.filename, content_type = EXCLUDED.content_type,
                size_bytes = EXCLUDED.size_bytes, content = EXCLUDED.content, created_at = now()
            """,
            (row["id"], filename, kind[0], len(content), content, key),
        )
    return {"filename": filename, "size_bytes": len(content), "content_type": kind[0]}


@router.get(staff + "/config")
async def get_config(job_id: UUID, user: User = Depends(get_current_user)):
    async with get_connection() as conn, conn.cursor() as cur:
        job = await get_job_for_tenant(cur, job_id, user.tenant_id)
    return {
        "config": job["config"],
        "can_edit": True,
        "job_status": job["status"],
    }


@router.put(staff + "/config")
async def save_config(job_id: UUID, config: TigConfig, user: User = Depends(get_current_user)):
    async with get_connection() as conn, conn.cursor() as cur:
        job = await get_job_for_tenant(cur, job_id, user.tenant_id, lock=True)
        if config.published:
            encryption_key()
            await cur.execute("UPDATE jobs SET status = 'OPEN' WHERE id = %s", (job_id,))
        await cur.execute("UPDATE tig_configs SET config = %s WHERE job_id = %s", (Jsonb(config.model_dump()), job_id))
        await audit(
            cur,
            user,
            "TIG_CONFIG_UPDATE",
            "job",
            job_id,
            {"published": config.published, "mode": "regular" if config.regular else "program"},
        )

    return {"config": config, "can_edit": True, "job_status": "OPEN" if config.published else job["status"]}


@router.get(staff + "/applications")
async def list_applications(job_id: UUID, response: Response, user: User = Depends(get_current_user)):
    response.headers["Cache-Control"] = "no-store"
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, user.tenant_id)
        await cur.execute(
            """
            SELECT a.id, a.stage, a.assessment, a.assessed_at, a.created_at, CASE WHEN a.assessment IS NOT NULL THEN 'DONE' ELSE q.status END AS assessment_status
            FROM tig_applications a JOIN jobs_queue q ON q.id = a.queue_id
            WHERE a.job_id = %s ORDER BY a.created_at DESC
            """,
            (job_id,),
        )
        return {
            "applications": [assessment_fields(row) for row in await cur.fetchall()],
            "can_edit": True,
        }


async def require_application(cur, job_id: UUID, application_id: UUID, *, lock: bool = False):
    sql = """
        SELECT a.id, a.stage, a.assessment, a.assessed_at, a.created_at,
               CASE WHEN a.assessment IS NOT NULL THEN 'DONE' ELSE q.status END AS assessment_status
        FROM tig_applications a JOIN jobs_queue q ON q.id = a.queue_id
        WHERE a.job_id = %s AND a.id = %s
    """
    if lock:
        sql += " FOR UPDATE OF a"
    await cur.execute(sql, (job_id, application_id))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Lamaran tidak ditemukan.")
    return row


@router.get(staff + "/applications/{application_id}")
async def application_detail(
    job_id: UUID,
    application_id: UUID,
    response: Response,
    user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "no-store"
    key = encryption_key()
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, user.tenant_id)
        row = await require_application(cur, job_id, application_id)
        await cur.execute(
            """
            SELECT pgp_sym_decrypt(form, %s) AS form, assessment_config, assessment_history
            FROM tig_applications WHERE id = %s AND job_id = %s
            """,
            (key, application_id, job_id),
        )
        encrypted_row = await cur.fetchone()
        if not encrypted_row:
            raise HTTPException(404, "Lamaran tidak ditemukan.")
        await cur.execute(
            "SELECT filename, size_bytes, content_type FROM tig_application_cvs WHERE application_id = %s", (application_id,)
        )
        cv = await cur.fetchone()
        # Viewing the decrypted form is an identity access and is logged.
        await audit(cur, user, "TIG_APPLICATION_VIEW", "tig_application", application_id, {})
        return {
            "cv": cv,
            **assessment_fields(row),
            "assessment": row["assessment"],
            "assessment_config": encrypted_row["assessment_config"],
            "assessment_history": encrypted_row["assessment_history"],
            "form": Application.model_validate_json(encrypted_row["form"]),
        }


@router.get(staff + "/applications/{application_id}/cv")
async def application_cv(
    job_id: UUID,
    application_id: UUID,
    user: User = Depends(get_current_user),
):
    key = encryption_key()
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, user.tenant_id)
        await require_application(cur, job_id, application_id)
        await cur.execute(
            """
            SELECT filename, content_type, pgp_sym_decrypt_bytea(content, %s) AS content
            FROM tig_application_cvs WHERE application_id = %s
            """,
            (key, application_id),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Pelamar tidak melampirkan CV.")
        # Opening the original file is an identity access and is logged, like viewing the form.
        await audit(cur, user, "TIG_CV_VIEW", "tig_application", application_id, {})
    inline = row["content_type"] == "application/pdf"
    return Response(
        bytes(row["content"]),
        media_type=row["content_type"],
        headers={
            "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(row['filename'])}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.patch(staff + "/applications/{application_id}")
async def update_stage(
    job_id: UUID,
    application_id: UUID,
    body: StageUpdate,
    user: User = Depends(get_current_user),
):
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, user.tenant_id)
        await require_application(cur, job_id, application_id, lock=True)
        await cur.execute("UPDATE tig_applications SET stage = %s WHERE id = %s", (body.stage, application_id))
        await audit(cur, user, "TIG_STAGE_UPDATE", "tig_application", application_id, {"stage": body.stage})
    return {"stage": body.stage}


@router.post(staff + "/applications/{application_id}/rescore", status_code=202)
async def rescore(job_id: UUID, application_id: UUID, user: User = Depends(get_current_user)):
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, user.tenant_id)
        row = await require_application(cur, job_id, application_id, lock=True)
        if row["assessment_status"] in ("PENDING", "RUNNING"):
            raise HTTPException(409, "Penilaian masih diproses.")
        queue_id = await enqueue(cur, application_id)
        # The previous result is kept so HR can compare scores across reassessments.
        await cur.execute(
            """
            UPDATE tig_applications
            SET assessment_history = CASE WHEN assessment IS NULL THEN assessment_history
                    ELSE assessment_history || jsonb_build_array(jsonb_build_object(
                        'assessment', assessment, 'assessed_at', assessed_at,
                        'replaced_at', now(), 'replaced_by', %s::text))
                    END,
                queue_id = %s, assessment = NULL, assessed_at = NULL
            WHERE id = %s
            """,
            (user.email, queue_id, application_id),
        )
        await audit(
            cur,
            user,
            "TIG_RESCORE",
            "tig_application",
            application_id,
            {"previous_score": assessment_fields(row)["score"]},
        )
    return {"assessment_status": "PENDING"}
