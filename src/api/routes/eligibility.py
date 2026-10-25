"""Administrative Eligibility Gate rules management and approval endpoints (FX-24 Revision 2)."""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user, get_job_for_tenant, require_role
from src.domain.models import User, UserRole
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

router = APIRouter(tags=["Eligibility Rules"])

GENERIC_JUSTIFICATIONS = {
    "sesuai kebutuhan",
    "kebijakan perusahaan",
    "permintaan user",
    "sesuai kebutuhan perusahaan",
}


class EligibilityRuleCreate(BaseModel):
    rule_type: Literal["AGE_MAX", "AGE_MIN", "GENDER"]
    value: dict[str, Any]
    basis_category: Literal["KARAKTERISTIK_JABATAN", "REGULASI_SEKTOR", "PROGRAM_KHUSUS", "LAINNYA"]
    justification: str = Field(..., min_length=30, description="HR legal justification required by SE Menaker")
    reference_date: date


class EligibilityRuleUpdate(BaseModel):
    value: dict[str, Any] | None = None
    basis_category: Literal["KARAKTERISTIK_JABATAN", "REGULASI_SEKTOR", "PROGRAM_KHUSUS", "LAINNYA"] | None = None
    justification: str | None = Field(default=None, min_length=30)
    reference_date: date | None = None


class EligibilityRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=10)


def _validate_rule_data(rule_type: str, value: dict[str, Any], justification: str, reference_date: date) -> None:
    # 1. Justification generic check
    norm_j = " ".join(justification.lower().split())
    if norm_j in GENERIC_JUSTIFICATIONS or any(g in norm_j for g in GENERIC_JUSTIFICATIONS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "JUSTIFICATION_TOO_GENERIC",
                "message": "Justifikasi terlalu umum. Jelaskan alasan spesifik keterkaitan karakteristik jabatan dengan syarat administratif.",
            },
        )

    # 2. Reference date within +/- 365 days
    today = date.today()
    delta_days = abs((reference_date - today).days)
    if delta_days > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="reference_date wajib dalam rentang 365 hari ke belakang atau ke depan.",
        )

    # 3. Value validation
    if rule_type in ("AGE_MAX", "AGE_MIN"):
        years = value.get("years")
        if not isinstance(years, int) or years < 15 or years > 70:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{rule_type} mewajibkan value.years berupa integer antara 15 dan 70.",
            )
    elif rule_type == "GENDER":
        allowed = value.get("allowed")
        if not isinstance(allowed, list) or len(allowed) == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="GENDER mewajibkan value.allowed berupa list tidak kosong subset dari ['M', 'F'].",
            )
        if not set(allowed).issubset({"M", "F"}):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="value.allowed hanya boleh berisi 'M' atau 'F'.",
            )
        if set(allowed) == {"M", "F"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Aturan yang mengizinkan kedua gender ('M' dan 'F') tidak bermakna dan ditolak.",
            )


@router.get("/api/v1/jobs/{job_id}/eligibility-rules")
async def list_eligibility_rules(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            """
            SELECT id, tenant_id, job_id, rule_type, value, basis_category, justification,
                   reference_date, status, created_by, created_at, approved_by, approved_at,
                   revoked_by, revoked_at, revoke_reason
            FROM eligibility_rules
            WHERE job_id = %s AND tenant_id = %s
            ORDER BY created_at ASC
            """,
            (job_id, current_user.tenant_id),
        )
        return [dict(r) for r in await cur.fetchall()]


@router.post("/api/v1/jobs/{job_id}/eligibility-rules", status_code=status.HTTP_201_CREATED)
async def create_eligibility_rule(
    job_id: uuid.UUID,
    payload: EligibilityRuleCreate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    _validate_rule_data(payload.rule_type, payload.value, payload.justification, payload.reference_date)

    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        # Check conflicting active rule (DRAFT or APPROVED) of same type
        await cur.execute(
            """
            SELECT id FROM eligibility_rules
            WHERE job_id = %s AND tenant_id = %s AND rule_type = %s AND status IN ('DRAFT', 'APPROVED')
            """,
            (job_id, current_user.tenant_id, payload.rule_type),
        )
        if await cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Aturan aktif untuk tipe {payload.rule_type} sudah ada untuk lowongan ini.",
            )

        # Cross rule validation: check AGE_MIN <= AGE_MAX
        if payload.rule_type == "AGE_MAX":
            await cur.execute(
                """
                SELECT value FROM eligibility_rules
                WHERE job_id = %s AND tenant_id = %s AND rule_type = 'AGE_MIN' AND status IN ('DRAFT', 'APPROVED')
                """,
                (job_id, current_user.tenant_id),
            )
            min_row = await cur.fetchone()
            if min_row:
                min_years = min_row["value"].get("years", 0)
                if min_years > payload.value.get("years", 0):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"AGE_MAX ({payload.value.get('years')}) tidak boleh lebih kecil dari AGE_MIN ({min_years}).",
                    )
        elif payload.rule_type == "AGE_MIN":
            await cur.execute(
                """
                SELECT value FROM eligibility_rules
                WHERE job_id = %s AND tenant_id = %s AND rule_type = 'AGE_MAX' AND status IN ('DRAFT', 'APPROVED')
                """,
                (job_id, current_user.tenant_id),
            )
            max_row = await cur.fetchone()
            if max_row:
                max_years = max_row["value"].get("years", 99)
                if payload.value.get("years", 0) > max_years:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"AGE_MIN ({payload.value.get('years')}) tidak boleh lebih besar dari AGE_MAX ({max_years}).",
                    )

        rule_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO eligibility_rules (
                id, tenant_id, job_id, rule_type, value, basis_category, justification,
                reference_date, status, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'DRAFT', %s)
            RETURNING id, tenant_id, job_id, rule_type, value, basis_category, justification,
                      reference_date, status, created_by, created_at
            """,
            (
                rule_id,
                current_user.tenant_id,
                job_id,
                payload.rule_type,
                json.dumps(payload.value),
                payload.basis_category,
                payload.justification,
                payload.reference_date,
                current_user.id,
            ),
        )
        row = await cur.fetchone()

        # Audit log
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'ELIGIBILITY_RULE_CREATED', 'eligibility_rule', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                str(rule_id),
                json.dumps(
                    {
                        "job_id": str(job_id),
                        "rule_type": payload.rule_type,
                        "value": payload.value,
                        "basis_category": payload.basis_category,
                    }
                ),
            ),
        )
        await conn.commit()
        return dict(row)


@router.patch("/api/v1/jobs/{job_id}/eligibility-rules/{rule_id}")
async def update_eligibility_rule(
    job_id: uuid.UUID,
    rule_id: uuid.UUID,
    payload: EligibilityRuleUpdate,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            "SELECT * FROM eligibility_rules WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (rule_id, job_id, current_user.tenant_id),
        )
        rule = await cur.fetchone()
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aturan eligibility tidak ditemukan.")
        if rule["status"] != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="RULE_NOT_EDITABLE: Hanya aturan berstatus DRAFT yang dapat dimodifikasi.",
            )

        new_val = payload.value if payload.value is not None else rule["value"]
        new_basis = payload.basis_category if payload.basis_category is not None else rule["basis_category"]
        new_just = payload.justification if payload.justification is not None else rule["justification"]
        new_ref = payload.reference_date if payload.reference_date is not None else rule["reference_date"]

        _validate_rule_data(rule["rule_type"], new_val, new_just, new_ref)

        await cur.execute(
            """
            UPDATE eligibility_rules
            SET value = %s, basis_category = %s, justification = %s, reference_date = %s
            WHERE id = %s AND tenant_id = %s
            RETURNING *
            """,
            (json.dumps(new_val), new_basis, new_just, new_ref, rule_id, current_user.tenant_id),
        )
        updated = await cur.fetchone()
        await conn.commit()
        return dict(updated)


@router.delete("/api/v1/jobs/{job_id}/eligibility-rules/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_eligibility_rule(
    job_id: uuid.UUID,
    rule_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.RECRUITER])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            "SELECT status FROM eligibility_rules WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (rule_id, job_id, current_user.tenant_id),
        )
        rule = await cur.fetchone()
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aturan eligibility tidak ditemukan.")
        if rule["status"] != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Aturan APPROVED tidak boleh dihapus demi jejak audit; gunakan aksi revoke.",
            )

        await cur.execute(
            "DELETE FROM eligibility_rules WHERE id = %s AND tenant_id = %s",
            (rule_id, current_user.tenant_id),
        )
        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'ELIGIBILITY_RULE_DELETED', 'eligibility_rule', %s, %s)
            """,
            (current_user.tenant_id, current_user.id, str(rule_id), json.dumps({"job_id": str(job_id)})),
        )
        await conn.commit()
        return {"status": "DELETED", "id": str(rule_id)}


@router.post("/api/v1/jobs/{job_id}/eligibility-rules/{rule_id}/approve", status_code=status.HTTP_200_OK)
async def approve_eligibility_rule(
    job_id: uuid.UUID,
    rule_id: uuid.UUID,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        await cur.execute(
            "SELECT id, created_by, status, rule_type, value FROM eligibility_rules WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (rule_id, job_id, current_user.tenant_id),
        )
        rule = await cur.fetchone()
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aturan eligibility tidak ditemukan.")

        if rule["status"] != "DRAFT":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Hanya aturan DRAFT yang dapat disetujui (status saat ini: {rule['status']}).",
            )

        # Four-eyes principle check
        if settings.ELIGIBILITY_FOUR_EYES and rule["created_by"] == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "FOUR_EYES_REQUIRED",
                    "message": "Persetujuan aturan administratif memerlukan verifikasi dari Admin yang berbeda (four-eyes principle).",
                },
            )

        await cur.execute(
            """
            UPDATE eligibility_rules
            SET status = 'APPROVED', approved_by = %s, approved_at = now()
            WHERE id = %s AND tenant_id = %s
            RETURNING *
            """,
            (current_user.id, rule_id, current_user.tenant_id),
        )
        updated = await cur.fetchone()

        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'ELIGIBILITY_RULE_APPROVED', 'eligibility_rule', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                str(rule_id),
                json.dumps({"job_id": str(job_id), "rule_type": rule["rule_type"]}),
            ),
        )
        await conn.commit()
        return dict(updated)


@router.post("/api/v1/jobs/{job_id}/eligibility-rules/{rule_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_eligibility_rule(
    job_id: uuid.UUID,
    rule_id: uuid.UUID,
    payload: EligibilityRevokeRequest,
    current_user: User = Depends(require_role([UserRole.ADMIN])),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)
        await cur.execute(
            "SELECT * FROM eligibility_rules WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (rule_id, job_id, current_user.tenant_id),
        )
        rule = await cur.fetchone()
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aturan eligibility tidak ditemukan.")
        if rule["status"] != "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Hanya aturan berstatus APPROVED yang dapat dicabut (revoke).",
            )

        await cur.execute(
            """
            UPDATE eligibility_rules
            SET status = 'REVOKED', revoked_by = %s, revoked_at = now(), revoke_reason = %s
            WHERE id = %s AND tenant_id = %s
            RETURNING *
            """,
            (current_user.id, payload.reason, rule_id, current_user.tenant_id),
        )
        updated = await cur.fetchone()

        await cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_id, action, target_type, target_id, metadata)
            VALUES (%s, %s, 'ELIGIBILITY_RULE_REVOKED', 'eligibility_rule', %s, %s)
            """,
            (
                current_user.tenant_id,
                current_user.id,
                str(rule_id),
                json.dumps({"job_id": str(job_id), "reason": payload.reason}),
            ),
        )
        await conn.commit()
        return dict(updated)


@router.get("/api/v1/jobs/{job_id}/screenings/{run_id}/eligibility-summary")
async def get_eligibility_summary(
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    top_n: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    async with get_connection() as conn, conn.cursor() as cur:
        await get_job_for_tenant(cur, job_id, current_user.tenant_id)

        # Get snapshot rules from screening_run
        await cur.execute(
            "SELECT eligibility_snapshot FROM screening_runs WHERE id = %s AND job_id = %s AND tenant_id = %s",
            (run_id, job_id, current_user.tenant_id),
        )
        run_row = await cur.fetchone()
        if not run_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening run tidak ditemukan.")

        snapshot = run_row["eligibility_snapshot"] or []

        # Count all statuses
        await cur.execute(
            """
            SELECT overall_status, COUNT(*) as cnt
            FROM candidate_eligibility
            WHERE run_id = %s AND tenant_id = %s
            GROUP BY overall_status
            """,
            (run_id, current_user.tenant_id),
        )
        counts = {"ELIGIBLE": 0, "NOT_ELIGIBLE": 0, "UNKNOWN": 0, "NOT_APPLICABLE": 0}
        for r in await cur.fetchall():
            counts[r["overall_status"]] = r["cnt"]

        # Check top N impact based on scores
        await cur.execute(
            """
            SELECT cs.candidate_id, ce.overall_status
            FROM candidate_scores cs
            LEFT JOIN candidate_eligibility ce ON ce.candidate_id = cs.candidate_id AND ce.run_id = cs.run_id
            WHERE cs.run_id = %s AND cs.tenant_id = %s
            ORDER BY cs.rank ASC NULLS LAST, cs.final_score DESC
            LIMIT %s
            """,
            (run_id, current_user.tenant_id, top_n),
        )
        top_rows = await cur.fetchall()
        not_eligible_top = sum(1 for r in top_rows if r["overall_status"] == "NOT_ELIGIBLE")
        unknown_top = sum(1 for r in top_rows if r["overall_status"] == "UNKNOWN")

        return {
            "counts": counts,
            "impact": {
                "top_n": len(top_rows),
                "not_eligible_in_top_n": not_eligible_top,
                "unknown_in_top_n": unknown_top,
            },
            "rules": snapshot,
        }
