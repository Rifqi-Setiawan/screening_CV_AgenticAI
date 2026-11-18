"""Applicant accounts: register, sign in, and follow submitted applications."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.errors import UniqueViolation
from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, StringConstraints

from src.api.middleware.rate_limiter import check_rate_limit
from src.domain.auth import create_applicant_token, decode_applicant_token, hash_password, verify_password_or_dummy
from src.infrastructure.database import get_connection

router = APIRouter(prefix="/api/v1/applicant", tags=["Pelamar"])
security = HTTPBearer(auto_error=False)


def _bcrypt_length(password: str) -> str:
    # bcrypt only reads the first 72 bytes.
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Kata sandi maksimal 72 byte.")
    return password


NewPassword = Annotated[str, StringConstraints(min_length=8, max_length=72), AfterValidator(_bcrypt_length)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(Strict):
    full_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    email: EmailStr
    password: NewPassword
    consent: Literal[True]


class LoginRequest(Strict):
    email: EmailStr
    password: Annotated[str, StringConstraints(max_length=200)]


class Applicant(BaseModel):
    id: UUID
    email: str
    full_name: str


class ApplicantToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    applicant: Applicant


class ApplicantApplication(BaseModel):
    id: UUID
    job_id: UUID
    title: str
    stage: str
    created_at: datetime


async def get_current_applicant(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> Applicant:
    applicant_id = decode_applicant_token(credentials.credentials) if credentials else None
    if not applicant_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Silakan masuk sebagai pelamar.", headers={"WWW-Authenticate": "Bearer"}
        )
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id, email, full_name FROM applicants WHERE id = %s", (applicant_id,))
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Akun pelamar tidak ditemukan. Silakan masuk kembali.")
    return Applicant.model_validate(row)


def token_for(applicant: Applicant) -> ApplicantToken:
    return ApplicantToken(
        access_token=create_applicant_token(str(applicant.id), applicant.email),
        applicant=applicant,
    )


@router.post("/register", status_code=201, response_model=ApplicantToken, dependencies=[Depends(check_rate_limit(5))])
async def register(req: RegisterRequest, response: Response) -> ApplicantToken:
    response.headers["Cache-Control"] = "no-store"
    try:
        async with get_connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO applicants (email, password_hash, full_name, consent_at)
                VALUES (%s, %s, %s, now()) RETURNING id, email, full_name
                """,
                (req.email.lower(), hash_password(req.password), req.full_name),
            )
            applicant = Applicant.model_validate(await cur.fetchone())
    except UniqueViolation as error:
        raise HTTPException(409, "Email sudah terdaftar. Silakan masuk.") from error
    return token_for(applicant)


@router.post("/login", response_model=ApplicantToken, dependencies=[Depends(check_rate_limit(12))])
async def login(req: LoginRequest, response: Response) -> ApplicantToken:
    response.headers["Cache-Control"] = "no-store"
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id, email, full_name, password_hash FROM applicants WHERE lower(email) = %s",
            (req.email.lower(),),
        )
        row = await cur.fetchone()
    if not verify_password_or_dummy(req.password, row["password_hash"] if row else None) or not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email atau kata sandi salah.")
    return token_for(Applicant.model_validate(row))


@router.get("/me", response_model=Applicant)
async def me(applicant: Applicant = Depends(get_current_applicant)) -> Applicant:
    return applicant


@router.get("/applications", response_model=list[ApplicantApplication])
async def my_applications(
    response: Response, applicant: Applicant = Depends(get_current_applicant)
) -> list[ApplicantApplication]:
    response.headers["Cache-Control"] = "no-store"
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT a.id, a.job_id, j.title, a.stage, a.created_at
            FROM tig_applications a JOIN jobs j ON j.id = a.job_id
            WHERE a.applicant_id = %s ORDER BY a.created_at DESC
            """,
            (applicant.id,),
        )
        return [ApplicantApplication.model_validate(row) for row in await cur.fetchall()]
