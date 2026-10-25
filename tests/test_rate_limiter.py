import asyncio
import uuid

import httpx
import pytest
from fastapi import APIRouter, Depends, FastAPI

from src.api.middleware.rate_limiter import check_rate_limit, clear_rate_limiter_state
from src.domain.auth import create_access_token
from src.domain.models import UserRole

# Create a small standalone test app with the rate limiter dependency
test_app = FastAPI()
router = APIRouter()


@router.get("/test-limited", dependencies=[Depends(check_rate_limit(max_requests=3, window_seconds=1))])
async def limited_endpoint():
    return {"status": "ok"}


test_app.include_router(router)


@pytest.fixture(autouse=True)
def reset_limiter():
    clear_rate_limiter_state()
    yield
    clear_rate_limiter_state()


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_n_requests():
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Request 1, 2, 3 -> 200
        for _ in range(3):
            r = await ac.get("/test-limited")
            assert r.status_code == 200

        # Request 4 -> 429
        r4 = await ac.get("/test-limited")
        assert r4.status_code == 429
        assert "Rate limit exceeded" in r4.json()["detail"]


@pytest.mark.asyncio
async def test_rate_limiter_resets_after_window():
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        for _ in range(3):
            r = await ac.get("/test-limited")
            assert r.status_code == 200

        r_blocked = await ac.get("/test-limited")
        assert r_blocked.status_code == 429

        # Wait for 1.1s (window is 1s)
        await asyncio.sleep(1.1)

        r_after = await ac.get("/test-limited")
        assert r_after.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiter_two_users_isolated():
    transport = httpx.ASGITransport(app=test_app)
    user_1_token = create_access_token(
        {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "email": "u1@test.com",
            "role": UserRole.RECRUITER.value,
        }
    )
    user_2_token = create_access_token(
        {
            "sub": str(uuid.uuid4()),
            "tenant_id": str(uuid.uuid4()),
            "email": "u2@test.com",
            "role": UserRole.RECRUITER.value,
        }
    )

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        h1 = {"Authorization": f"Bearer {user_1_token}"}
        h2 = {"Authorization": f"Bearer {user_2_token}"}

        # User 1 uses all 3 requests
        for _ in range(3):
            r = await ac.get("/test-limited", headers=h1)
            assert r.status_code == 200

        # User 1 is blocked
        r1_blocked = await ac.get("/test-limited", headers=h1)
        assert r1_blocked.status_code == 429

        # User 2 is NOT blocked
        r2 = await ac.get("/test-limited", headers=h2)
        assert r2.status_code == 200
