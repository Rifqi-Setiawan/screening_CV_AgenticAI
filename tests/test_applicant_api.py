"""Applicant accounts, applying, and HR transparency against the isolated _test database."""

from __future__ import annotations

from uuid import uuid4

import pytest
from psycopg.errors import CheckViolation
from psycopg.types.json import Jsonb

from src.api.middleware.rate_limiter import clear_rate_limiter_state
from src.domain.auth import create_access_token
from src.domain.tig import TigConfig
from src.infrastructure.database import get_connection

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    clear_rate_limiter_state()
    yield
    clear_rate_limiter_state()


FORM = {
    "full_name": "Pelamar Sintetis",
    "email": "kontak@example.org",
    "phone": "081234567890",
    "education": [{"level": "S1", "campus": "Kampus Contoh", "major": "Informatika", "gpa": 3.4}],
    "skills": ["Python", "SQL"],
    "preferences": {"domicile": "Bandung", "expected_salary": 8_000_000},
    # Required since the intake rules: an applicant with no work history declares it explicitly, and consents.
    "fresh_graduate": True,
    "consent": True,
}


async def staff_and_job(role: str = "recruiter") -> tuple[str, str, str]:
    """Creates a staff account and a published job; returns (staff token, job id, staff email)."""
    tenant_id, user_id, job_id = uuid4(), uuid4(), uuid4()
    email = f"staf-{user_id.hex[:8]}@example.org"
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO users (id, tenant_id, email, password_hash, role) VALUES (%s, %s, %s, 'x', %s)",
            (user_id, tenant_id, email, role),
        )
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text, status) VALUES (%s, %s, 'Data Analyst', '', 'OPEN')",
            (job_id, tenant_id),
        )
        await cur.execute(
            "INSERT INTO tig_configs (job_id, config) VALUES (%s, %s)",
            (job_id, Jsonb(TigConfig(published=True).model_dump())),
        )
    token = create_access_token({"sub": str(user_id), "tenant_id": str(tenant_id), "email": email, "role": role})
    return token, str(job_id), email


async def register(client, email: str | None = None) -> str:
    email = email or f"pelamar-{uuid4().hex[:8]}@example.org"
    response = await client.post(
        "/api/v1/applicant/register",
        json={"full_name": "Pelamar Sintetis", "email": email, "password": "rahasia-sintetis", "consent": True},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


async def test_register_login_and_duplicate_email(client):
    email = f"Pelamar-{uuid4().hex[:8]}@Example.org"
    await register(client, email)
    duplicate = await client.post(
        "/api/v1/applicant/register",
        json={"full_name": "Lain", "email": email.lower(), "password": "rahasia-sintetis", "consent": True},
    )
    assert duplicate.status_code == 409
    no_consent = await client.post(
        "/api/v1/applicant/register",
        json={"full_name": "Lain", "email": "x" + email, "password": "rahasia-sintetis", "consent": False},
    )
    assert no_consent.status_code == 422
    wrong = await client.post("/api/v1/applicant/login", json={"email": email, "password": "salah-sekali"})
    assert wrong.status_code == 401
    ok = await client.post("/api/v1/applicant/login", json={"email": email.lower(), "password": "rahasia-sintetis"})
    assert ok.status_code == 200
    me = await client.get("/api/v1/applicant/me", headers={"Authorization": "Bearer " + ok.json()["access_token"]})
    assert me.json()["email"] == email.lower()


async def test_applicant_applies_once_and_follows_status(client):
    staff_token, job_id, _ = await staff_and_job()
    jobs = await client.get("/api/v1/tig/jobs")
    assert job_id in [job["id"] for job in jobs.json()]

    anonymous = await client.post(f"/api/v1/tig/apply/{job_id}", json=FORM)
    assert anonymous.status_code == 401
    token = await register(client)
    headers = {"Authorization": "Bearer " + token}
    submitted = await client.post(f"/api/v1/tig/apply/{job_id}", json=FORM, headers=headers)
    assert submitted.status_code == 202, submitted.text
    again = await client.post(f"/api/v1/tig/apply/{job_id}", json=FORM, headers=headers)
    assert again.status_code == 409

    mine = await client.get("/api/v1/applicant/applications", headers=headers)
    assert [(item["job_id"], item["stage"]) for item in mine.json()] == [(job_id, "Seleksi")]

    # Tokens do not cross between applicant and staff areas.
    assert (await client.get("/api/v1/jobs", headers=headers)).status_code == 401
    staff_headers = {"Authorization": "Bearer " + staff_token}
    assert (await client.get("/api/v1/applicant/applications", headers=staff_headers)).status_code == 401


async def test_hr_detail_is_audited_and_rescore_keeps_history(client):
    staff_token, job_id, staff_email = await staff_and_job()
    token = await register(client)
    submitted = await client.post(
        f"/api/v1/tig/apply/{job_id}", json=FORM, headers={"Authorization": "Bearer " + token}
    )
    application_id = submitted.json()["application_id"]
    previous = {"score": 64, "summary": "Penilaian pertama.", "categories": {}, "strengths": [], "gaps": []}
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE tig_applications SET assessment = %s, assessed_at = now() WHERE id = %s",
            (Jsonb(previous), application_id),
        )
        await cur.execute(
            "UPDATE jobs_queue SET status = 'DONE' WHERE id = (SELECT queue_id FROM tig_applications WHERE id = %s)",
            (application_id,),
        )

    headers = {"Authorization": "Bearer " + staff_token}
    base = f"/api/v1/jobs/{job_id}/tig/applications/{application_id}"
    detail = await client.get(base, headers=headers)
    assert detail.status_code == 200
    assert detail.json()["form"]["full_name"] == "Pelamar Sintetis"
    assert detail.json()["assessment_history"] == []

    assert (await client.post(base + "/rescore", headers=headers)).status_code == 202
    detail = await client.get(base, headers=headers)
    history = detail.json()["assessment_history"]
    assert detail.json()["assessment"] is None
    assert [(entry["assessment"]["score"], entry["replaced_by"]) for entry in history] == [(64, staff_email)]

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT action FROM audit_logs WHERE target_id = %s ORDER BY id", (application_id,))
        actions = [row["action"] for row in await cur.fetchall()]
    assert actions == ["TIG_APPLICATION_VIEW", "TIG_RESCORE", "TIG_APPLICATION_VIEW"]


async def test_recruiter_is_the_only_staff_role_and_can_configure(client):
    staff_token, job_id, _ = await staff_and_job()
    headers = {"Authorization": "Bearer " + staff_token}
    config = TigConfig(published=True).model_dump()
    config["regular"]["skills"] = ["SQL"]
    saved = await client.put(f"/api/v1/jobs/{job_id}/tig/config", json=config, headers=headers)
    assert saved.status_code == 200, saved.text
    assert (await client.get(f"/api/v1/jobs/{job_id}/tig/config", headers=headers)).json()["can_edit"] is True

    # The database no longer accepts other staff roles.
    with pytest.raises(CheckViolation):
        async with get_connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, 'x', 'admin')",
                (uuid4(), f"admin-{uuid4().hex[:8]}@example.org"),
            )
