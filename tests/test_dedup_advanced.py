import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.worker.processor import process_document
from src.worker.sanitizer import SanitizeResult


@pytest.mark.asyncio
async def test_duplicate_text_content_marks_duplicate():
    test_tenant = uuid.uuid4()
    job_id = uuid.uuid4()
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()

    vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(test_tenant)
    vault_dir.mkdir(parents=True, exist_ok=True)
    k1 = f"doc1_{doc1_id}.pdf"
    k2 = f"doc2_{doc2_id}.pdf"
    (vault_dir / k1).write_bytes(b"%PDF-1.4 original file bytes")
    (vault_dir / k2).write_bytes(b"%PDF-1.4 re-exported different bytes")

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'Job Text Dedup', 'JD')",
            (job_id, test_tenant),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status)
            VALUES (%s, %s, %s, 'cv_v1.pdf', 100, 'sha_unique_1', %s, 'PROCESSING')
            """,
            (doc1_id, test_tenant, job_id, k1),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status)
            VALUES (%s, %s, %s, 'cv_v2.pdf', 150, 'sha_unique_2', %s, 'PROCESSING')
            """,
            (doc2_id, test_tenant, job_id, k2),
        )
        await conn.commit()

    identical_text = "Budi Santoso is a Software Engineer with Python and Docker skills."
    mock_san1 = SanitizeResult(
        is_valid=True, status="READY", extracted_text=identical_text, sha256="sha_unique_1", file_type="pdf"
    )
    mock_san2 = SanitizeResult(
        is_valid=True, status="READY", extracted_text=identical_text, sha256="sha_unique_2", file_type="pdf"
    )

    mock_profile = {
        "identity": {
            "full_name": "Budi Santoso",
            "email": "budi@dedup.com",
            "phone": "081299991111",
            "other_personal": {},
        },
        "headline": "Software Engineer",
        "summary": "Experienced dev",
        "experiences": [],
        "education": [],
        "skills": ["python"],
    }

    with patch("src.worker.processor.embed_texts", return_value=[[0.1] * 640]):
        with (
            patch("src.worker.processor.sanitize_file", return_value=mock_san1),
            patch("src.worker.processor.extract_candidate_profile", return_value=mock_profile),
        ):
            res1 = await process_document(doc1_id)
            assert res1["status"] == "READY"

        with (
            patch("src.worker.processor.sanitize_file", return_value=mock_san2),
            patch("src.worker.processor.extract_candidate_profile", return_value=mock_profile),
        ):
            res2 = await process_document(doc2_id)
            assert res2["status"] == "DUPLICATE"


@pytest.mark.asyncio
async def test_different_cv_same_candidate_gets_possible_duplicate_flag():
    test_tenant = uuid.uuid4()
    job_id = uuid.uuid4()
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()

    vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(test_tenant)
    vault_dir.mkdir(parents=True, exist_ok=True)
    k1 = f"cvA_{doc1_id}.pdf"
    k2 = f"cvB_{doc2_id}.pdf"
    (vault_dir / k1).write_bytes(b"%PDF-1.4 file A")
    (vault_dir / k2).write_bytes(b"%PDF-1.4 file B")

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'Job Multi CV', 'JD')",
            (job_id, test_tenant),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status)
            VALUES (%s, %s, %s, 'cv_early.pdf', 100, 'sha_A', %s, 'PROCESSING')
            """,
            (doc1_id, test_tenant, job_id, k1),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status)
            VALUES (%s, %s, %s, 'cv_later.pdf', 120, 'sha_B', %s, 'PROCESSING')
            """,
            (doc2_id, test_tenant, job_id, k2),
        )
        await conn.commit()

    # Different text, but same candidate identity email
    san_a = SanitizeResult(
        is_valid=True, status="READY", extracted_text="Early version with Python", sha256="sha_A", file_type="pdf"
    )
    san_b = SanitizeResult(
        is_valid=True,
        status="READY",
        extracted_text="Updated version with Python, FastAPI and Go",
        sha256="sha_B",
        file_type="pdf",
    )

    prof_a = {
        "identity": {
            "full_name": "Dewi Sartika",
            "email": "dewi@multicv.com",
            "phone": "0812334455",
            "other_personal": {},
        },
        "experiences": [],
        "education": [],
        "skills": ["python"],
    }
    prof_b = {
        "identity": {
            "full_name": "Dewi Sartika",
            "email": "dewi@multicv.com",
            "phone": "0812334455",
            "other_personal": {},
        },
        "experiences": [],
        "education": [],
        "skills": ["python", "go"],
    }

    with patch("src.worker.processor.embed_texts", return_value=[[0.1] * 640]):
        with (
            patch("src.worker.processor.sanitize_file", return_value=san_a),
            patch("src.worker.processor.extract_candidate_profile", return_value=prof_a),
        ):
            res1 = await process_document(doc1_id)
            assert res1["status"] == "READY"

        with (
            patch("src.worker.processor.sanitize_file", return_value=san_b),
            patch("src.worker.processor.extract_candidate_profile", return_value=prof_b),
        ):
            res2 = await process_document(doc2_id)
            assert res2["status"] == "READY"

    # Second document must have flag POSSIBLE_DUPLICATE_OF:<candidate_code>
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT flags FROM documents WHERE id = %s", (doc2_id,))
        doc2_row = await cur.fetchone()
        assert any(f.startswith("POSSIBLE_DUPLICATE_OF:") for f in doc2_row["flags"])
