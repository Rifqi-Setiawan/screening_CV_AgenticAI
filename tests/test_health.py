"""Tests for health check and operational endpoints."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_health_check_public(client: httpx.AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


@pytest.mark.asyncio
async def test_health_check_admin_authorized(client: httpx.AsyncClient, admin_token: str):
    response = await client.get("/api/v1/admin/health", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert data["database"] == "HEALTHY"
    assert data["pgvector_version"] is not None
    assert data["pgvector_version"].startswith("0.8")


@pytest.mark.asyncio
async def test_health_check_admin_unauthorized(client: httpx.AsyncClient, recruiter_token: str):
    response = await client.get("/api/v1/admin/health", headers={"Authorization": f"Bearer {recruiter_token}"})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_root_endpoint(client: httpx.AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
