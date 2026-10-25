import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.worker.processor import process_document
from src.worker.sanitizer import SanitizeResult


@pytest.mark.asyncio
async def test_processor_error_sets_needs_review_and_rolls_back():
    test_tenant = uuid.uuid4()
    doc_id = uuid.uuid4()
    job_id = uuid.uuid4()

    # Create dummy file in storage vault
    vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(test_tenant)
    vault_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"test_err_{doc_id}.pdf"
    (vault_dir / storage_key).write_bytes(b"%PDF-1.4 dummy valid header")

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (id, tenant_id, email, password_hash, role)
            VALUES (%s, %s, %s, 'hash', 'recruiter')
            ON CONFLICT (email) DO NOTHING
            """,
            (uuid.uuid4(), test_tenant, f"u_{test_tenant}@test.com"),
        )
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text)
            VALUES (%s, %s, 'Job', 'JD')
            """,
            (job_id, test_tenant),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status)
            VALUES (%s, %s, %s, 'corrupt.pdf', 20, 'sha256dummy', %s, 'PROCESSING')
            """,
            (doc_id, test_tenant, job_id, storage_key),
        )
        await conn.commit()

    mock_san = SanitizeResult(
        is_valid=True, status="READY", extracted_text="Sample text content", sha256="abc", file_type="pdf"
    )

    # Mock extract_candidate_profile to raise an unexpected runtime error mid-transaction
    with (
        patch("src.worker.processor.sanitize_file", return_value=mock_san),
        patch("src.worker.processor.extract_candidate_profile", side_effect=RuntimeError("Corrupted PDF structure")),
    ):
        res = await process_document(doc_id)
        assert res["status"] == "NEEDS_REVIEW"
        assert any("PROCESSING_ERROR" in r for r in res["reasons"])

    # Verify status in database is NEEDS_REVIEW, NOT stuck in PROCESSING
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT status, reasons FROM documents WHERE id = %s", (doc_id,))
        row = await cur.fetchone()
        assert row["status"] == "NEEDS_REVIEW"
        assert any("PROCESSING_ERROR" in r for r in row["reasons"])


@pytest.mark.asyncio
async def test_processor_deduplicates_candidate_by_email():
    test_tenant = uuid.uuid4()
    job_id = uuid.uuid4()
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()

    vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(test_tenant)
    vault_dir.mkdir(parents=True, exist_ok=True)
    k1 = f"test_doc1_{doc1_id}.pdf"
    k2 = f"test_doc2_{doc2_id}.pdf"
    (vault_dir / k1).write_bytes(b"%PDF-1.4 content 1")
    (vault_dir / k2).write_bytes(b"%PDF-1.4 content 2")

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text)
            VALUES (%s, %s, 'Job Dedup', 'JD')
            """,
            (job_id, test_tenant),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status)
            VALUES (%s, %s, %s, 'doc1.pdf', 10, 'sha1', %s, 'PROCESSING')
            """,
            (doc1_id, test_tenant, job_id, k1),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status)
            VALUES (%s, %s, %s, 'doc2.pdf', 10, 'sha2', %s, 'PROCESSING')
            """,
            (doc2_id, test_tenant, job_id, k2),
        )
        await conn.commit()

    mock_profile = {
        "identity": {
            "full_name": "Alice Smith",
            "email": "alice.smith@deduptest.com",
            "phone": "+628111222333",
            "other_personal": {},
        },
        "headline": "Python Dev",
        "summary": "Experienced engineer",
        "experiences": [],
        "education": [],
        "skills": ["python"],
    }
    mock_san1 = SanitizeResult(
        is_valid=True,
        status="READY",
        extracted_text="Alice Smith initial CV Python backend engineer",
        sha256="abc1",
        file_type="pdf",
    )
    mock_san2 = SanitizeResult(
        is_valid=True,
        status="READY",
        extracted_text="Alice Smith updated CV with Python, FastAPI and Kubernetes",
        sha256="abc2",
        file_type="pdf",
    )

    with (
        patch("src.worker.processor.sanitize_file", side_effect=[mock_san1, mock_san2]),
        patch("src.worker.processor.extract_candidate_profile", return_value=mock_profile),
        patch("src.worker.processor.embed_texts", return_value=[[0.1] * 640]),
    ):
        res1 = await process_document(doc1_id)
        assert res1["status"] == "READY"

        res2 = await process_document(doc2_id)
        assert res2["status"] == "READY"

    # Both documents must have the same candidate_id
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT candidate_id FROM documents WHERE id IN (%s, %s)", (doc1_id, doc2_id))
        cand_ids = [r["candidate_id"] for r in await cur.fetchall()]
        assert len(cand_ids) == 2
        assert cand_ids[0] == cand_ids[1]
