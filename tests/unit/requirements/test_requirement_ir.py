"""Unit tests for RequirementIR, Facet Decomposition, Duration Policy, and Database Persistence (v2.1).

Tests:
1. Decomposition of requirement 'Frontend Developer' into 5 atomic facets (F1..F5).
2. Validation of DurationPolicySchema and deterministic hashing.
3. JD compilation pipeline with rule-based fallback and 9Router LLM adapter.
4. Database persistence and schema integrity for requirements, requirement_facets,
   facet_judgments, domain_durations, and facet_templates.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from src.domain.requirements.compiler import (
    compile_jd_rule_based,
    compile_job_requirements_ir,
    decompose_role_to_facets,
    extract_duration_policy,
    load_requirement_ir_from_db,
    save_domain_duration_to_db,
    save_facet_judgment_to_db,
    save_requirement_ir_to_db,
)
from src.domain.requirements.facet_templates import (
    ROLE_FACET_TEMPLATES,
    get_facet_templates_for_role,
    resolve_role_family,
    sync_facet_templates_to_database,
)
from src.domain.requirements.schemas import (
    DurationPolicySchema,
    RequirementFacet,
    RequirementIR,
    RequirementSetIR,
)
from src.infrastructure.database import get_connection

# ----------------------------------------------------------------------
# 1. Facet Decomposition Unit Tests
# ----------------------------------------------------------------------


def test_frontend_developer_facet_decomposition_5_facets():
    """Requirement 'Frontend Developer' must decompose into exactly 5 atomic facets (C3 Blueprint)."""
    facets = decompose_role_to_facets("Frontend Developer")

    assert len(facets) == 5
    assert all(isinstance(f, RequirementFacet) for f in facets)

    # Keys must be F1 through F5
    keys = [f.facet_key for f in facets]
    assert keys == ["F1", "F2", "F3", "F4", "F5"]

    # F1..F3 are mandatory core facets; F4..F5 are supporting
    assert facets[0].core is True
    assert facets[1].core is True
    assert facets[2].core is True
    assert facets[3].core is False
    assert facets[4].core is False

    # Check hypotheses
    assert "membangun komponen UI di framework SPA" in facets[0].hypothesis
    assert "mengelola state sisi klien" in facets[1].hypothesis
    assert "implementasi layout/slicing dari desain, responsive" in facets[2].hypothesis
    assert "integrasi API sisi klien" in facets[3].hypothesis
    assert "testing/performa frontend" in facets[4].hypothesis

    # Check concepts
    assert any("react" in c for c in facets[0].concepts)
    assert any("redux" in c or "state_management" in c for c in facets[1].concepts)
    assert any("css" in c or "responsive" in c for c in facets[2].concepts)

    # Test RequirementIR core/supporting properties
    req = RequirementIR(
        requirement_id="REQ-FE-01",
        description="Minimal 3 tahun pengalaman sebagai Frontend Developer",
        category="EXPERIENCE",
        kind="ROLE_EQUIVALENCE",
        importance="MUST_HAVE",
        weight=25.0,
        concepts=["role:frontend"],
        target_domains=["frontend"],
        facets=facets,
    )

    assert len(req.core_facets) == 3
    assert len(req.supporting_facets) == 2
    assert req.get_facet("F1") is not None
    assert req.get_facet("F1").core is True
    assert req.get_facet("F99") is None


def test_other_roles_decomposition():
    """All 6 standard roles (backend, fullstack, data, qa, devops) must decompose into 5 facets."""
    roles = [r for r in ROLE_FACET_TEMPLATES if r != "frontend"]
    for r in roles:
        facets = get_facet_templates_for_role(r)
        assert len(facets) == 5, f"Role {r} should decompose into 5 facets"
        cores = [f for f in facets if f.core]
        supps = [f for f in facets if not f.core]
        assert len(cores) == 3
        assert len(supps) == 2


def test_resolve_role_family_normalization():
    """Role titles with various spellings and seniority map to canonical families."""
    assert resolve_role_family("Senior Frontend Engineer") == "frontend"
    assert resolve_role_family("Lead Back-End Developer") == "backend"
    assert resolve_role_family("Full Stack Software Engineer") == "fullstack"
    assert resolve_role_family("Data Scientist / ML Engineer") == "data"
    assert resolve_role_family("SDET / QA Automation") == "qa"
    assert resolve_role_family("Site Reliability Engineer (DevOps)") == "devops"


# ----------------------------------------------------------------------
# 2. Duration Policy Schema & Extraction Tests
# ----------------------------------------------------------------------


def test_duration_policy_schema_validation_and_hashing():
    """Validates DurationPolicySchema defaults, hash determinism, and temporal engine conversion."""
    policy = DurationPolicySchema(
        min_months=36.0,
        target_domain="frontend",
        recency_window_months=60,
    )

    assert policy.min_months == 36.0
    assert policy.target_domain == "frontend"
    assert policy.alloc_weights["PRIMARY"] == 1.0
    assert policy.alloc_weights["SECONDARY"] == 0.5
    assert policy.emp_weights["full-time"] == 1.0
    assert policy.emp_weights["magang"] == 0.5

    # Check temporal engine conversion
    runtime_policy = policy.to_duration_policy()
    assert runtime_policy.alloc_weights["PRIMARY"] == 1.0
    assert runtime_policy.recency_window_months == 60

    # Check hash determinism
    hash1 = policy.compute_hash()
    hash2 = policy.compute_hash()
    assert len(hash1) == 64
    assert hash1 == hash2

    # Different duration must yield different hash
    policy_diff = DurationPolicySchema(min_months=24.0, target_domain="frontend")
    assert policy_diff.compute_hash() != hash1


def test_extract_duration_policy_patterns():
    """Extracts duration policy from various natural language expressions."""
    pol1 = extract_duration_policy("Minimal 3 tahun pengalaman sebagai Frontend Developer", "frontend")
    assert pol1 is not None
    assert pol1.min_months == 36.0
    assert pol1.target_domain == "frontend"

    pol2 = extract_duration_policy("Pengalaman minimal 2-3 tahun di bidang backend", "backend")
    assert pol2 is not None
    assert pol2.min_months == 24.0

    pol3 = extract_duration_policy("Minimal 6 bulan magang", "frontend")
    assert pol3 is not None
    assert pol3.min_months == 6.0

    pol4 = extract_duration_policy("Menguasai React dan CSS tanpa batasan waktu")
    assert pol4 is None


# ----------------------------------------------------------------------
# 3. JD Compiler Pipeline Tests
# ----------------------------------------------------------------------


def test_compile_jd_rule_based_frontend():
    """Rule-based compiler extracts Frontend Developer requirement with 5 facets and duration."""
    jd_text = """
    Lowongan Kerja: Frontend Developer
    Kualifikasi Wajib:
    - Minimal 3 tahun pengalaman sebagai Frontend Developer
    - Menguasai React, TypeScript, dan Tailwind CSS
    - Pendidikan minimal S1 Teknik Informatika atau bidang terkait
    Nilai Tambah:
    - Memiliki pengalaman dengan Next.js dan Jest
    """

    req_set = compile_jd_rule_based(jd_text)

    assert isinstance(req_set, RequirementSetIR)
    assert "Frontend" in req_set.job_title
    assert len(req_set.requirements) >= 3

    # Primary requirement
    role_req = req_set.requirements[0]
    assert role_req.kind == "ROLE_EQUIVALENCE"
    assert role_req.importance == "MUST_HAVE"
    assert role_req.target_domains == ["frontend"]
    assert role_req.duration_policy is not None
    assert role_req.duration_policy.min_months == 36.0
    assert len(role_req.facets) == 5
    assert role_req.facets[0].facet_key == "F1"
    assert role_req.facets[0].core is True

    # Skill requirement
    skill_reqs = [r for r in req_set.requirements if r.kind == "SKILL"]
    assert len(skill_reqs) >= 1
    assert any("skill:react" in r.concepts for r in skill_reqs)

    # Education requirement
    edu_reqs = [r for r in req_set.requirements if r.kind == "EDUCATION"]
    assert len(edu_reqs) == 1
    assert edu_reqs[0].category == "EDUCATION_CERT"


@pytest.mark.asyncio
async def test_compile_job_requirements_ir_with_mock_llm():
    """Tests LLM adapter and graceful fallback if mock client fails."""
    jd_text = "Frontend Developer minimal 3 tahun pengalaman"

    # 1. Mock LLM returning valid JSON
    mock_llm_json = {
        "job_title": "Frontend Developer",
        "category_weights": {"EXPERIENCE": 40, "HARD_SKILLS": 30, "EDUCATION_CERT": 15, "ACHIEVEMENT": 15},
        "requirements": [
            {
                "requirement_id": "REQ-01",
                "description": "Minimal 3 tahun pengalaman sebagai Frontend Developer",
                "category": "EXPERIENCE",
                "kind": "ROLE_EQUIVALENCE",
                "importance": "MUST_HAVE",
                "weight": 30.0,
                "concepts": ["role:frontend"],
                "target_domains": ["frontend"],
                "duration_policy": {"min_months": 36.0, "target_domain": "frontend"},
                "accepted_evidence": ["T1", "T2", "T3", "T4"],
                "depth_floor": "L1",
                "facets": [
                    {
                        "facet_key": "F1",
                        "hypothesis": "membangun komponen UI di framework SPA",
                        "core": True,
                        "concepts": ["skill:react"],
                    },
                    {
                        "facet_key": "F2",
                        "hypothesis": "mengelola state sisi klien",
                        "core": True,
                        "concepts": ["skill:redux"],
                    },
                ],
            }
        ],
    }

    class MockGatewaySuccess:
        def verify_redacted_text(self, text: str) -> None:
            pass

        async def call_chat(self, **kwargs: Any) -> dict[str, Any]:
            return {"choices": [{"message": {"content": json.dumps(mock_llm_json)}}]}

    res = await compile_job_requirements_ir(jd_text, use_llm=True, client=MockGatewaySuccess())
    assert res.job_title == "Frontend Developer"
    assert len(res.requirements) == 1
    assert len(res.requirements[0].facets) == 2

    # 2. Mock LLM failing -> triggers fallback to rule-based compiler
    class MockGatewayFailure:
        def verify_redacted_text(self, text: str) -> None:
            pass

        async def call_chat(self, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("Simulated Gateway Timeout")

    res_fallback = await compile_job_requirements_ir(jd_text, use_llm=True, client=MockGatewayFailure())
    assert len(res_fallback.requirements) >= 1
    assert res_fallback.requirements[0].kind == "ROLE_EQUIVALENCE"
    assert len(res_fallback.requirements[0].facets) == 5


# ----------------------------------------------------------------------
# 4. Database Persistence & Alembic Schema Tests
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_database_persistence_requirement_ir_and_facets():
    """Tests saving and loading RequirementIR with 5 facets against real PostgreSQL database."""
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    set_id = uuid.uuid4()

    facets = decompose_role_to_facets("Frontend Developer")
    duration_policy = DurationPolicySchema(min_months=36.0, target_domain="frontend")

    req = RequirementIR(
        requirement_id="REQ-FE-PERSIST",
        description="Minimal 3 tahun pengalaman sebagai Frontend Developer",
        category="EXPERIENCE",
        kind="ROLE_EQUIVALENCE",
        importance="MUST_HAVE",
        weight=25.0,
        concepts=["role:frontend", "skill:react"],
        target_domains=["frontend"],
        duration_policy=duration_policy,
        accepted_evidence=["T1", "T2", "T3", "T4"],
        depth_floor="L1",
        facets=facets,
        hard_filter=False,
        source_text="Minimal 3 tahun pengalaman sebagai Frontend Developer",
    )

    async with get_connection() as conn, conn.cursor() as cur:
        # Create test job and requirement set
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text)
            VALUES (%s, %s, 'Frontend Developer', 'JD text')
            """,
            (job_id, tenant_id),
        )
        await cur.execute(
            """
            INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights)
            VALUES (%s, %s, %s, 1, 'DRAFT', '{}')
            """,
            (set_id, tenant_id, job_id),
        )
        await conn.commit()

        # Save RequirementIR to DB
        r_uuid = await save_requirement_ir_to_db(conn, set_id, tenant_id, req)
        assert r_uuid is not None

        # Verify columns in requirements table directly
        await cur.execute(
            """
            SELECT target_domains, duration_policy, accepted_evidence, depth_floor
            FROM requirements
            WHERE id = %s
            """,
            (r_uuid,),
        )
        req_row = await cur.fetchone()
        assert req_row["target_domains"] == ["frontend"]
        assert req_row["depth_floor"] == "L1"
        assert req_row["accepted_evidence"] == ["T1", "T2", "T3", "T4"]

        # Verify requirement_facets table
        await cur.execute(
            """
            SELECT facet_key, hypothesis, core, concepts
            FROM requirement_facets
            WHERE requirement_uuid = %s
            ORDER BY facet_key ASC
            """,
            (r_uuid,),
        )
        facet_rows = await cur.fetchall()
        assert len(facet_rows) == 5
        assert [r["facet_key"] for r in facet_rows] == ["F1", "F2", "F3", "F4", "F5"]
        assert facet_rows[0]["core"] is True
        assert facet_rows[4]["core"] is False

        # Load back through domain loader
        loaded_req = await load_requirement_ir_from_db(conn, r_uuid)
        assert loaded_req.requirement_id == "REQ-FE-PERSIST"
        assert loaded_req.target_domains == ["frontend"]
        assert loaded_req.depth_floor == "L1"
        assert loaded_req.duration_policy is not None
        assert loaded_req.duration_policy.min_months == 36.0
        assert len(loaded_req.facets) == 5
        assert loaded_req.facets[0].facet_key == "F1"
        assert loaded_req.facets[0].core is True
        assert len(loaded_req.core_facets) == 3
        assert len(loaded_req.supporting_facets) == 2


@pytest.mark.asyncio
async def test_database_persistence_facet_judgments_and_domain_durations():
    """Tests inserting and querying facet_judgments and domain_durations tables."""
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    set_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    run_id = uuid.uuid4()
    atom_id = uuid.uuid4()

    async with get_connection() as conn, conn.cursor() as cur:
        # Prerequisites
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'BE Dev', 'JD')",
            (job_id, tenant_id),
        )
        await cur.execute(
            "INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights) VALUES (%s, %s, %s, 1, 'DRAFT', '{}')",
            (set_id, tenant_id, job_id),
        )
        await cur.execute(
            "INSERT INTO candidates (id, tenant_id, candidate_code) VALUES (%s, %s, 'CAND-IR-TEST')",
            (cand_id, tenant_id),
        )
        await cur.execute(
            """
            INSERT INTO screening_runs (id, tenant_id, job_id, requirement_set_id, as_of, status, versions)
            VALUES (%s, %s, %s, %s, '2026-10-25', 'RUNNING', '{}')
            """,
            (run_id, tenant_id, job_id, set_id),
        )
        await conn.commit()

        # 1. Test facet_judgments
        await save_facet_judgment_to_db(
            conn=conn,
            run_id=run_id,
            candidate_id=cand_id,
            requirement_id="REQ-01",
            facet_key="F1",
            tenant_id=tenant_id,
            verdict="ENTAILED",
            depth_level="L2",
            support_atom_ids=[atom_id],
            method="matcher",
            analysis="Candidate implemented 12 React SPA components with high code quality.",
            nli_p_entail=0.94,
            rationale_code="ENTAILED_HIGH_CONFIDENCE",
            superseded_by_critic=False,
        )

        await cur.execute(
            """
            SELECT verdict, depth_level, method, analysis, nli_p_entail, superseded_by_critic
            FROM facet_judgments
            WHERE run_id = %s AND candidate_id = %s AND requirement_id = %s AND facet_key = %s
            """,
            (run_id, cand_id, "REQ-01", "F1"),
        )
        fj_row = await cur.fetchone()
        assert fj_row is not None
        assert fj_row["verdict"] == "ENTAILED"
        assert fj_row["depth_level"] == "L2"
        assert fj_row["method"] == "matcher"
        assert float(fj_row["nli_p_entail"]) == pytest.approx(0.94, abs=0.01)
        assert fj_row["superseded_by_critic"] is False

        # 2. Test domain_durations
        policy = DurationPolicySchema(min_months=36.0, target_domain="frontend")
        pol_hash = policy.compute_hash()
        ledger = [{"month": "2023-01", "weight": 1.0, "entry": "exp_1"}]

        await save_domain_duration_to_db(
            conn=conn,
            run_id=run_id,
            candidate_id=cand_id,
            domain="frontend",
            tenant_id=tenant_id,
            policy_hash=pol_hash,
            months_lo=36.0,
            months_hi=42.0,
            month_ledger=ledger,
        )

        await cur.execute(
            """
            SELECT domain, policy_hash, months_lo, months_hi, month_ledger
            FROM domain_durations
            WHERE run_id = %s AND candidate_id = %s AND domain = %s
            """,
            (run_id, cand_id, "frontend"),
        )
        dd_row = await cur.fetchone()
        assert dd_row is not None
        assert dd_row["domain"] == "frontend"
        assert dd_row["policy_hash"] == pol_hash
        assert float(dd_row["months_lo"]) == 36.0
        assert float(dd_row["months_hi"]) == 42.0
        assert len(dd_row["month_ledger"]) == 1


@pytest.mark.asyncio
async def test_facet_templates_database_sync():
    """Tests syncing all 6 standard roles facet templates into Postgres."""
    async with get_connection() as conn, conn.cursor() as cur:
        # Create prerequisite ontology_version if not present
        await cur.execute(
            """
            INSERT INTO ontology_versions (version, sha256)
            VALUES ('v2.1_test', 'testsha256')
            ON CONFLICT (version) DO NOTHING
            """
        )
        await conn.commit()

        synced_count = await sync_facet_templates_to_database(conn, version="v2.1_test")
        assert synced_count == 30  # 6 roles * 5 facets each = 30 rows

        await cur.execute(
            """
            SELECT count(*) as total
            FROM facet_templates
            WHERE version = 'v2.1_test'
            """
        )
        count_row = await cur.fetchone()
        assert count_row["total"] == 30
