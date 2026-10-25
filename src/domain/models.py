"""Domain models and enum types for CV Screening."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"


class User(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    role: UserRole
    is_active: bool = True
    created_at: datetime


class UserInDB(User):
    password_hash: str


class TokenData(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    role: UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User


class HealthResponse(BaseModel):
    status: str
    app_env: str
    database: str
    pgvector_version: str | None
    active_services: list[str] = Field(default_factory=list)
    timestamp: datetime


class JobCreate(BaseModel):
    title: str
    jd_text: str
    location: str | None = None
    employment_type: str | None = None
    external_ref: str | None = None


class JobUpdate(BaseModel):
    title: str | None = None
    location: str | None = None
    employment_type: str | None = None
    status: str | None = None


class JobResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    status: str
    location: str | None = None
    employment_type: str | None = None
    external_ref: str | None = None
    jd_text: str | None = None
    created_at: datetime
    cv_count: int = 0
