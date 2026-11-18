"""Public health and route checks for the TIG-only API."""

from uuid import uuid4

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_check_public(client: httpx.AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


@pytest.mark.asyncio
async def test_admin_health_requires_login(client: httpx.AsyncClient):
    response = await client.get("/api/v1/admin/health")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_root_endpoint(client: httpx.AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "Rekrutmen TIG"


@pytest.mark.asyncio
async def test_removed_workflow_routes_return_not_found(client: httpx.AsyncClient):
    job = "/api/v1/jobs/" + str(uuid4())
    for path in (
        job + "/requirements",
        job + "/cvs/status",
        job + "/screenings/latest",
        job + "/eligibility-rules",
        "/audit-files/old.pdf",
    ):
        assert (await client.get(path)).status_code == 404
