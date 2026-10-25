import uuid

import httpx
import pytest

from src.domain.auth import create_access_token
from src.domain.models import UserRole
from src.infrastructure.database import get_connection

TEST_TENANT = uuid.uuid4()
TEST_USER = uuid.uuid4()


@pytest.fixture
def auth_header():
    token = create_access_token(
        {
            "sub": str(TEST_USER),
            "tenant_id": str(TEST_TENANT),
            "email": f"rec_{TEST_USER}@gate-test.com",
            "role": UserRole.RECRUITER.value,
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_screening_without_approved_set_returns_409(client: httpx.AsyncClient, auth_header: dict):
    # 1. Create a job
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (id, tenant_id, email, password_hash, role, is_active)
            VALUES (%s, %s, %s, 'hash', 'recruiter', true)
            ON CONFLICT (email) DO NOTHING
            """,
            (TEST_USER, TEST_TENANT, f"rec_{TEST_USER}@gate-test.com"),
        )
        job_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text, created_by)
            VALUES (%s, %s, 'Unapproved Job', 'JD without approved requirements', %s)
            """,
            (job_id, TEST_TENANT, TEST_USER),
        )
        # Create a DRAFT requirement set (not approved)
        set_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights)
            VALUES (%s, %s, %s, 1, 'DRAFT', '{"HARD_SKILLS": 100}'::jsonb)
            """,
            (set_id, TEST_TENANT, job_id),
        )
        await cur.execute(
            """
            INSERT INTO requirements (id, tenant_id, requirement_set_id, requirement_id, description, category, kind, importance, weight)
            VALUES (%s, %s, %s, 'R1', 'Python expert', 'HARD_SKILLS', 'SKILL', 'MUST_HAVE', 100)
            """,
            (uuid.uuid4(), TEST_TENANT, set_id),
        )
        await conn.commit()

    # Trigger screening -> must return 409
    res = await client.post(f"/api/v1/jobs/{job_id}/screenings", json={"as_of": "2026-10-01"}, headers=auth_header)
    assert res.status_code == 409
    assert "Kriteria belum disetujui" in res.json()["detail"]

    # Now approve the requirement set
    approve_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/approve", headers=auth_header)
    assert approve_res.status_code == 200

    # Trigger screening again -> must succeed (201 or 202)
    res2 = await client.post(f"/api/v1/jobs/{job_id}/screenings", json={"as_of": "2026-10-01"}, headers=auth_header)
    assert res2.status_code in (201, 202)
