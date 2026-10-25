import json
import uuid

import httpx
import pytest
import pytest_asyncio

from src.domain.auth import create_access_token
from src.domain.models import UserRole
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

TEST_TENANT = uuid.uuid4()
ADMIN_USER = uuid.uuid4()


@pytest_asyncio.fixture
async def setup_env():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (id, tenant_id, email, password_hash, role)
            VALUES (%s, %s, %s, 'hash', 'admin')
            ON CONFLICT (email) DO NOTHING
            """,
            (ADMIN_USER, TEST_TENANT, f"admin_{ADMIN_USER}@test.com"),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_screening_run_records_eligibility_and_exposes_badge(client: httpx.AsyncClient, setup_env):
    token = create_access_token(
        {
            "sub": str(ADMIN_USER),
            "tenant_id": str(TEST_TENANT),
            "email": f"admin_{ADMIN_USER}@test.com",
            "role": UserRole.ADMIN.value,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    job_id = uuid.uuid4()
    cand_young_id = uuid.uuid4()
    cand_senior_id = uuid.uuid4()
    doc_young_id = uuid.uuid4()
    doc_senior_id = uuid.uuid4()

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'MT Tech', 'JD')",
            (job_id, TEST_TENANT),
        )

        # Requirement set APPROVED
        set_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights)
            VALUES (%s, %s, %s, 1, 'APPROVED', '{"HARD_SKILLS": 100}'::jsonb)
            """,
            (set_id, TEST_TENANT, job_id),
        )
        await cur.execute(
            """
            INSERT INTO requirements (id, tenant_id, requirement_set_id, requirement_id, description, category, kind, importance, weight)
            VALUES (%s, %s, %s, 'R1', 'Python dev', 'HARD_SKILLS', 'SKILL', 'MUST_HAVE', 10)
            """,
            (uuid.uuid4(), TEST_TENANT, set_id),
        )

        # Create active Max Age rule (max 26 years)
        rule_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO eligibility_rules (
                id, tenant_id, job_id, rule_type, value, basis_category, justification,
                reference_date, status, created_by, approved_by, approved_at
            )
            VALUES (%s, %s, %s, 'AGE_MAX', '{"years": 26}'::jsonb, 'KARAKTERISTIK_JABATAN',
                    'Program Management Trainee operasional lapangan 5 tahun ikatan dinas',
                    '2026-10-01', 'APPROVED', %s, %s, now())
            """,
            (rule_id, TEST_TENANT, job_id, ADMIN_USER, ADMIN_USER),
        )

        # Candidate 1: Young (Born 2002 -> Age 24 as of 2026-10-01) -> ELIGIBLE
        await cur.execute(
            "INSERT INTO candidates (id, tenant_id, candidate_code) VALUES (%s, %s, 'C-1001')",
            (cand_young_id, TEST_TENANT),
        )
        await cur.execute(
            """
            INSERT INTO candidate_identities (candidate_id, tenant_id, other_personal)
            VALUES (%s, %s, pgp_sym_encrypt(%s, %s))
            """,
            (
                cand_young_id,
                TEST_TENANT,
                json.dumps({"date_of_birth": "2002-05-10"}),
                settings.PII_ENCRYPTION_KEY,
            ),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, candidate_id, original_filename, size_bytes, sha256, status)
            VALUES (%s, %s, %s, %s, 'young.pdf', 10, 'sha_y', 'READY')
            """,
            (doc_young_id, TEST_TENANT, job_id, cand_young_id),
        )
        await cur.execute(
            """
            INSERT INTO candidate_profiles (id, tenant_id, document_id, profile, matching_profile, extractor_version)
            VALUES (%s, %s, %s, '{}'::jsonb, '{"skills": [{"name": "Python"}]}'::jsonb, '1.0')
            """,
            (uuid.uuid4(), TEST_TENANT, doc_young_id),
        )

        # Candidate 2: Older (Born 1995 -> Age 31 as of 2026-10-01) -> NOT_ELIGIBLE
        await cur.execute(
            "INSERT INTO candidates (id, tenant_id, candidate_code) VALUES (%s, %s, 'C-1002')",
            (cand_senior_id, TEST_TENANT),
        )
        await cur.execute(
            """
            INSERT INTO candidate_identities (candidate_id, tenant_id, other_personal)
            VALUES (%s, %s, pgp_sym_encrypt(%s, %s))
            """,
            (
                cand_senior_id,
                TEST_TENANT,
                json.dumps({"date_of_birth": "1995-05-10"}),
                settings.PII_ENCRYPTION_KEY,
            ),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, candidate_id, original_filename, size_bytes, sha256, status)
            VALUES (%s, %s, %s, %s, 'older.pdf', 10, 'sha_o', 'READY')
            """,
            (doc_senior_id, TEST_TENANT, job_id, cand_senior_id),
        )
        await cur.execute(
            """
            INSERT INTO candidate_profiles (id, tenant_id, document_id, profile, matching_profile, extractor_version)
            VALUES (%s, %s, %s, '{}'::jsonb, '{"skills": [{"name": "Python"}]}'::jsonb, '1.0')
            """,
            (uuid.uuid4(), TEST_TENANT, doc_senior_id),
        )
        await conn.commit()

    # Trigger screening run as of 2026-10-01 (sync=true for test evaluation)
    run_res = await client.post(
        f"/api/v1/jobs/{job_id}/screenings?sync=true",
        json={"as_of": "2026-10-01", "use_verifier": False},
        headers=headers,
    )
    assert run_res.status_code == 201
    run_id = run_res.json()["screening_run_id"]

    # Fetch latest rankings
    rank_res = await client.get(f"/api/v1/jobs/{job_id}/screenings/latest", headers=headers)
    assert rank_res.status_code == 200
    rankings = rank_res.json()["rankings"]
    assert len(rankings) == 2

    # Map by file_name
    r_map = {r["file_name"]: r for r in rankings}
    assert r_map["young.pdf"]["eligibility_status"] == "ELIGIBLE"
    assert r_map["older.pdf"]["eligibility_status"] == "NOT_ELIGIBLE"

    # Invariant I-1: Both candidates must have identical final scores and competency bands!
    assert r_map["young.pdf"]["final_score"] == r_map["older.pdf"]["final_score"]
    assert r_map["young.pdf"]["band"] == r_map["older.pdf"]["band"]

    # Test filtering by eligibility=eligible
    f_res = await client.get(
        f"/api/v1/jobs/{job_id}/screenings/{run_id}/rankings?eligibility=eligible", headers=headers
    )
    assert f_res.status_code == 200
    f_rankings = f_res.json()["rankings"]
    assert len(f_rankings) == 1
    assert f_rankings[0]["file_name"] == "young.pdf"
    # Rank must remain original rank (not renumbered to 1)
    assert f_rankings[0]["rank"] == r_map["young.pdf"]["rank"]

    # Test eligibility summary endpoint
    summary_res = await client.get(
        f"/api/v1/jobs/{job_id}/screenings/{run_id}/eligibility-summary?top_n=10", headers=headers
    )
    assert summary_res.status_code == 200
    s_data = summary_res.json()
    assert s_data["counts"]["ELIGIBLE"] == 1
    assert s_data["counts"]["NOT_ELIGIBLE"] == 1
    assert s_data["impact"]["not_eligible_in_top_n"] == 1
    assert len(s_data["rules"]) == 1
