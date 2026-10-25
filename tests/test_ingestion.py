"""Integration tests for CV ingestion API, quality checks, deduplication, and extraction export."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest


@pytest.mark.asyncio
async def test_batch_upload_and_edge_cases(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}

    # 1. Create a job
    job_payload = {
        "title": "Backend Screening Test Job",
        "jd_text": "Python PostgreSQL backend engineering requirements.",
        "external_ref": "JD-01",
    }
    j_res = await client.post("/api/v1/jobs", json=job_payload, headers=headers)
    assert j_res.status_code == 201
    job_id = j_res.json()["id"]

    # 2. Upload S1, E8 (duplicate of S1), E1 (empty), E6 (encrypted), E7 (cover letter), and E3 (injection)
    cvs_core = Path("docs/spec/golden_dataset/cvs/core")
    cvs_edge = Path("docs/spec/golden_dataset/cvs/edge")

    files_to_upload = [
        (
            "files",
            ("S1_senior_backend_id.pdf", (cvs_core / "S1_senior_backend_id.pdf").read_bytes(), "application/pdf"),
        ),
        ("files", ("E8_duplicate_of_S1.pdf", (cvs_edge / "E8_duplicate_of_S1.pdf").read_bytes(), "application/pdf")),
        ("files", ("E1_empty_cv.pdf", (cvs_edge / "E1_empty_cv.pdf").read_bytes(), "application/pdf")),
        (
            "files",
            ("E6_password_protected.pdf", (cvs_edge / "E6_password_protected.pdf").read_bytes(), "application/pdf"),
        ),
        (
            "files",
            ("E7_cover_letter_not_cv.pdf", (cvs_edge / "E7_cover_letter_not_cv.pdf").read_bytes(), "application/pdf"),
        ),
        (
            "files",
            (
                "E3_hidden_prompt_injection.pdf",
                (cvs_edge / "E3_hidden_prompt_injection.pdf").read_bytes(),
                "application/pdf",
            ),
        ),
    ]

    up_res = await client.post(f"/api/v1/jobs/{job_id}/cvs", files=files_to_upload, headers=headers)
    assert up_res.status_code == 202
    assert up_res.json()["total_files"] == 6

    # 3. Check status
    st_res = await client.get(f"/api/v1/jobs/{job_id}/cvs/status", headers=headers)
    assert st_res.status_code == 200
    st_data = st_res.json()
    docs = {d["filename"]: d for d in st_data["documents"]}

    # Verify S1 is READY
    assert docs["S1_senior_backend_id.pdf"]["status"] == "READY"

    # Verify E8 is DUPLICATE of S1
    assert docs["E8_duplicate_of_S1.pdf"]["status"] == "DUPLICATE"
    assert docs["E8_duplicate_of_S1.pdf"]["duplicate_of"] == "S1_senior_backend_id.pdf"

    # Verify E1 is NEEDS_REVIEW
    assert docs["E1_empty_cv.pdf"]["status"] == "NEEDS_REVIEW"
    assert any("INSUFFICIENT_CONTENT" in r or "EMPTY_DOCUMENT" in r for r in docs["E1_empty_cv.pdf"]["reasons"])

    # Verify E6 is REJECTED (ENCRYPTED_FILE)
    assert docs["E6_password_protected.pdf"]["status"] == "REJECTED"
    assert any("ENCRYPTED_FILE" in r for r in docs["E6_password_protected.pdf"]["reasons"])

    # Verify E7 is NEEDS_REVIEW (NOT_A_CV)
    assert docs["E7_cover_letter_not_cv.pdf"]["status"] == "NEEDS_REVIEW"
    assert any("NOT_A_CV" in r for r in docs["E7_cover_letter_not_cv.pdf"]["reasons"])

    # Verify E3 is READY with PROMPT_INJECTION / HIDDEN_TEXT flags
    assert docs["E3_hidden_prompt_injection.pdf"]["status"] == "READY"
    assert "PROMPT_INJECTION" in docs["E3_hidden_prompt_injection.pdf"]["flags"]
    assert "HIDDEN_TEXT" in docs["E3_hidden_prompt_injection.pdf"]["flags"]


@pytest.mark.asyncio
async def test_extraction_export_matches_evaluator(client: httpx.AsyncClient, recruiter_token: str):
    headers = {"Authorization": f"Bearer {recruiter_token}"}

    # Create job for 15 core CVs
    j_res = await client.post(
        "/api/v1/jobs",
        json={"title": "15 Core Evaluation Job", "jd_text": "Requirements test", "external_ref": "JD-01"},
        headers=headers,
    )
    job_id = j_res.json()["id"]

    # Upload all 15 core CVs
    core_dir = Path("docs/spec/golden_dataset/cvs/core")
    files_to_upload = []
    for p in sorted(list(core_dir.glob("*.pdf")) + list(core_dir.glob("*.docx"))):
        files_to_upload.append(("files", (p.name, p.read_bytes(), "application/octet-stream")))

    up_res = await client.post(f"/api/v1/jobs/{job_id}/cvs", files=files_to_upload, headers=headers)
    assert up_res.status_code == 202

    # Get extraction export
    export_res = await client.get(f"/api/v1/jobs/{job_id}/extraction-export", headers=headers)
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert "files" in export_data
    assert len(export_data["files"]) == 15

    # Run golden dataset evaluate.py --extraction on this exact exported JSON!
    import sys

    sys.path.insert(0, "docs/spec/golden_dataset")
    from evaluate import eval_extraction

    passed = eval_extraction(export_data)
    assert passed is True, "evaluate.py --extraction failed on API export data!"


@pytest.mark.asyncio
async def test_zip_archive_cv_upload(client: httpx.AsyncClient, recruiter_token: str):
    import io
    import zipfile

    headers = {"Authorization": f"Bearer {recruiter_token}"}
    j_res = await client.post(
        "/api/v1/jobs",
        json={"title": "Zip Upload Job", "jd_text": "Python PostgreSQL backend development."},
        headers=headers,
    )
    assert j_res.status_code == 201
    job_id = j_res.json()["id"]

    # Pack 3 PDFs into in-memory zip
    cvs_core = Path("docs/spec/golden_dataset/cvs/core")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("S1_senior_backend_id.pdf", (cvs_core / "S1_senior_backend_id.pdf").read_bytes())
        z.writestr("S2_backend_fintech_en.pdf", (cvs_core / "S2_backend_fintech_en.pdf").read_bytes())
        z.writestr("M1_nodejs_backend_two_column.pdf", (cvs_core / "M1_nodejs_backend_two_column.pdf").read_bytes())
        # Add a macosx hidden file to verify sanitizer ignores it
        z.writestr("__MACOSX/._dummy.pdf", b"fake resource fork")

    files_to_upload = [("files", ("kandidat_batch.zip", buf.getvalue(), "application/zip"))]
    up_res = await client.post(f"/api/v1/jobs/{job_id}/cvs", files=files_to_upload, headers=headers)
    assert up_res.status_code == 202
    res_data = up_res.json()
    assert res_data["total_files"] == 3

    st_res = await client.get(f"/api/v1/jobs/{job_id}/cvs/status", headers=headers)
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert st_data["total"] == 3
    doc_names = {d["filename"] for d in st_data["documents"]}
    assert doc_names == {"S1_senior_backend_id.pdf", "S2_backend_fintech_en.pdf", "M1_nodejs_backend_two_column.pdf"}
