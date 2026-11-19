"""The applicant's original CV file is kept (encrypted) so the recruiter can open it from the applicant detail page."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.api.middleware.rate_limiter import clear_rate_limiter_state
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from tests.test_applicant_api import FORM, register, staff_and_job

pytestmark = pytest.mark.asyncio

PDF = b"%PDF-1.4\n1 0 obj<< /Type /Catalog >>endobj\n% rahasia-isi-cv-sintetis\ntrailer<< /Root 1 0 R >>\n%%EOF\n"
DOCX = b"PK\x03\x04" + b"\x00" * 64 + b"rahasia-isi-docx-sintetis"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    clear_rate_limiter_state()
    yield
    clear_rate_limiter_state()


async def applied(client, staff=None):
    staff_token, job_id, _ = staff or await staff_and_job()
    token = await register(client)
    headers = {"Authorization": "Bearer " + token}
    submitted = await client.post(f"/api/v1/tig/apply/{job_id}", json=FORM, headers=headers)
    assert submitted.status_code == 202, submitted.text
    return staff_token, job_id, submitted.json()["application_id"], headers


def upload(client, job_id, headers, content=PDF, name="cv-sari.pdf"):
    return client.put(f"/api/v1/tig/apply/{job_id}/cv", files={"file": (name, content, "application/octet-stream")}, headers=headers)


def cv_url(job_id, application_id):
    return f"/api/v1/jobs/{job_id}/tig/applications/{application_id}/cv"


async def test_recruiter_opens_the_original_pdf_and_the_view_is_audited(client):
    staff_token, job_id, application_id, headers = await applied(client)
    response = await upload(client, job_id, headers)
    assert response.status_code == 200, response.text
    staff = {"Authorization": "Bearer " + staff_token}

    detail = await client.get(f"/api/v1/jobs/{job_id}/tig/applications/{application_id}", headers=staff)
    assert detail.json()["cv"] == {"filename": "cv-sari.pdf", "size_bytes": len(PDF), "content_type": "application/pdf"}

    served = await client.get(cv_url(job_id, application_id), headers=staff)
    assert served.status_code == 200
    assert served.content == PDF
    assert served.headers["content-type"] == "application/pdf"
    assert served.headers["content-disposition"].startswith("inline")
    assert served.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in served.headers["cache-control"]

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT action FROM audit_logs WHERE target_id = %s ORDER BY id", (application_id,))
        assert "TIG_CV_VIEW" in [row["action"] for row in await cur.fetchall()]


async def test_the_stored_file_is_encrypted_at_rest(client):
    _, job_id, application_id, headers = await applied(client)
    assert (await upload(client, job_id, headers)).status_code == 200
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT content FROM tig_application_cvs WHERE application_id = %s", (application_id,))
        stored = bytes((await cur.fetchone())["content"])
    assert b"rahasia-isi-cv-sintetis" not in stored and not stored.startswith(b"%PDF")


async def test_word_files_are_offered_as_a_download_not_rendered(client):
    staff_token, job_id, application_id, headers = await applied(client)
    assert (await upload(client, job_id, headers, DOCX, "cv.docx")).status_code == 200
    served = await client.get(cv_url(job_id, application_id), headers={"Authorization": "Bearer " + staff_token})
    assert served.headers["content-type"] == DOCX_TYPE
    assert served.headers["content-disposition"].startswith("attachment")


async def test_a_second_upload_replaces_the_first(client):
    staff_token, job_id, application_id, headers = await applied(client)
    await upload(client, job_id, headers, PDF, "lama.pdf")
    newer = PDF + b"% versi baru\n"
    assert (await upload(client, job_id, headers, newer, "baru.pdf")).status_code == 200
    served = await client.get(cv_url(job_id, application_id), headers={"Authorization": "Bearer " + staff_token})
    assert served.content == newer


async def test_only_cv_files_are_accepted_whatever_the_name_says(client):
    _, job_id, _, headers = await applied(client)
    html = await upload(client, job_id, headers, b"<html><script>alert(1)</script></html>", "cv.pdf")
    assert html.status_code == 415
    empty = await upload(client, job_id, headers, b"", "cv.pdf")
    assert empty.status_code in (415, 422)


async def test_an_oversized_file_is_refused(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    _, job_id, _, headers = await applied(client)
    big = await upload(client, job_id, headers, b"%PDF-1.4\n" + b"0" * (1024 * 1024 + 10))
    assert big.status_code == 413


async def test_the_file_name_is_cleaned_before_it_is_stored_or_sent_back(client):
    staff_token, job_id, application_id, headers = await applied(client)
    assert (await upload(client, job_id, headers, PDF, '../../etc/pa"ss\r\nwd.pdf')).status_code == 200
    detail = await client.get(f"/api/v1/jobs/{job_id}/tig/applications/{application_id}", headers={"Authorization": "Bearer " + staff_token})
    name = detail.json()["cv"]["filename"]
    assert "/" not in name and '"' not in name and "\n" not in name and name.endswith(".pdf")
    served = await client.get(cv_url(job_id, application_id), headers={"Authorization": "Bearer " + staff_token})
    assert "\n" not in served.headers["content-disposition"]


async def test_upload_needs_an_account_and_an_application_of_your_own(client):
    _, job_id, application_id, headers = await applied(client)
    anonymous = await client.put(f"/api/v1/tig/apply/{job_id}/cv", files={"file": ("cv.pdf", PDF, "application/pdf")})
    assert anonymous.status_code == 401
    stranger = {"Authorization": "Bearer " + await register(client)}
    assert (await upload(client, job_id, stranger)).status_code == 404  # has not applied here
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT count(*) AS n FROM tig_application_cvs WHERE application_id = %s", (application_id,))
        assert (await cur.fetchone())["n"] == 0


async def test_staff_of_another_company_cannot_open_the_file_and_a_missing_file_is_404(client):
    staff_token, job_id, application_id, headers = await applied(client)
    staff = {"Authorization": "Bearer " + staff_token}
    detail = await client.get(f"/api/v1/jobs/{job_id}/tig/applications/{application_id}", headers=staff)
    assert detail.json()["cv"] is None
    assert (await client.get(cv_url(job_id, application_id), headers=staff)).status_code == 404

    await upload(client, job_id, headers)
    other_token, _, _ = await staff_and_job()
    other = await client.get(cv_url(job_id, application_id), headers={"Authorization": "Bearer " + other_token})
    assert other.status_code == 404
    assert (await client.get(cv_url(job_id, application_id))).status_code == 401
    assert (await client.get(cv_url(job_id, uuid4()), headers=staff)).status_code == 404
