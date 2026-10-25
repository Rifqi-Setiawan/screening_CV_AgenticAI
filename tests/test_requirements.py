"""Tests for Requirement Compiler, Policy Linter, Manual Editing, and Approval Gates (M3)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.infrastructure.database import get_connection


@pytest.mark.asyncio
async def test_compile_jd01_covers_concepts(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}
    jd_path = Path("docs/spec/golden_dataset/job_descriptions/JD-01_backend_engineer.md")
    assert jd_path.exists()
    jd_text = jd_path.read_text()

    # Create job
    j_res = await client.post(
        "/api/v1/jobs",
        json={"title": "Backend Engineer (Mid–Senior)", "jd_text": jd_text, "external_ref": "JD-01"},
        headers=headers,
    )
    assert j_res.status_code == 201
    job_id = j_res.json()["id"]

    # Compile requirements
    c_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/compile", headers=headers)
    assert c_res.status_code == 201
    c_data = c_res.json()
    assert c_data["status"] == "DRAFT"
    assert c_data["is_valid"] is True

    reqs = c_data["requirements"]
    assert len(reqs) >= 9

    # Check concepts coverage
    compiled_concepts = set()
    for r in reqs:
        for c in r.get("concepts", []):
            compiled_concepts.add(c)

    target_concepts = [
        "role_family:backend",
        "skill:python",
        "skill:postgresql",
        "skill:rest_api",
        "skill:docker",
        "skill:kubernetes",
        "skill:mentoring",
        "field:computing",
        "achievement:quantified_backend",
    ]

    matched = sum(1 for tc in target_concepts if tc in compiled_concepts)
    assert matched >= 8, f"Only matched {matched}/9 target concepts: {compiled_concepts}"


@pytest.mark.asyncio
async def test_prohibited_criteria_blocks_approval(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}
    prohibited_jd = "Dibutuhkan staf dengan kriteria: berpenampilan menarik, good looking, dan beragama tertentu."

    # Create job with prohibited text
    j_res = await client.post(
        "/api/v1/jobs",
        json={"title": "Prohibited Test Job", "jd_text": prohibited_jd},
        headers=headers,
    )
    assert j_res.status_code == 201
    job_id = j_res.json()["id"]

    # Compile requirements
    c_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/compile", headers=headers)
    assert c_res.status_code == 201
    c_data = c_res.json()

    # Must detect prohibited flags for appearance & religion
    prohibited = c_data["prohibited_flags"]
    assert "PROHIBITED_APPEARANCE" in prohibited
    assert "PROHIBITED_RELIGION" in prohibited
    assert c_data["is_valid"] is False

    # Try to approve -> MUST be blocked with HTTP 422
    appr_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/approve", headers=headers)
    assert appr_res.status_code == 422
    err_detail = appr_res.json()["detail"]
    assert err_detail["error"] == "CANNOT_APPROVE_PROHIBITED_CRITERIA"
    assert len(err_detail["violations"]) >= 1


@pytest.mark.asyncio
async def test_manual_prohibited_input_rejected(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}

    # Create job
    j_res = await client.post(
        "/api/v1/jobs",
        json={"title": "Manual Prohibited Test Job", "jd_text": "Normal job description"},
        headers=headers,
    )
    job_id = j_res.json()["id"]

    # Attempt to manually add prohibited criteria: "berpenampilan menarik dan good looking"
    bad_req = {
        "requirement_id": "R_BAD",
        "description": "Kandidat harus berpenampilan menarik dan good looking",
        "category": "HARD_SKILLS",
    }
    m_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/manual", json=bad_req, headers=headers)
    assert m_res.status_code == 422
    data = m_res.json()["detail"]
    assert data["error"] == "CANNOT_ADD_PROHIBITED_CRITERIA"
    assert "PROHIBITED_APPEARANCE" in data["flags"]


@pytest.mark.asyncio
async def test_editing_approved_requirement_set_creates_new_version(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}

    # Create job
    j_res = await client.post(
        "/api/v1/jobs",
        json={"title": "Versioning Job", "jd_text": "Version test"},
        headers=headers,
    )
    job_id = j_res.json()["id"]

    # 1. Add requirement to v1 and approve it
    r1 = {
        "requirement_id": "R1",
        "description": "Pengalaman Python 2 tahun",
        "category": "HARD_SKILLS",
    }
    await client.post(f"/api/v1/jobs/{job_id}/requirements/manual", json=r1, headers=headers)
    appr_v1 = await client.post(f"/api/v1/jobs/{job_id}/requirements/approve", headers=headers)
    assert appr_v1.status_code == 200
    assert appr_v1.json()["version"] == 1
    assert appr_v1.json()["status"] == "APPROVED"

    # 2. Now edit / add a requirement after v1 is approved -> MUST create v2 with DRAFT status!
    r2 = {
        "requirement_id": "R2",
        "description": "Pengalaman Docker container",
        "category": "HARD_SKILLS",
    }
    m_v2 = await client.post(f"/api/v1/jobs/{job_id}/requirements/manual", json=r2, headers=headers)
    assert m_v2.status_code == 201

    # Verify database has both v1 (APPROVED) and v2 (DRAFT)
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT version, status FROM requirement_sets WHERE job_id = %s ORDER BY version ASC",
            (job_id,),
        )
        rows = await cur.fetchall()
        assert len(rows) == 2
        assert rows[0]["version"] == 1 and rows[0]["status"] == "APPROVED"
        assert rows[1]["version"] == 2 and rows[1]["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_import_approved_jd01_and_jd02(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}
    jd01_approved_path = Path("docs/spec/golden_dataset/job_descriptions/JD-01_requirements.approved.json")
    jd02_approved_path = Path("docs/spec/golden_dataset/job_descriptions/JD-02_requirements.approved.json")

    jd01_data = json.loads(jd01_approved_path.read_text())
    jd02_data = json.loads(jd02_approved_path.read_text())

    # Create Job 1
    j1_res = await client.post(
        "/api/v1/jobs",
        json={"title": "JD-01 Backend", "jd_text": "Requirements test", "external_ref": "JD-01"},
        headers=headers,
    )
    job1_id = j1_res.json()["id"]

    # Import Approved JD-01
    imp1_res = await client.post(
        f"/api/v1/jobs/{job1_id}/requirements/import-approved",
        json=jd01_data,
        headers=headers,
    )
    assert imp1_res.status_code == 201
    assert imp1_res.json()["status"] == "APPROVED"
    assert imp1_res.json()["total_requirements"] == 10

    # Create Job 2
    j2_res = await client.post(
        "/api/v1/jobs",
        json={"title": "JD-02 HR", "jd_text": "HR requirements test", "external_ref": "JD-02"},
        headers=headers,
    )
    job2_id = j2_res.json()["id"]

    # Import Approved JD-02
    imp2_res = await client.post(
        f"/api/v1/jobs/{job2_id}/requirements/import-approved",
        json=jd02_data,
        headers=headers,
    )
    assert imp2_res.status_code == 201
    assert imp2_res.json()["status"] == "APPROVED"
    assert imp2_res.json()["total_requirements"] == 7


@pytest.mark.asyncio
async def test_manual_criteria_editing_and_approval(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}

    # Create Job
    j_res = await client.post(
        "/api/v1/jobs",
        json={"title": "Manual Criteria Job", "jd_text": "Manual custom requirements"},
        headers=headers,
    )
    job_id = j_res.json()["id"]

    # Recruiter manually adds requirements without LLM
    r1_payload = {
        "requirement_id": "R1",
        "description": "Minimal 2 tahun pengalaman Golang microservices",
        "category": "EXPERIENCE",
        "kind": "EXPERIENCE_DURATION",
        "importance": "MUST_HAVE",
        "weight": 25.0,
        "concepts": ["skill:go", "skill:microservices"],
    }
    m1_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/manual", json=r1_payload, headers=headers)
    assert m1_res.status_code == 201
    assert m1_res.json()["requirement_id"] == "R1"
    assert m1_res.json()["lint_flags"] == []

    # Recruiter approves
    appr_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/approve", headers=headers)
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "APPROVED"
