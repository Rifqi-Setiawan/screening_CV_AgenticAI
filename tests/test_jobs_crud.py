import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.domain.auth import create_access_token


@pytest.mark.asyncio
async def test_job_update_rename_and_delete():
    token = create_access_token(
        data={
            "sub": "ce12fcef-601b-4fb8-b8ed-f3eab5e8de6c",
            "role": "recruiter",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "email": "recruiter@rifqisetiawan.my.id",
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Create a job
        res_create = await ac.post(
            "/api/v1/jobs",
            headers=headers,
            json={
                "title": "Temporary Test Job for Deletion",
                "jd_text": "Deskripsi singkat lowongan uji coba untuk pengujian delete dan rename.",
                "location": "Jakarta",
            },
        )
        assert res_create.status_code == 201
        job_data = res_create.json()
        job_id = job_data["id"]
        assert job_data["title"] == "Temporary Test Job for Deletion"

        # 2. Rename the job
        res_patch = await ac.patch(
            f"/api/v1/jobs/{job_id}",
            headers=headers,
            json={"title": "Renamed Test Job"},
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["title"] == "Renamed Test Job"

        # 3. Delete the job
        res_del = await ac.delete(f"/api/v1/jobs/{job_id}", headers=headers)
        assert res_del.status_code == 200
        assert res_del.json()["message"] == "Job deleted successfully"

        # 4. Verify 404 on deleted job
        res_del_again = await ac.delete(f"/api/v1/jobs/{job_id}", headers=headers)
        assert res_del_again.status_code == 404
