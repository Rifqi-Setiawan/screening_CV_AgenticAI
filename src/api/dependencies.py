"""FastAPI request dependencies for recruiter sessions and tenant scoping."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.domain.auth import decode_access_token
from src.domain.models import TokenData, User, UserRole
from src.infrastructure.database import get_connection

security = HTTPBearer(auto_error=False)

# These seeded identities used public credentials in the legacy frontend.
DEMO_STAFF = {
    "admin@rifqisetiawan.my.id",
    "recruiter@rifqisetiawan.my.id",
    "manager@rifqisetiawan.my.id",
}


def is_demo_staff(email: str) -> bool:
    return email.casefold() in DEMO_STAFF


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
        if is_demo_staff(row["email"]):
            raise HTTPException(403, "Gunakan akun staf khusus TIG.")
        user = User(
            id=row["id"],
            tenant_id=row["tenant_id"],
            email=row["email"],
            role=UserRole(row["role"]),
            is_active=row["is_active"],
            created_at=row["created_at"],
        )
    return user


async def get_job_for_tenant(cur, job_id: Any, tenant_id: Any, *, lock: bool = False) -> dict[str, Any]:
    """Helper to verify job belongs to the authenticated tenant. Returns 404 if not found."""
    sql = """
        SELECT j.id, j.status, c.config FROM jobs j JOIN tig_configs c ON c.job_id = j.id
        WHERE j.id = %s AND j.tenant_id = %s
    """
    if lock:
        sql += " FOR UPDATE OF j"
    await cur.execute(sql, (job_id, tenant_id))
    job = await cur.fetchone()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job tidak ditemukan")
    return job
