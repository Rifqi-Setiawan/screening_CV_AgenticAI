import uuid
from datetime import date

import httpx
import pytest
import pytest_asyncio

from src.domain.auth import create_access_token
from src.domain.jd_compiler import compile_job_requirements
from src.domain.models import UserRole
from src.domain.policy_linter import lint_text
from src.infrastructure.database import get_connection

TEST_TENANT = uuid.uuid4()
ADMIN_USER_1 = uuid.uuid4()
ADMIN_USER_2 = uuid.uuid4()
RECRUITER_USER = uuid.uuid4()


@pytest_asyncio.fixture
async def setup_users():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (id, tenant_id, email, password_hash, role)
            VALUES (%s, %s, %s, 'hash', 'admin'),
                   (%s, %s, %s, 'hash', 'admin'),
                   (%s, %s, %s, 'hash', 'recruiter')
            ON CONFLICT (email) DO NOTHING
            """,
            (
                ADMIN_USER_1,
                TEST_TENANT,
                f"admin1_{ADMIN_USER_1}@elig.com",
                ADMIN_USER_2,
                TEST_TENANT,
                f"admin2_{ADMIN_USER_2}@elig.com",
                RECRUITER_USER,
                TEST_TENANT,
                f"rec_{RECRUITER_USER}@elig.com",
            ),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_eligibility_rule_crud_and_lifecycle(client: httpx.AsyncClient, setup_users):
    admin1_token = create_access_token(
        {
            "sub": str(ADMIN_USER_1),
            "tenant_id": str(TEST_TENANT),
            "email": f"admin1_{ADMIN_USER_1}@elig.com",
            "role": UserRole.ADMIN.value,
        }
    )
    admin2_token = create_access_token(
        {
            "sub": str(ADMIN_USER_2),
            "tenant_id": str(TEST_TENANT),
            "email": f"admin2_{ADMIN_USER_2}@elig.com",
            "role": UserRole.ADMIN.value,
        }
    )
    recruiter_token = create_access_token(
        {
            "sub": str(RECRUITER_USER),
            "tenant_id": str(TEST_TENANT),
            "email": f"rec_{RECRUITER_USER}@elig.com",
            "role": UserRole.RECRUITER.value,
        }
    )

    admin1_h = {"Authorization": f"Bearer {admin1_token}"}
    admin2_h = {"Authorization": f"Bearer {admin2_token}"}
    recruiter_h = {"Authorization": f"Bearer {recruiter_token}"}

    job_id = uuid.uuid4()
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'MT Job', 'JD')",
            (job_id, TEST_TENANT),
        )
        await conn.commit()

    # 1. Validation tests
    # 1a. Invalid years (10 < 15) -> 422
    r_bad_years = await client.post(
        f"/api/v1/jobs/{job_id}/eligibility-rules",
        json={
            "rule_type": "AGE_MAX",
            "value": {"years": 10},
            "basis_category": "KARAKTERISTIK_JABATAN",
            "justification": "Program Management Trainee operasional lapangan 5 tahun ikatan dinas",
            "reference_date": str(date.today()),
        },
        headers=recruiter_h,
    )
    assert r_bad_years.status_code == 422

    # 1b. GENDER allowed both ['M', 'F'] -> 422
    r_bad_gender = await client.post(
        f"/api/v1/jobs/{job_id}/eligibility-rules",
        json={
            "rule_type": "GENDER",
            "value": {"allowed": ["M", "F"]},
            "basis_category": "KARAKTERISTIK_JABATAN",
            "justification": "Program Management Trainee operasional lapangan 5 tahun ikatan dinas",
            "reference_date": str(date.today()),
        },
        headers=recruiter_h,
    )
    assert r_bad_gender.status_code == 422

    # 1c. Short justification (< 30 chars) -> 422
    r_short = await client.post(
        f"/api/v1/jobs/{job_id}/eligibility-rules",
        json={
            "rule_type": "AGE_MAX",
            "value": {"years": 27},
            "basis_category": "KARAKTERISTIK_JABATAN",
            "justification": "Kebutuhan tim",
            "reference_date": str(date.today()),
        },
        headers=recruiter_h,
    )
    assert r_short.status_code == 422

    # 1d. Generic justification -> 422 JUSTIFICATION_TOO_GENERIC
    r_generic = await client.post(
        f"/api/v1/jobs/{job_id}/eligibility-rules",
        json={
            "rule_type": "AGE_MAX",
            "value": {"years": 27},
            "basis_category": "KARAKTERISTIK_JABATAN",
            "justification": "Sesuai kebutuhan perusahaan yang berlaku saat ini",
            "reference_date": str(date.today()),
        },
        headers=recruiter_h,
    )
    assert r_generic.status_code == 422
    assert "JUSTIFICATION_TOO_GENERIC" in str(r_generic.json())

    # 2. Recruiter creates valid rule -> 201 DRAFT
    good_payload = {
        "rule_type": "AGE_MAX",
        "value": {"years": 27},
        "basis_category": "KARAKTERISTIK_JABATAN",
        "justification": "Program Management Trainee operasional lapangan 5 tahun ikatan dinas",
        "reference_date": str(date.today()),
    }
    r_create = await client.post(f"/api/v1/jobs/{job_id}/eligibility-rules", json=good_payload, headers=recruiter_h)
    assert r_create.status_code == 201
    rule_data = r_create.json()
    rule_id = rule_data["id"]
    assert rule_data["status"] == "DRAFT"

    # 3. Create second rule with same rule_type -> 409 Conflict
    r_dup = await client.post(f"/api/v1/jobs/{job_id}/eligibility-rules", json=good_payload, headers=recruiter_h)
    assert r_dup.status_code == 409

    # 4. Recruiter tries to approve rule -> 403 Forbidden
    r_rec_app = await client.post(f"/api/v1/jobs/{job_id}/eligibility-rules/{rule_id}/approve", headers=recruiter_h)
    assert r_rec_app.status_code == 403

    # 5. Admin 1 creates rule and tries to self-approve -> 403 FOUR_EYES_REQUIRED
    r_adm_create = await client.post(
        f"/api/v1/jobs/{job_id}/eligibility-rules",
        json={
            "rule_type": "GENDER",
            "value": {"allowed": ["F"]},
            "basis_category": "KARAKTERISTIK_JABATAN",
            "justification": "Kebutuhan perawat asrama putri sesuai regulasi asrama santri",
            "reference_date": str(date.today()),
        },
        headers=admin1_h,
    )
    assert r_adm_create.status_code == 201
    gender_rule_id = r_adm_create.json()["id"]

    r_self_app = await client.post(
        f"/api/v1/jobs/{job_id}/eligibility-rules/{gender_rule_id}/approve", headers=admin1_h
    )
    assert r_self_app.status_code == 403
    assert "FOUR_EYES_REQUIRED" in str(r_self_app.json())

    # 6. Admin 2 approves Admin 1's rule -> 200 OK
    r_other_app = await client.post(
        f"/api/v1/jobs/{job_id}/eligibility-rules/{gender_rule_id}/approve", headers=admin2_h
    )
    assert r_other_app.status_code == 200
    assert r_other_app.json()["status"] == "APPROVED"

    # 7. PATCH approved rule -> 409 Conflict
    r_patch = await client.patch(
        f"/api/v1/jobs/{job_id}/eligibility-rules/{gender_rule_id}",
        json={"value": {"allowed": ["M"]}},
        headers=admin1_h,
    )
    assert r_patch.status_code == 409

    # 8. DELETE approved rule -> 409 Conflict
    r_del = await client.delete(f"/api/v1/jobs/{job_id}/eligibility-rules/{gender_rule_id}", headers=admin1_h)
    assert r_del.status_code == 409

    # 9. Revoke approved rule -> 200 OK
    r_revoke = await client.post(
        f"/api/v1/jobs/{job_id}/eligibility-rules/{gender_rule_id}/revoke",
        json={"reason": "Perubahan kebijakan asrama putri menjadi asrama campuran"},
        headers=admin2_h,
    )
    assert r_revoke.status_code == 200
    assert r_revoke.json()["status"] == "REVOKED"


@pytest.mark.asyncio
async def test_jd_compiler_demographic_extraction_and_suggestion():
    jd = """Kualifikasi Wajib:
- Usia maksimal 27 tahun
- Diutamakan wanita
- Menguasai Microsoft Excel
- Pengalaman minimal 2 tahun sebagai Data Analyst"""

    res = await compile_job_requirements(jd)
    # Requirements must NOT contain age or gender
    req_descs = [r["description"].lower() for r in res["requirements"]]
    assert not any("usia" in d or "umur" in d for d in req_descs)
    assert not any("wanita" in d or "gender" in d for d in req_descs)

    # Suggestions must contain AGE_MAX and GENDER
    sugg = res.get("eligibility_suggestions", [])
    assert len(sugg) >= 2
    types = [s["rule_type"] for s in sugg]
    assert "AGE_MAX" in types
    assert "GENDER" in types

    age_sugg = next(s for s in sugg if s["rule_type"] == "AGE_MAX")
    assert age_sugg["value"]["years"] == 27

    gender_sugg = next(s for s in sugg if s["rule_type"] == "GENDER")
    assert gender_sugg["value"]["allowed"] == ["F"]


def test_policy_linter_distinguishes_prohibited_and_administrative():
    # Prohibited appearance & religion
    l1 = lint_text("Kandidat berpenampilan menarik dan beragama X")
    assert any(f.startswith("PROHIBITED_") for f in l1["prohibited_flags"])
    assert l1["is_valid"] is False

    # Administrative only age
    l2 = lint_text("Usia maksimal 25 tahun")
    assert len(l1["prohibited_flags"]) > 0
    assert len(l2["prohibited_flags"]) == 0
    assert "ADMIN_ONLY_AGE" in l2["admin_flags"]
