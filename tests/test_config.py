import pytest
from pydantic import ValidationError

from src.infrastructure.config import Settings


def test_config_rejects_short_jwt_in_production():
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            JWT_SECRET="short",
            METRICS_TOKEN="a" * 32,
            DATABASE_URL="postgresql://user:password@127.0.0.1:5432/test_db",
        )


def test_config_rejects_short_metrics_token_in_production():
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            JWT_SECRET="a" * 32,
            METRICS_TOKEN="short",
            DATABASE_URL="postgresql://user:password@127.0.0.1:5432/test_db",
        )


def test_config_rejects_insecure_default_keywords_in_production():
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            JWT_SECRET="default-insecure-secret-key-change-in-production-12345",
            METRICS_TOKEN="a" * 32,
            DATABASE_URL="postgresql://user:password@127.0.0.1:5432/test_db",
        )

    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            JWT_SECRET="a" * 32,
            METRICS_TOKEN="default-metrics-token-secret-change-it-now",
            DATABASE_URL="postgresql://user:password@127.0.0.1:5432/test_db",
        )


def test_config_accepts_strong_secret():
    jwt_val = "b" * 64
    metrics_val = "c" * 64
    s = Settings(
        APP_ENV="production",
        JWT_SECRET=jwt_val,
        METRICS_TOKEN=metrics_val,
        DATABASE_URL="postgresql://user:password@127.0.0.1:5432/test_db",
    )
    assert jwt_val == s.JWT_SECRET
    assert metrics_val == s.METRICS_TOKEN


def test_config_allows_test_env_bypass():
    s = Settings(
        APP_ENV="test",
        JWT_SECRET="short-test-secret",
        DATABASE_URL="postgresql://user:***@127.0.0.1:5432/db",
    )
    assert s.JWT_SECRET == "short-test-secret"


def test_conftest_guard_blocks_production_database():
    import os
    import subprocess

    res = subprocess.run(
        [".venv/bin/pytest", "tests/test_health.py"],
        env={**os.environ, "TEST_DATABASE_URL": "postgresql://cv_screening_user:pass@127.0.0.1:5432/cv_screening"},
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "Ditolak: database testing" in res.stderr
    assert "_test" in res.stderr
