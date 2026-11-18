"""Health and operational readiness check endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from src.api.dependencies import get_current_user
from src.domain.models import HealthResponse, User
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

router = APIRouter(tags=["Health"])


@router.get("/health")
async def check_health() -> dict[str, str]:
    return {"status": "UP"}


@router.get("/api/v1/admin/health", response_model=HealthResponse)
async def check_admin_health(
    current_user: User = Depends(get_current_user),
) -> HealthResponse:
    db_status = "DOWN"
    try:
        async with get_connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1")
            db_status = "HEALTHY"
    except Exception:
        db_status = "ERROR"

    return HealthResponse(
        status="UP" if db_status == "HEALTHY" else "DEGRADED",
        app_env=settings.APP_ENV,
        database=db_status,
        active_services=["api", "postgres", "caddy"],
        timestamp=datetime.now(UTC),
    )
