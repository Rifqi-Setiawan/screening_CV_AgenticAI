"""Tests for job routes and role-based access control (RBAC)."""

from __future__ import annotations

import httpx
import pytest

from src.infrastructure.database import get_connection


@pytest.mark.asyncio
async def test_create_job_as_recruiter(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}
    payload = {
        "title": "Senior Backend Engineer",
        "jd_text": "We are seeking a senior backend engineer with 5+ years of Python & PostgreSQL experience.",
        "location": "Jakarta",
        "employment_type": "full_time",
        "external_ref": "JD-01",
    }
    response = await client.post("/api/v1/jobs", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Senior Backend Engineer"
    assert data["status"] == "DRAFT"
    assert data["external_ref"] == "JD-01"

    # Verify audit log entry exists
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT action, target_type, target_id FROM audit_logs WHERE action = 'JOB_CREATE' AND target_id = %s",
            (str(data["id"]),),
        )
        audit_row = await cur.fetchone()
        assert audit_row is not None
        assert audit_row["action"] == "JOB_CREATE"
        assert audit_row["target_type"] == "job"


@pytest.mark.asyncio
async def test_create_job_forbidden_for_hiring_manager(client: httpx.AsyncClient, hiring_manager_token: str):
    headers = {"Authorization": f"Bearer {hiring_manager_token}"}
    payload = {
        "title": "Data Scientist",
        "jd_text": "Machine learning specialist required.",
    }
    response = await client.post("/api/v1/jobs", json=payload, headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_jobs_authenticated(client: httpx.AsyncClient, hiring_manager_token: str):
    headers = {"Authorization": f"Bearer {hiring_manager_token}"}
    response = await client.get("/api/v1/jobs", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
