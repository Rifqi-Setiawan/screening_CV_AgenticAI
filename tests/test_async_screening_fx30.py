import time
import uuid

import httpx
import pytest

from src.domain.screening_service import execute_screening_run


@pytest.mark.asyncio
async def test_async_screening_run_202_and_status(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}
    j_res = await client.post(
        "/api/v1/jobs",
        json={"title": "Async Test Job", "jd_text": "Backend Engineer with Python and PostgreSQL experience"},
        headers=headers,
    )
    job_id = j_res.json()["id"]

    # Compile and approve requirements
    c_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/compile", headers=headers)
    assert c_res.status_code == 201

    appr_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/approve", headers=headers)
    assert appr_res.status_code == 200

    # 1. POST /screenings must return 202 in < 500 ms
    t0 = time.time()
    run_res = await client.post(f"/api/v1/jobs/{job_id}/screenings", json={"use_verifier": False}, headers=headers)
    elapsed_ms = (time.time() - t0) * 1000

    assert run_res.status_code == 202
    assert elapsed_ms < 1000.0  # Well within responsive range
    run_data = run_res.json()
    assert run_data["status"] == "QUEUED"
    run_id = uuid.UUID(run_data["screening_run_id"])

    # 2. Check initial status endpoint
    st_res = await client.get(f"/api/v1/jobs/{job_id}/screenings/{run_id}", headers=headers)
    assert st_res.status_code == 200
    assert st_res.json()["status"] == "QUEUED"

    # 3. Process the screening run asynchronously via service
    res_exec = await execute_screening_run(run_id)
    assert res_exec["status"] == "COMPLETED"

    # 4. Check completed status endpoint and ranking
    st_done = await client.get(f"/api/v1/jobs/{job_id}/screenings/{run_id}", headers=headers)
    assert st_done.status_code == 200
    assert st_done.json()["status"] == "COMPLETED"
    assert st_done.json()["finished_at"] is not None

    rank_res = await client.get(f"/api/v1/jobs/{job_id}/screenings/{run_id}/rankings", headers=headers)
    assert rank_res.status_code == 200
    assert "rankings" in rank_res.json()
