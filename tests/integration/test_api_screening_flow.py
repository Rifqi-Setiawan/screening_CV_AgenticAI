"""Integration test for full Agentic v2.1 Pipeline:
Ingestion (Graph A) -> Screening (Graph B) -> Ranking API -> Candidate Detail API.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.agents.schemas.critic import (
    CriticFacetReview,
    CriticOutput,
    VerdictAction,
)
from src.agents.schemas.matcher import (
    DepthLevel,
    FacetEvaluationResult,
    FacetVerdict,
    MatcherBatchOutput,
)
from src.agents.schemas.profiler import (
    AtomTag,
    DomainAllocation,
    DomainAllocationLevel,
    EvidenceType,
    ProfilerExperience,
    ProfilerOutput,
)
from src.domain.screening_service import execute_screening_run
from src.infrastructure.database import get_connection
from src.worker.processor import process_document


@pytest.mark.asyncio
async def test_full_agentic_v21_pipeline_ingestion_screening_and_api(
    client: httpx.AsyncClient,
    recruiter_token: str,
) -> None:
    headers = {"Authorization": f"Bearer {recruiter_token}"}
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # 1. Create Job and compile/approve requirements
    j_res = await client.post(
        "/api/v1/jobs",
        json={
            "title": "Senior Backend Engineer",
            "jd_text": "Dibutuhkan Senior Backend Engineer dengan pengalaman Python dan PostgreSQL minimal 3 tahun.",
        },
        headers=headers,
    )
    assert j_res.status_code == 201
    job_id = uuid.UUID(j_res.json()["id"])

    c_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/compile", headers=headers)
    assert c_res.status_code == 201

    appr_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/approve", headers=headers)
    assert appr_res.status_code == 200

    # 2. Ingest CV Document
    doc_id = uuid.uuid4()
    raw_pdf_text = """
    Budi Santoso
    Email: budi.santoso@example.com
    Telepon: 081234567890

    Pengalaman Kerja:
    Backend Engineer di PT Maju Mundur (Januari 2021 - Sekarang)
    - Membangun REST API performa tinggi menggunakan Python FastAPI dan database PostgreSQL.
    - Mengoptimasi kueri PostgreSQL dan arsitektur microservices.
    - Mengembangkan sistem autentikasi OAuth2 dan enkripsi pgcrypto.
    """

    storage_key = f"tenants/{tenant_id}/jobs/{job_id}/cv_budi.pdf"
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO documents (
                id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status
            )
            VALUES (%s, %s, %s, %s, 100, %s, %s, 'PROCESSING')
            """,
            (
                doc_id,
                tenant_id,
                job_id,
                "cv_budi.pdf",
                "sha256_mock_hash_budi",
                storage_key,
            ),
        )
        await conn.commit()

    from pathlib import Path

    from src.infrastructure.config import settings

    vault_file = Path(settings.STORAGE_VAULT_PATH) / str(tenant_id) / storage_key
    vault_file.parent.mkdir(parents=True, exist_ok=True)
    vault_file.write_bytes(b"%PDF-1.4 mock pdf content")

    from src.worker.sanitizer import SanitizeResult

    mock_san = SanitizeResult(
        is_valid=True,
        status="READY",
        extracted_text=raw_pdf_text,
        sha256="sha256_mock_hash_budi",
        file_type="pdf",
    )
    mock_extracted_profile = {
        "identity": {
            "full_name": "Budi Santoso",
            "email": "budi.santoso@example.com",
            "phone": "081234567890",
        },
        "headline": "Senior Backend Engineer",
        "experiences": [
            {
                "entry_id": "exp_1",
                "title": "Backend Engineer",
                "organization": "PT Maju Mundur",
                "start_date": "2021-01",
                "end_date": None,
                "is_current": True,
                "description": "Membangun REST API performa tinggi menggunakan Python FastAPI dan database PostgreSQL.",
                "bullets": [
                    {"text": "Membangun REST API performa tinggi menggunakan Python FastAPI dan database PostgreSQL."},
                    {"text": "Mengoptimasi kueri PostgreSQL dan arsitektur microservices."},
                    {"text": "Mengembangkan sistem autentikasi OAuth2 dan enkripsi pgcrypto."},
                ],
            }
        ],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
    }

    # Mock profiler output to ensure deterministic, offline testing
    mock_profiler_output = ProfilerOutput(
        experiences=[
            ProfilerExperience(
                entry_ref="exp_1",
                domain_allocations=[
                    DomainAllocation(
                        domain="backend_development",
                        level=DomainAllocationLevel.PRIMARY,
                        support_atom_ids=[],
                        code_atom_ratio=0.8,
                    )
                ],
            )
        ],
        atom_tags=[
            AtomTag(
                atom_id="atom_exp_1_1",
                domains=["backend_development"],
                activities=["software_engineering"],
                concepts=["python", "fastapi", "postgresql"],
                evidence_type=EvidenceType.USAGE,
                impact_quantified=False,
            )
        ],
    )

    with (
        patch("src.worker.processor.sanitize_file", return_value=mock_san),
        patch("src.worker.processor.extract_candidate_profile", return_value=mock_extracted_profile),
        patch(
            "src.domain.pipeline.profiling_pipeline.run_profiler_agent",
            new_callable=AsyncMock,
            return_value=mock_profiler_output,
        ),
    ):
        # Process document through processor (Graph A)
        await process_document(doc_id)

    # Verify Graph A artifacts in database
    async with get_connection() as conn, conn.cursor() as cur:
        # Candidate profile
        await cur.execute(
            "SELECT id, full_text_redacted FROM candidate_profiles WHERE document_id = %s",
            (doc_id,),
        )
        prof_row = await cur.fetchone()
        assert prof_row is not None
        profile_id = prof_row["id"]

        # Evidence atoms
        await cur.execute("SELECT count(*) as cnt FROM evidence_atoms WHERE profile_id = %s", (profile_id,))
        ea_row = await cur.fetchone()
        assert ea_row["cnt"] > 0

        # Redaction offset map
        await cur.execute("SELECT count(*) as cnt FROM redaction_offset_maps WHERE document_id = %s", (doc_id,))
        rom_row = await cur.fetchone()
        assert rom_row["cnt"] == 1

        # Experience entries
        await cur.execute("SELECT count(*) as cnt FROM experience_entries WHERE profile_id = %s", (profile_id,))
        ee_row = await cur.fetchone()
        assert ee_row["cnt"] > 0

        # Experience domain allocations
        await cur.execute(
            """
            SELECT count(*) as cnt FROM experience_domain_allocations eda
            JOIN experience_entries ee ON ee.id = eda.experience_id
            WHERE ee.profile_id = %s
            """,
            (profile_id,),
        )
        eda_row = await cur.fetchone()
        assert eda_row["cnt"] > 0

    # 3. Create Screening Run
    run_res = await client.post(
        f"/api/v1/jobs/{job_id}/screenings",
        json={"use_verifier": False},
        headers=headers,
    )
    assert run_res.status_code == 202
    run_id = uuid.UUID(run_res.json()["screening_run_id"])

    # Execute screening run (Graph B)
    # Mock LLM calls in Matcher and Critic to be deterministic & fast
    async def mock_matcher_fn(facets, candidate_atoms, **kwargs):
        evals = []
        supp = [candidate_atoms[0].atom_key] if candidate_atoms else []
        for f in facets:
            fkey = f.facet_key if hasattr(f, "facet_key") else f.get("facet_key", "")
            evals.append(
                FacetEvaluationResult(
                    facet_key=fkey,
                    analysis="Kandidat membuktikan pengalaman backend dengan FastAPI dan PostgreSQL.",
                    verdict=FacetVerdict.ENTAILED,
                    depth_level=DepthLevel.L3,
                    support_atoms=supp,
                )
            )
        return MatcherBatchOutput(evaluations=evals)

    async def mock_critic_fn(critic_input, **kwargs):
        inp = critic_input if hasattr(critic_input, "judgments") else critic_input
        cid = str(getattr(inp, "candidate_id", "cand_1"))
        reviews = []
        for j in getattr(inp, "judgments", []):
            fkey = getattr(j, "facet_key", "")
            supp = getattr(j, "support_atoms", [])
            reviews.append(
                CriticFacetReview(
                    facet_key=fkey,
                    analysis="Review adversarial mengonfirmasi bukti FastAPI.",
                    verdict_action=VerdictAction.CONFIRM,
                    final_verdict=FacetVerdict.ENTAILED,
                    reasoning="Bukti kuat.",
                    depth_level=DepthLevel.L3,
                    support_atoms=supp,
                    is_disagreement=False,
                )
            )
        return CriticOutput(candidate_id=cid, facet_reviews=reviews)

    with (
        patch("src.domain.pipeline.screening_pipeline.run_matcher_agent", side_effect=mock_matcher_fn),
        patch("src.domain.pipeline.screening_pipeline.run_critic_agent", side_effect=mock_critic_fn),
    ):
        res_exec = await execute_screening_run(run_id)

    assert res_exec["status"] == "COMPLETED"

    # 4. Check Rankings Endpoint
    rank_res = await client.get(
        f"/api/v1/jobs/{job_id}/screenings/{run_id}/rankings",
        headers=headers,
    )
    assert rank_res.status_code == 200
    rank_data = rank_res.json()
    assert "rankings" in rank_data
    assert len(rank_data["rankings"]) == 1

    first_cand = rank_data["rankings"][0]
    cand_id_str = first_cand["candidate_id"]
    assert "facet_judgments" in first_cand
    assert len(first_cand["facet_judgments"]) > 0
    assert "domain_durations" in first_cand
    assert "critic_reviews" in first_cand
    assert "grounding_atoms" in first_cand

    # Check facet judgment fields
    fj_item = first_cand["facet_judgments"][0]
    assert "verdict" in fj_item
    assert "depth_level" in fj_item
    assert "analysis" in fj_item
    assert "support_atom_ids" in fj_item

    # 5. Check Candidate Detail Endpoint
    detail_res = await client.get(
        f"/api/v1/jobs/{job_id}/screenings/{run_id}/candidates/{cand_id_str}",
        headers=headers,
    )
    assert detail_res.status_code == 200
    detail_data = detail_res.json()

    assert detail_data["candidate_id"] == cand_id_str
    assert "facet_judgments" in detail_data
    assert len(detail_data["facet_judgments"]) > 0
    assert "domain_durations" in detail_data
    assert "critic_reviews" in detail_data
    assert "grounding_atoms" in detail_data

    # 6. Recruiter assist (v2.2): probes, interview answers (re-score), Copilot tools + audit trail
    base = f"/api/v1/jobs/{job_id}/screenings/{run_id}"
    probes_res = await client.get(f"{base}/candidates/{cand_id_str}/probes?budget=3", headers=headers)
    assert probes_res.status_code == 200
    probes_data = probes_res.json()
    assert probes_data["budget"] == 3 and len(probes_data["probes"]) <= 3
    assert all(p["status"] == "PENDING_APPROVAL" for p in probes_data["probes"])

    facet_key = first_cand["facet_judgments"][0]["facet_key"]
    ans_res = await client.post(
        f"{base}/candidates/{cand_id_str}/interview-answers",
        json={
            "answers": [
                {
                    "facet_key": facet_key,
                    "rating": "STRONG",
                    "answer_text": "Saya merancang dan memimpin migrasi skema.",
                }
            ]
        },
        headers=headers,
    )
    assert ans_res.status_code == 200
    ans_data = ans_res.json()
    assert ans_data["adjusted_facets"] == [facet_key]
    assert ans_data["interview_atoms"][0]["kind"] == "interview_answer"
    assert "INTERVIEW_ADJUSTED" in ans_data["after"]["flags"]
    bad_ans = await client.post(
        f"{base}/candidates/{cand_id_str}/interview-answers",
        json={"answers": [{"facet_key": "NOPE", "rating": "STRONG"}]},
        headers=headers,
    )
    assert bad_ans.status_code == 422

    cop_res = await client.post(
        f"{base}/copilot", json={"tool": "explain_score", "args": {"candidate_id": cand_id_str}}, headers=headers
    )
    assert cop_res.status_code == 200
    explained = cop_res.json()["result"]
    assert explained["candidate"] == cand_id_str.replace("-", "")[:8]
    assert "file_name" not in str(explained) and "cv_budi" not in str(explained)

    refused = await client.post(
        f"{base}/copilot",
        json={
            "tool": "explain_score",
            "args": {"candidate_id": cand_id_str},
            "draft_answer": "Kandidat ini beragama Islam dan sudah menikah.",
        },
        headers=headers,
    )
    assert refused.status_code == 422 and "atribut terlindungi" in refused.json()["detail"]

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT allowed, count(*) AS n FROM copilot_audit_log WHERE run_id = %s GROUP BY allowed", (run_id,)
        )
        audit = {r["allowed"]: r["n"] for r in await cur.fetchall()}
    assert audit == {True: 1, False: 1}
