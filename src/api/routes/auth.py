"""Authentication endpoints: login, token issuance, and profile inspection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from src.domain.auth import create_access_token, verify_password
from src.domain.models import TokenResponse, User, UserRole
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    async with get_connection() as conn:
        cur = conn.cursor()
        await cur.execute(
            "SELECT id, tenant_id, email, password_hash, role, is_active, created_at FROM users WHERE email = %s",
            (req.email,),
        )
        user_row = await cur.fetchone()

        if not user_row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user_row["is_active"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended or deactivated",
            )
        if not verify_password(req.password, user_row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        user = User(
            id=user_row["id"],
            tenant_id=user_row["tenant_id"],
            email=user_row["email"],
            role=UserRole(user_row["role"]),
            is_active=user_row["is_active"],
            created_at=user_row["created_at"],
        )

        token = create_access_token(
            data={
                "sub": str(user.id),
                "tenant_id": str(user.tenant_id),
                "email": user.email,
                "role": user.role.value,
            }
        )

        # Record audit log matching db_schema.sql
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'LOGIN', 'user', %s, '{"method": "password"}'::jsonb)
            """,
            (user.tenant_id, user.id, str(user.id)),
        )
        await conn.commit()

        return TokenResponse(access_token=token, token_type="bearer", user=user)
