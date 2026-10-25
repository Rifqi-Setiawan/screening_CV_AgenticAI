"""Unit and integration tests for M6 Hardening (Candidate deletion, dispute, rate limit, metrics)."""

from __future__ import annotations

import uuid

import httpx
import pytest

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

TEST_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.mark.asyncio
async def test_metrics_endpoint(client: httpx.AsyncClient):
    res = await client.get("/metrics", headers={"Authorization": f"Bearer {settings.METRICS_TOKEN}"})
    assert res.status_code == 200
    text = res.text
    assert "cv_processed_total" in text
    assert "pipeline_stage_latency_seconds" in text
    assert "llm_tokens_total" in text
    assert "llm_cache" in text


@pytest.mark.asyncio
async def test_candidate_dispute_and_deletion_flow(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}

    # 1. Create a job, candidate, document, and profile
    job_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    cand_id = uuid.uuid4()

    cand_code = f"C-{uuid.uuid4().hex[:6]}"

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text, external_ref)
            VALUES (%s, %s, 'Dispute Test Job', 'Description', 'JD-DISPUTE')
            """,
            (job_id, TEST_TENANT),
        )
        await cur.execute(
            """
            INSERT INTO candidates (id, tenant_id, candidate_code, status)
            VALUES (%s, %s, %s, 'ACTIVE')
            """,
            (cand_id, TEST_TENANT, cand_code),
        )
        await cur.execute(
            """
            INSERT INTO candidate_identities (candidate_id, tenant_id, full_name, email, phone)
            VALUES (%s, %s, 'Test Candidate To Delete', 'test.delete@example.com', '0819999999')
            """,
            (cand_id, TEST_TENANT),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, candidate_id, original_filename, sha256, status)
            VALUES (%s, %s, %s, %s, 'test_delete_cv.pdf', 'fakehash999', 'READY')
            """,
            (doc_id, TEST_TENANT, job_id, cand_id),
        )
        await conn.commit()

    # 2. Test Objection / Dispute endpoint -> should set status to MANUAL_ONLY
    dispute_res = await client.post(
        f"/api/v1/candidates/{cand_id}/object",
        json={"reason": "Penilaian otomatis melewatkan sertifikasi AWS di halaman 2"},
        headers=headers,
    )
    assert dispute_res.status_code == 200
    assert dispute_res.json()["status"] == "MANUAL_ONLY"

    # Verify status in database
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT status FROM candidates WHERE id = %s", (cand_id,))
        cand_row = await cur.fetchone()
        assert cand_row["status"] == "MANUAL_ONLY"

        # Verify audit log was created
        await cur.execute(
            "SELECT action, target_id FROM audit_logs WHERE action = 'CANDIDATE_OBJECTION' AND target_id = %s",
            (str(cand_id),),
        )
        audit_row = await cur.fetchone()
        assert audit_row is not None

    # 3. Test Permanent Deletion (GDPR Right-to-be-Forgotten)
    del_res = await client.delete(f"/api/v1/candidates/{cand_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "DELETED"

    # 4. Verify that ALL personal data is erased and only tombstone remains
    async with get_connection() as conn, conn.cursor() as cur:
        # Candidate status is tombstone
        await cur.execute("SELECT status, deleted_at FROM candidates WHERE id = %s", (cand_id,))
        tombstone_row = await cur.fetchone()
        assert tombstone_row["status"] == "DELETED"
        assert tombstone_row["deleted_at"] is not None

        # Identity is completely removed
        await cur.execute("SELECT count(*) as cnt FROM candidate_identities WHERE candidate_id = %s", (cand_id,))
        assert (await cur.fetchone())["cnt"] == 0

        # Document is removed
        await cur.execute("SELECT count(*) as cnt FROM documents WHERE candidate_id = %s", (cand_id,))
        assert (await cur.fetchone())["cnt"] == 0

        # Audit log confirms deletion
        await cur.execute(
            "SELECT action FROM audit_logs WHERE action = 'CANDIDATE_DELETE' AND target_id = %s",
            (str(cand_id),),
        )
        assert (await cur.fetchone()) is not None
