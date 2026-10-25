import uuid

import httpx
import pytest
import pytest_asyncio

from src.domain.auth import create_access_token
from src.domain.models import UserRole
from src.infrastructure.database import get_connection

TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()

USER_A_ID = uuid.uuid4()
USER_B_ID = uuid.uuid4()


@pytest_asyncio.fixture
async def setup_two_tenants():
    async with get_connection() as conn, conn.cursor() as cur:
        # Create users for tenant A and tenant B
        await cur.execute(
            """
            INSERT INTO users (id, tenant_id, email, password_hash, role, is_active)
            VALUES (%s, %s, %s, 'hash', 'recruiter', true),
                   (%s, %s, %s, 'hash', 'recruiter', true)
            ON CONFLICT (email) DO NOTHING
            """,
            (USER_A_ID, TENANT_A, f"rec_a_{TENANT_A}@test.com", USER_B_ID, TENANT_B, f"rec_b_{TENANT_B}@test.com"),
        )

        # Create Job B
        job_b_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text, created_by)
            VALUES (%s, %s, 'Backend B', 'JD Text for B', %s)
            """,
            (job_b_id, TENANT_B, USER_B_ID),
        )

        # Create Requirement Set B (APPROVED)
        set_b_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights)
            VALUES (%s, %s, %s, 1, 'APPROVED', '{"HARD_SKILLS": 100}'::jsonb)
            """,
            (set_b_id, TENANT_B, job_b_id),
        )
        req_b_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO requirements (id, tenant_id, requirement_set_id, requirement_id, description, category, kind, importance, weight)
            VALUES (%s, %s, %s, 'R1', 'Python expert', 'HARD_SKILLS', 'SKILL', 'MUST_HAVE', 100)
            """,
            (req_b_id, TENANT_B, set_b_id),
        )

        # Create Candidate B & Document B
        cand_b_id = uuid.uuid4()
        cand_b_code = f"C-B{str(uuid.uuid4())[:6]}"
        await cur.execute(
            """
            INSERT INTO candidates (id, tenant_id, candidate_code, status)
            VALUES (%s, %s, %s, 'ACTIVE')
            """,
            (cand_b_id, TENANT_B, cand_b_code),
        )
        await cur.execute(
            """
            INSERT INTO candidate_identities (candidate_id, tenant_id, full_name, email, phone)
            VALUES (%s, %s, 'Bob B', 'bob@tenant-b.com', '0811111111')
            """,
            (cand_b_id, TENANT_B),
        )
        doc_b_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, candidate_id, original_filename, size_bytes, mime, sha256, storage_key, status)
            VALUES (%s, %s, %s, %s, 'bob_cv.pdf', 1000, 'application/pdf', 'dummyhashb', 'keyb.pdf', 'READY')
            """,
            (doc_b_id, TENANT_B, job_b_id, cand_b_id),
        )

        # Create Screening Run B
        run_b_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO screening_runs (id, tenant_id, job_id, requirement_set_id, status, as_of, versions)
            VALUES (%s, %s, %s, %s, 'DONE', '2026-10-01', '{"extractor": "1.0"}'::jsonb)
            """,
            (run_b_id, TENANT_B, job_b_id, set_b_id),
        )
        await cur.execute(
            """
            INSERT INTO candidate_scores (run_id, candidate_id, tenant_id, document_id, rank, final_score, band, recommendation)
            VALUES (%s, %s, %s, %s, 1, 95.0, 'A', 'SHORTLIST')
            """,
            (run_b_id, cand_b_id, TENANT_B, doc_b_id),
        )
        await cur.execute(
            """
            INSERT INTO requirement_scores (run_id, candidate_id, requirement_id, tenant_id, state, confidence, method)
            VALUES (%s, %s, 'R1', %s, 'STRONG', 0.95, 'rule')
            """,
            (run_b_id, cand_b_id, TENANT_B),
        )

        await conn.commit()

    token_a = create_access_token(
        {
            "sub": str(USER_A_ID),
            "tenant_id": str(TENANT_A),
            "email": f"rec_a_{TENANT_A}@test.com",
            "role": UserRole.RECRUITER.value,
        }
    )

    return {
        "token_a": token_a,
        "job_b_id": str(job_b_id),
        "cand_b_id": str(cand_b_id),
        "cand_b_code": cand_b_code,
        "run_b_id": str(run_b_id),
        "doc_b_id": str(doc_b_id),
    }


@pytest.mark.asyncio
async def test_tenant_isolation_cross_tenant_access_denied(client: httpx.AsyncClient, setup_two_tenants):
    data = setup_two_tenants
    headers_a = {"Authorization": f"Bearer {data['token_a']}"}
    job_b = data["job_b_id"]
    cand_b = data["cand_b_id"]
    cand_b_code = data["cand_b_code"]
    run_b = data["run_b_id"]

    # 1. GET /jobs/{B} -> 404
    r = await client.get(f"/api/v1/jobs/{job_b}", headers=headers_a)
    assert r.status_code == 404

    # 2. POST /jobs/{B}/screenings -> 404
    r = await client.post(f"/api/v1/jobs/{job_b}/screenings", json={"as_of": "2026-10-01"}, headers=headers_a)
    assert r.status_code == 404

    # 3. GET /jobs/{B}/screenings/latest -> 404
    r = await client.get(f"/api/v1/jobs/{job_b}/screenings/latest", headers=headers_a)
    assert r.status_code == 404

    # 4. GET /jobs/{B}/screenings/{run_b}/rankings -> 404
    r = await client.get(f"/api/v1/jobs/{job_b}/screenings/{run_b}/rankings", headers=headers_a)
    assert r.status_code == 404

    # 5. GET /jobs/{B}/screenings/{run_b}/candidates/{cand_b} -> 404
    r = await client.get(f"/api/v1/jobs/{job_b}/screenings/{run_b}/candidates/{cand_b}", headers=headers_a)
    assert r.status_code == 404

    # 6. POST /candidates/{B_cand}/reveal-identity -> 404
    r = await client.post(
        f"/api/v1/candidates/{cand_b}/reveal-identity", json={"reason": "Auditing IDOR"}, headers=headers_a
    )
    assert r.status_code == 404

    # 7. POST /candidates/C-xxxx(B)/reveal-identity -> 404
    r = await client.post(
        f"/api/v1/candidates/{cand_b_code}/reveal-identity", json={"reason": "Auditing IDOR by code"}, headers=headers_a
    )
    assert r.status_code == 404

    # 8. DELETE /candidates/{B_cand} -> 404
    r = await client.delete(f"/api/v1/candidates/{cand_b}", headers=headers_a)
    assert r.status_code == 404

    # 9. POST /jobs/{B}/requirements/manual -> 404
    r = await client.post(
        f"/api/v1/jobs/{job_b}/requirements/manual",
        json={"requirement_id": "R2", "description": "Expert in Rust"},
        headers=headers_a,
    )
    assert r.status_code == 404

    # 10. POST /jobs/{B}/requirements/approve -> 404
    r = await client.post(f"/api/v1/jobs/{job_b}/requirements/approve", headers=headers_a)
    assert r.status_code == 404

    # 11. GET /jobs/{B}/cvs/status -> 404
    r = await client.get(f"/api/v1/jobs/{job_b}/cvs/status", headers=headers_a)
    assert r.status_code == 404

    # 12. DELETE /jobs/{B}/cvs -> 404
    r = await client.delete(f"/api/v1/jobs/{job_b}/cvs", headers=headers_a)
    assert r.status_code == 404

    # 13. GET /jobs/{B}/eligibility-rules -> 404
    r = await client.get(f"/api/v1/jobs/{job_b}/eligibility-rules", headers=headers_a)
    assert r.status_code == 404

    # 14. POST /jobs/{B}/eligibility-rules -> 404
    r = await client.post(
        f"/api/v1/jobs/{job_b}/eligibility-rules",
        json={
            "rule_type": "AGE_MAX",
            "value": {"years": 28},
            "basis_category": "KARAKTERISTIK_JABATAN",
            "justification": "Operasional lapangan 5 tahun ikatan dinas",
            "reference_date": "2026-10-14",
        },
        headers=headers_a,
    )
    assert r.status_code == 404

    # 15. GET /jobs/{B}/screenings/{run_b}/eligibility-summary -> 404
    r = await client.get(f"/api/v1/jobs/{job_b}/screenings/{run_b}/eligibility-summary", headers=headers_a)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_reveal_identity_non_existent_candidate_returns_404(client: httpx.AsyncClient, setup_two_tenants):
    headers_a = {"Authorization": f"Bearer {setup_two_tenants['token_a']}"}
    fake_id = str(uuid.uuid4())
    r = await client.post(
        f"/api/v1/candidates/{fake_id}/reveal-identity", json={"reason": "Testing 404"}, headers=headers_a
    )
    assert r.status_code == 404
