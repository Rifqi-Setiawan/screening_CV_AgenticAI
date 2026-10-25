"""Tests for user authentication, JWT token issuance, and validation."""

from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_login_success(client: httpx.AsyncClient):
    payload = {
        "email": "recruiter@rifqisetiawan.my.id",
        "password": "RecruiterPassword2026!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "recruiter@rifqisetiawan.my.id"
    assert data["user"]["role"] == "recruiter"


@pytest.mark.asyncio
async def test_login_invalid_password(client: httpx.AsyncClient):
    payload = {
        "email": "recruiter@rifqisetiawan.my.id",
        "password": "WrongPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_user_not_found(client: httpx.AsyncClient):
    payload = {
        "email": "nonexistent@rifqisetiawan.my.id",
        "password": "AnyPassword123!",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
