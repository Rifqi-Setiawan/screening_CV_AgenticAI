import httpx
import pytest


@pytest.mark.asyncio
async def test_cors_rejects_unregistered_origin(client: httpx.AsyncClient):
    headers = {
        "Origin": "https://evil-attacker.com",
        "Access-Control-Request-Method": "POST",
    }
    res = await client.options("/api/v1/jobs", headers=headers)
    assert "access-control-allow-origin" not in res.headers


@pytest.mark.asyncio
async def test_cors_accepts_registered_origin(client: httpx.AsyncClient):
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
    }
    res = await client.options("/api/v1/jobs", headers=headers)
    assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"
