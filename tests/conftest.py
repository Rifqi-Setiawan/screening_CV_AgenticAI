"""Isolate test settings from runtime credentials and the production database."""

from __future__ import annotations

import os
import secrets
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

import httpx
import pytest_asyncio

os.environ["APP_ENV"] = "test"
test_db_url = os.environ.get("TEST_DATABASE_URL")
if not test_db_url:
    raise RuntimeError("Set TEST_DATABASE_URL ke database TES (bukan production).")
if not urlparse(test_db_url).path.endswith("_test"):
    raise RuntimeError("Ditolak: database testing harus berakhiran '_test'.")

os.environ["DATABASE_URL"] = test_db_url
os.environ["JWT_SECRET"] = secrets.token_hex(32)
os.environ["METRICS_TOKEN"] = secrets.token_hex(32)
os.environ["PII_ENCRYPTION_KEY"] = secrets.token_hex(32)

from src.api.main import app


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
