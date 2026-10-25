import httpx
import pytest

from src.infrastructure.config import settings


@pytest.mark.asyncio
async def test_compile_preview_requires_auth(client: httpx.AsyncClient):
    # Without token -> 401
    res = await client.post(
        "/api/v1/requirements/compile-preview",
        json={"jd_text": "Requirements: Python, FastAPI, Docker, and PostgreSQL."},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_metrics_requires_token(client: httpx.AsyncClient):
    # Without token -> 401
    res = await client.get("/metrics")
    assert res.status_code == 401

    # With invalid token -> 401
    res_invalid = await client.get("/metrics", headers={"Authorization": "Bearer wrong-token"})
    assert res_invalid.status_code == 401

    # With valid METRICS_TOKEN -> 200
    res_valid = await client.get("/metrics", headers={"Authorization": f"Bearer {settings.METRICS_TOKEN}"})
    assert res_valid.status_code == 200
    assert "cv_processed_total" in res_valid.text
