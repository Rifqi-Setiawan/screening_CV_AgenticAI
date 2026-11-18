"""Staff sessions must reject publicly exposed demo identities."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
import pytest

from src.api import dependencies
from src.api.routes import auth
from src.domain.auth import create_access_token, hash_password

TEST_EMAIL = "staff@example.org"
TEST_PASSWORD = "SyntheticCredentialOnly"


@pytest.fixture
def staff_row(monkeypatch):
    row = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "email": TEST_EMAIL,
        "role": "recruiter",
        "is_active": True,
        "password_hash": hash_password(TEST_PASSWORD),
        "created_at": datetime.now(UTC),
    }
    cur = AsyncMock()
    cur.fetchone.return_value = row
    cur.__aenter__.return_value = cur
    conn = MagicMock()
    conn.cursor.return_value = cur
    conn.commit = AsyncMock()

    @asynccontextmanager
    async def connection():
        yield conn

    monkeypatch.setattr(auth, "get_connection", connection)
    monkeypatch.setattr(dependencies, "get_connection", connection)
    return row


@pytest.mark.asyncio
async def test_login_and_reload_session(client: httpx.AsyncClient, staff_row):
    result = await client.post("/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    assert result.status_code == 200
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + result.json()["access_token"]})
    assert response.status_code == 200
    assert response.json()["id"] == str(staff_row["id"])


@pytest.mark.asyncio
async def test_bad_password_returns_unauthorized(client: httpx.AsyncClient, staff_row):
    result = await client.post("/api/v1/auth/login", json={"email": TEST_EMAIL, "password": "wrong"})
    assert result.status_code == 401


@pytest.mark.asyncio
async def test_demo_staff_cannot_login_or_reuse_existing_token(client: httpx.AsyncClient, staff_row):
    demo_email = "recruiter@rifqisetiawan.my.id"
    staff_row["email"] = demo_email
    result = await client.post("/api/v1/auth/login", json={"email": demo_email, "password": TEST_PASSWORD})
    assert result.status_code == 401
    token = create_access_token(
        {
            "sub": str(staff_row["id"]),
            "tenant_id": str(staff_row["tenant_id"]),
            "email": demo_email,
            "role": "recruiter",
        }
    )
    response = await client.get("/api/v1/jobs", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 403
