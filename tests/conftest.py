"""Pytest configuration and shared test fixtures."""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Add cv-extractor to python path for full extraction fidelity
cv_extractor_src = "/srv/hermes-control/services/cv-extractor/src"
if cv_extractor_src not in sys.path:
    sys.path.insert(0, cv_extractor_src)

# Set test environment before importing application
os.environ.setdefault("APP_ENV", "test")

test_db_url = os.environ.get("TEST_DATABASE_URL")
if not test_db_url:
    raise RuntimeError("Set TEST_DATABASE_URL ke database TES (bukan production).")

parsed = urlparse(test_db_url)
db_name = parsed.path.lstrip("/")
if not db_name.endswith("_test"):
    raise RuntimeError(f"Ditolak: database testing '{db_name}' harus berakhiran '_test' demi keamanan production.")

os.environ["DATABASE_URL"] = test_db_url
os.environ.setdefault("JWT_SECRET", secrets.token_hex(32))
os.environ.setdefault("METRICS_TOKEN", secrets.token_hex(32))
os.environ.setdefault("PII_ENCRYPTION_KEY", secrets.token_hex(32))
os.environ.setdefault("ALLOW_RELIGION_CRITERIA", "false")
os.environ.setdefault("ALLOW_GENDER_CRITERIA", "false")

from collections.abc import AsyncGenerator

import httpx
import pytest
import pytest_asyncio

from src.api.main import app
from src.domain.auth import create_access_token
from src.domain.models import UserRole

DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_token() -> str:
    return create_access_token(
        {
            "sub": "adbbfe35-43d1-40ef-a02b-10c975110219",
            "tenant_id": DEMO_TENANT_ID,
            "email": "admin@rifqisetiawan.my.id",
            "role": UserRole.ADMIN.value,
        }
    )


@pytest.fixture
def recruiter_token() -> str:
    return create_access_token(
        {
            "sub": "ce12fcef-601b-4fb8-b8ed-f3eab5e8de6c",
            "tenant_id": DEMO_TENANT_ID,
            "email": "recruiter@rifqisetiawan.my.id",
            "role": UserRole.RECRUITER.value,
        }
    )


@pytest.fixture
def hiring_manager_token() -> str:
    return create_access_token(
        {
            "sub": "fffb4b73-f806-46df-89b4-3318143ece4a",
            "tenant_id": DEMO_TENANT_ID,
            "email": "manager@rifqisetiawan.my.id",
            "role": UserRole.HIRING_MANAGER.value,
        }
    )
