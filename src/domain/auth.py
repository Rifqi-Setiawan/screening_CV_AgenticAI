"""Authentication, JWT tokens, and RBAC utility functions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from src.domain.models import TokenData, UserRole
from src.infrastructure.config import settings


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(UTC)
    expire = now + expires_delta if expires_delta else now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


APPLICANT_TOKEN = "applicant"
_dummy_hash: str | None = None


def verify_password_or_dummy(plain_password: str, hashed_password: str | None) -> bool:
    """Runs bcrypt even for unknown accounts so response time does not reveal which emails exist."""
    global _dummy_hash
    if hashed_password is None:
        _dummy_hash = _dummy_hash or hash_password("timing-equaliser")
        verify_password(plain_password, _dummy_hash)
        return False
    return verify_password(plain_password, hashed_password)


def create_applicant_token(applicant_id: str, email: str) -> str:
    return create_access_token({"sub": applicant_id, "email": email, "typ": APPLICANT_TOKEN})


def decode_applicant_token(token: str) -> str | None:
    """Returns the applicant id for an applicant token; staff tokens are rejected."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != APPLICANT_TOKEN or not payload.get("sub"):
        return None
    return str(payload["sub"])


def decode_access_token(token: str) -> TokenData | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("typ") == APPLICANT_TOKEN:
            return None
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        email = payload.get("email")
        role_str = payload.get("role")
        if not user_id or not tenant_id or not email or not role_str:
            return None
        return TokenData(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=UserRole(role_str),
        )
    except (jwt.PyJWTError, ValueError):
        return None
