"""FastAPI request dependencies, security gates, and RBAC enforcement."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.domain.auth import decode_access_token
from src.domain.models import TokenData, User, UserRole
from src.infrastructure.database import get_connection

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    token_data: TokenData | None = decode_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id, tenant_id, email, role, is_active, created_at FROM users WHERE id = %s",
            (token_data.user_id,),
        )
        row = await cur.fetchone()
        if not row or not row["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account inactive or not found",
            )
        user = User(
            id=row["id"],
            tenant_id=row["tenant_id"],
            email=row["email"],
            role=UserRole(row["role"]),
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
    return user


async def get_job_for_tenant(cur, job_id: Any, tenant_id: Any) -> dict[str, Any]:
    """Helper to verify job belongs to the authenticated tenant. Returns 404 if not found."""
    await cur.execute(
        "SELECT * FROM jobs WHERE id = %s AND tenant_id = %s",
        (job_id, tenant_id),
    )
    job = await cur.fetchone()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job tidak ditemukan")
    return job


def require_role(allowed_roles: list[UserRole]) -> Callable:
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires one of {[r.value for r in allowed_roles]} roles",
            )
        return current_user

    return role_checker
