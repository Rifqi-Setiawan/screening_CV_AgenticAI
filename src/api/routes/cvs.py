"""CV batch upload, processing status inspection, and evaluation export endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status

from src.api.dependencies import get_current_user, get_job_for_tenant, require_role
from src.domain.models import User, UserRole
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger
from src.worker.processor import process_document

router = APIRouter(tags=["CV Ingestion"])


async def _run_batch_processing(doc_ids: list[uuid.UUID]):
    sem = asyncio.Semaphore(3)

    async def _worker(did: uuid.UUID):
        async with sem:
            try:
                await process_document(did)
            except Exception as e:
                logger.error(f"Async processing error for doc {did}: {e}")

    await asyncio.gather(*[_worker(did) for did in doc_ids])


@router.post("/api/v1/jobs/{job_id}/cvs", status_code=status.HTTP_202_ACCEPTED)
async def upload_cvs(
    job_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    # Verify job exists for tenant
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

    vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(current_user.tenant_id)
    vault_dir.mkdir(parents=True, exist_ok=True)

    extracted_items: list[tuple[str, bytes]] = []

    for f in files:
        fname = f.filename or "unknown"
        data = await f.read()

        # If file is a ZIP archive, unpack entries
        if fname.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for zinfo in z.infolist():
                        if (
                            zinfo.is_dir()
                            or "__macosx" in zinfo.filename.lower()
                            or Path(zinfo.filename).name.startswith(".")
                        ):
                            continue
                        leaf_name = Path(zinfo.filename).name
                        if leaf_name.lower().endswith((".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg")):
                            extracted_items.append((leaf_name, z.read(zinfo.filename)))
            except Exception as e:
                logger.error(f"Failed to unpack zip {fname}: {e}")
        else:
            extracted_items.append((fname, data))

    if not extracted_items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid CV documents found in upload")

    created_docs = []

    async with get_connection() as conn, conn.cursor() as cur:
        for fname, content in extracted_items:
            sha256 = hashlib.sha256(content).hexdigest()
            ext = Path(fname).suffix.lstrip(".").lower() or "bin"
            storage_key = f"{sha256}.{ext}"
            file_path = vault_dir / storage_key

            # Save file to vault with 0600 permissions
            if not file_path.exists():
                file_path.write_bytes(content)
                file_path.chmod(0o600)

            # Check if duplicate sha256 already exists in this job
            await cur.execute(
                """
                SELECT id, original_filename
                FROM documents
                WHERE job_id = %s AND sha256 = %s AND status <> 'DUPLICATE'
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (job_id, sha256),
            )
            existing_dup = await cur.fetchone()

            doc_id = uuid.uuid4()
            initial_status = "DUPLICATE" if existing_dup else "RECEIVED"
            dup_id = existing_dup["id"] if existing_dup else None

            await cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, job_id, original_filename, size_bytes, mime, sha256, storage_key, status, duplicate_of
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, original_filename, status
                """,
                (
                    doc_id,
                    current_user.tenant_id,
                    job_id,
                    fname,
                    len(content),
                    f"application/{ext}",
                    sha256,
                    storage_key,
                    initial_status,
                    dup_id,
                ),
            )
            doc_row = await cur.fetchone()

            # Enqueue into jobs_queue if not duplicate
            if initial_status != "DUPLICATE":
                await cur.execute(
                    """
                    INSERT INTO jobs_queue (type, payload)
                    VALUES ('ingest_cv', %s)
                    """,
                    (json.dumps({"document_id": str(doc_id)}),),
                )

            created_docs.append(
                {
                    "id": str(doc_row["id"]),
                    "filename": doc_row["original_filename"],
                    "status": initial_status,
                }
            )

        await conn.commit()

    # Dispatch asynchronous background extraction to prevent HTTP timeout
    pending_ids = [uuid.UUID(d["id"]) for d in created_docs if d["status"] != "DUPLICATE"]
    if pending_ids:
        background_tasks.add_task(_run_batch_processing, pending_ids)

    return {
        "status": "ACCEPTED",
        "job_id": str(job_id),
        "total_files": len(created_docs),
        "files": created_docs,
    }


@router.get("/api/v1/jobs/{job_id}/cvs/status")
async def get_cvs_status(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            """
            SELECT d.id, d.original_filename, d.status, d.reasons, d.flags, d.duplicate_of,
                   d2.original_filename as duplicate_of_name,
                   cp.quality
            FROM documents d
            LEFT JOIN documents d2 ON d.duplicate_of = d2.id
            LEFT JOIN candidate_profiles cp ON cp.document_id = d.id
            WHERE d.job_id = %s AND d.tenant_id = %s
            ORDER BY d.created_at ASC
            """,
            (job_id, current_user.tenant_id),
        )
        rows = await cur.fetchall()

        summary: dict[str, int] = {}
        items = []
        for r in rows:
            st = r["status"]
            summary[st] = summary.get(st, 0) + 1
            quality = r["quality"] or {}
            reasons = list(r["reasons"] or [])
            flags = list(set(list(r["flags"] or []) + list(quality.get("flags", []))))
            items.append(
                {
                    "id": str(r["id"]),
                    "filename": r["original_filename"],
                    "status": st,
                    "reasons": reasons,
                    "flags": flags,
                    "duplicate_of": r["duplicate_of_name"],
                }
            )

        return {
            "job_id": str(job_id),
            "total": len(rows),
            "summary": summary,
            "documents": items,
            "files": items,
        }


@router.delete("/api/v1/jobs/{job_id}/cvs", status_code=status.HTTP_200_OK)
async def clear_job_cvs(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    """Clears all uploaded documents, candidate profiles, screening runs, and evaluation artifacts for a job."""
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        # 1. Cancel / delete any pending jobs in jobs_queue for this job
        await cur.execute(
            """
            DELETE FROM jobs_queue
            WHERE (payload->>'job_id') = %s
            """,
            (str(job_id),),
        )

        # 2. Break self-referential / circular foreign keys
        await cur.execute(
            """
            UPDATE documents SET duplicate_of = NULL
            WHERE job_id = %s AND tenant_id = %s
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            UPDATE screening_runs SET parent_run_id = NULL
            WHERE job_id = %s AND tenant_id = %s
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            UPDATE experience_entries SET header_atom_id = NULL
            WHERE profile_id IN (
                SELECT id FROM candidate_profiles 
                WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
                  AND tenant_id = %s
            )
            """,
            (job_id, current_user.tenant_id, current_user.tenant_id),
        )

        # 3. Delete screening run downstream tables
        await cur.execute(
            """
            DELETE FROM critic_reviews
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM facet_judgments
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM domain_durations
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM candidate_scores
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
               OR document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id, job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM requirement_scores
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM evidence
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM reviews
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM candidate_eligibility
            WHERE run_id IN (SELECT id FROM screening_runs WHERE job_id = %s AND tenant_id = %s)
               OR document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id, job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM screening_runs
            WHERE job_id = %s AND tenant_id = %s
            """,
            (job_id, current_user.tenant_id),
        )

        # 4. Delete profile, atom, experience, and skill downstream tables
        await cur.execute(
            """
            DELETE FROM experience_domain_allocations
            WHERE experience_id IN (
                SELECT id FROM experience_entries
                WHERE profile_id IN (
                    SELECT id FROM candidate_profiles 
                    WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
                      AND tenant_id = %s
                )
            )
            """,
            (job_id, current_user.tenant_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM atom_tags
            WHERE atom_id IN (
                SELECT id FROM evidence_atoms
                WHERE profile_id IN (
                    SELECT id FROM candidate_profiles 
                    WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
                      AND tenant_id = %s
                )
            )
            """,
            (job_id, current_user.tenant_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM experience_entries
            WHERE profile_id IN (
                SELECT id FROM candidate_profiles 
                WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
                  AND tenant_id = %s
            )
            """,
            (job_id, current_user.tenant_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM evidence_atoms
            WHERE profile_id IN (
                SELECT id FROM candidate_profiles 
                WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
                  AND tenant_id = %s
            )
            """,
            (job_id, current_user.tenant_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM profile_chunks
            WHERE profile_id IN (
                SELECT id FROM candidate_profiles 
                WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
                  AND tenant_id = %s
            ) AND tenant_id = %s
            """,
            (job_id, current_user.tenant_id, current_user.tenant_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM skill_mentions
            WHERE profile_id IN (
                SELECT id FROM candidate_profiles 
                WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
                  AND tenant_id = %s
            )
            """,
            (job_id, current_user.tenant_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM candidate_profiles
            WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
              AND tenant_id = %s
            """,
            (job_id, current_user.tenant_id, current_user.tenant_id),
        )

        # 5. Delete document-level artifacts and documents
        await cur.execute(
            """
            DELETE FROM redaction_offset_maps
            WHERE document_id IN (SELECT id FROM documents WHERE job_id = %s AND tenant_id = %s)
            """,
            (job_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            DELETE FROM documents
            WHERE job_id = %s AND tenant_id = %s
            """,
            (job_id, current_user.tenant_id),
        )
        await conn.commit()

    return {"status": "SUCCESS", "message": "All CVs for this job opening have been cleared successfully."}


@router.delete("/api/v1/jobs/{job_id}/cvs/{document_id}", status_code=status.HTTP_200_OK)
async def delete_single_cv(
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    """Deletes a single candidate CV and all its associated artifacts from the job."""
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        # 1. Cancel / delete any pending queue tasks for this document
        await cur.execute(
            """
            DELETE FROM jobs_queue
            WHERE (payload->>'document_id') = %s
            """,
            (str(document_id),),
        )

        # 2. Clear duplicate references
        await cur.execute(
            """
            UPDATE documents SET duplicate_of = NULL
            WHERE duplicate_of = %s AND tenant_id = %s
            """,
            (document_id, current_user.tenant_id),
        )

        # 3. Delete downstream candidate scores and eligibility for this document
        await cur.execute(
            """
            DELETE FROM candidate_scores
            WHERE document_id = %s
            """,
            (document_id,),
        )
        await cur.execute(
            """
            DELETE FROM candidate_eligibility
            WHERE document_id = %s
            """,
            (document_id,),
        )

        # 4. Find candidate profile
        await cur.execute(
            "SELECT id FROM candidate_profiles WHERE document_id = %s AND tenant_id = %s",
            (document_id, current_user.tenant_id),
        )
        prof_rows = await cur.fetchall()
        for p in prof_rows:
            p_id = p["id"]
            await cur.execute("UPDATE experience_entries SET header_atom_id = NULL WHERE profile_id = %s", (p_id,))
            await cur.execute("DELETE FROM atom_evaluations WHERE atom_id IN (SELECT id FROM evidence_atoms WHERE profile_id = %s)", (p_id,))
            await cur.execute("DELETE FROM evidence_atoms WHERE profile_id = %s", (p_id,))
            await cur.execute("DELETE FROM profile_chunks WHERE profile_id = %s", (p_id,))
            await cur.execute("DELETE FROM experience_entries WHERE profile_id = %s", (p_id,))
            await cur.execute("DELETE FROM education_entries WHERE profile_id = %s", (p_id,))
            await cur.execute("DELETE FROM skill_mentions WHERE profile_id = %s", (p_id,))
            await cur.execute("DELETE FROM candidate_profiles WHERE id = %s", (p_id,))

        # 5. Delete redaction offset maps and document
        await cur.execute("DELETE FROM redaction_offset_maps WHERE document_id = %s", (document_id,))
        await cur.execute(
            "DELETE FROM documents WHERE id = %s AND job_id = %s AND tenant_id = %s RETURNING original_filename, storage_key",
            (document_id, job_id, current_user.tenant_id),
        )
        deleted_doc = await cur.fetchone()
        await conn.commit()

        if deleted_doc:
            try:
                storage_path = Path(settings.STORAGE_VAULT_PATH) / str(current_user.tenant_id) / deleted_doc["storage_key"]
                if storage_path.exists():
                    storage_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove file from vault: {e}")

        return {"status": "SUCCESS", "deleted_document_id": str(document_id)}


@router.post("/api/v1/jobs/{job_id}/cvs/{document_id}/retry", status_code=status.HTTP_200_OK)
async def retry_single_cv(
    job_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    """Retries ingestion processing for a single document."""
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        # Reset document status
        await cur.execute(
            """
            UPDATE documents
            SET status = 'RECEIVED', reasons = '{}', flags = '{}'
            WHERE id = %s AND job_id = %s AND tenant_id = %s
            RETURNING id, original_filename
            """,
            (document_id, job_id, current_user.tenant_id),
        )
        doc = await cur.fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Insert into jobs_queue
        await cur.execute(
            """
            INSERT INTO jobs_queue (id, tenant_id, type, status, payload, max_attempts)
            VALUES (gen_random_uuid(), %s, 'ingest_cv', 'PENDING', %s, 3)
            """,
            (
                current_user.tenant_id,
                json.dumps({
                    "document_id": str(document_id),
                    "tenant_id": str(current_user.tenant_id),
                    "job_id": str(job_id),
                }),
            ),
        )
        await conn.commit()

        return {"status": "QUEUED", "document_id": str(document_id), "message": "Proses ulang berkas dijadwalkan."}


@router.get("/api/v1/jobs/{job_id}/extraction-export")
@router.get("/api/v1/jobs/{job_id}/cvs/extraction-export")
async def export_extractions(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Returns extraction output formatted exactly for `evaluate.py --extraction`."""
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            """
            SELECT d.original_filename, cp.profile
            FROM documents d
            JOIN candidate_profiles cp ON cp.document_id = d.id
            WHERE d.job_id = %s AND d.tenant_id = %s AND d.status IN ('READY', 'SCORED')
            """,
            (job_id, current_user.tenant_id),
        )
        rows = await cur.fetchall()

        files_map = {}
        for r in rows:
            prof = r["profile"] or {}
            experiences = []
            for exp in prof.get("experiences", []):
                start_obj = exp.get("start")
                end_obj = exp.get("end")
                start_val = start_obj.get("value") if isinstance(start_obj, dict) else start_obj
                end_val = end_obj.get("value") if isinstance(end_obj, dict) else end_obj
                experiences.append(
                    {
                        "title": exp.get("title"),
                        "organization": exp.get("organization"),
                        "start": start_val,
                        "end": end_val,
                        "employment_type": exp.get("employment_type"),
                    }
                )

            education = [{"level": ed.get("level")} for ed in prof.get("education", [])]
            certifications = prof.get("certifications", [])
            skills = prof.get("skills", [])

            files_map[r["original_filename"]] = {
                "experiences": experiences,
                "education": education,
                "certifications": certifications,
                "skills": skills,
            }

        return {"files": files_map}
