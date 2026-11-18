"""Domain models and enum types for CV Screening."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class UserRole(str, Enum):
    # MVP: recruiters are the only staff role. Applicants have separate accounts (src/api/routes/applicant.py).
    RECRUITER = "recruiter"


class User(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    role: UserRole
    is_active: bool = True
    created_at: datetime


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
    active_services: list[str] = Field(default_factory=list)
    timestamp: datetime


JobTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
JobLocation = Annotated[str, StringConstraints(strip_whitespace=True, max_length=220)]
EmploymentType = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: JobTitle
    location: JobLocation | None = None
    employment_type: EmploymentType | None = None


class JobUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: JobTitle | None = None
    location: JobLocation | None = None
    employment_type: EmploymentType | None = None


class JobResponse(BaseModel):
    id: UUID
    title: str
    status: Literal["DRAFT", "OPEN", "CLOSED"]
    location: str | None
    employment_type: str | None
    created_at: datetime
    application_count: int
