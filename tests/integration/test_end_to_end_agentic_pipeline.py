"""End-to-End Integration Tests for Agentic CV Screening Pipeline (Blueprint v2.1).

Verifies the 3 Core Industrial Problems solved by Blueprint v2.1:
1. Problem 1 (Title Bias): Candidate with title 'Software Engineer' working on React/Redux
   applying for 'Frontend Developer' -> Graph A profiles experience -> Graph B matches facets ->
   evaluated as STRONG / Band A.
2. Problem 2 (Fragmented Experience Accumulation): Candidate with fragmented backend history
   (18 mos Backend + 6 mos Magang @0.5 + 12 mos Backend) applying for 'Backend 3 Tahun' ->
   Calendar union accumulates exactly 33 months without double counting -> evaluated accurately as PARTIAL.
3. Problem 3 (Adversarial Keyword Stuffing / Hidden Text): CV with hidden micro-font text
   and hollow keyword stuffing -> Visibility Gate purges hidden text, Scorer v2 enforces T0 floor
   capping at PARTIAL, and Critic Agent verifies downgrade -> evaluated as MANUAL_CHECK / Band C or R.

Also verifies full database persistence into PostgreSQL across both Graph A and Graph B.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest

from src.agents import (
    VerdictAction,
)
from src.domain.atoms import AtomKind, EvidenceAtom
from src.domain.matching.aggregator import RequirementState
from src.domain.ontology import Concept, ConceptEdge, OntologyGraph, RelationType
from src.domain.pipeline import (
    CandidateInput,
    ProfilingResult,
    ScreeningResult,
    run_profiling_pipeline,
    run_screening_pipeline,
)
from src.domain.requirements.schemas import (
    DurationPolicySchema,
    RequirementFacet,
    RequirementIR,
    RequirementSetIR,
)
from src.infrastructure.database import get_connection


class MockCombinedGateway:
    """Mock ModelGateway simulating LLM responses for Profiler, Matcher, and Critic."""

    def __init__(
        self,
        profiler_payload: dict[str, Any] | None = None,
        matcher_payload: dict[str, Any] | None = None,
        critic_payload: dict[str, Any] | None = None,
        jd_compiler_payload: dict[str, Any] | None = None,
    ):
        self.profiler_payload = profiler_payload or {}
        self.matcher_payload = matcher_payload or {}
        self.critic_payload = critic_payload or {}
        self.jd_compiler_payload = jd_compiler_payload
        self.call_history: list[dict[str, Any]] = []

    def verify_redacted_text(self, text: str) -> None:
        """Mock PII pre-flight verification."""
        pass

    async def call_chat(
        self,
        messages: list[dict[str, Any]],
        task: str = "matcher",
        tenant_id: uuid.UUID | None = None,
        json_mode: bool = True,
        model: str | None = None,
    ) -> dict[str, Any]:
        self.call_history.append({"task": task, "model": model, "messages": messages})

        if task == "profiler":
            payload = self.profiler_payload
        elif task == "critic":
            payload = self.critic_payload
        elif task == "jd_compiler":
            payload = self.jd_compiler_payload or {
                "job_title": "Frontend Developer",
                "category_weights": {"EXPERIENCE": 100},
                "requirements": [
                    {
                        "requirement_id": "REQ-01",
                        "description": "Frontend Developer",
                        "category": "EXPERIENCE",
                        "kind": "ROLE_EQUIVALENCE",
                        "importance": "MUST_HAVE",
                        "weight": 100.0,
                        "concepts": ["role:frontend"],
                        "target_domains": ["frontend"],
                        "duration_policy": {"min_months": 12.0, "target_domain": "frontend"},
                        "accepted_evidence": ["T1", "T2", "T3", "T4"],
                        "depth_floor": "L1",
                        "facets": [
                            {
                                "facet_key": "F1",
                                "hypothesis": "Pengalaman React SPA",
                                "core": True,
                                "concepts": ["skill:react"],
                            },
                            {
                                "facet_key": "F2",
                                "hypothesis": "Pengelolaan client state",
                                "core": True,
                                "concepts": ["skill:redux"],
                            },
                            {
                                "facet_key": "F3",
                                "hypothesis": "Slicing desain responsif",
                                "core": True,
                                "concepts": ["skill:tailwind"],
                            },
                            {
                                "facet_key": "F4",
                                "hypothesis": "Integrasi REST API",
                                "core": False,
                                "concepts": ["skill:axios"],
                            },
                            {
                                "facet_key": "F5",
                                "hypothesis": "Automated frontend testing",
                                "core": False,
                                "concepts": ["skill:jest"],
                            },
                        ],
                    }
                ],
            }
        else:
            payload = self.matcher_payload

        return {"raw_content": json.dumps(payload)}


def _build_test_ontology() -> OntologyGraph:
    """Constructs a deterministic ontology graph with concepts and relations."""
    ont = OntologyGraph(version="v2.1_test")
    ont.add_concept(Concept("v2.1_test", "skill:react", "React", "framework", ["reactjs", "react.js"]))
    ont.add_concept(Concept("v2.1_test", "skill:redux", "Redux", "library", ["redux toolkit", "rtk", "zustand"]))
    ont.add_concept(Concept("v2.1_test", "skill:tailwind", "Tailwind CSS", "framework", ["tailwind"]))
    ont.add_concept(Concept("v2.1_test", "skill:axios", "Axios", "library", ["rest api", "fetch", "axios"]))
    ont.add_concept(
        Concept("v2.1_test", "concept:frontend_ui", "Frontend UI", "capability", ["ui", "spa", "antarmuka"])
    )
    ont.add_concept(
        Concept("v2.1_test", "concept:state_management", "State Management", "capability", ["client state", "state"])
    )
    ont.add_concept(
        Concept("v2.1_test", "concept:backend_api", "Backend API", "capability", ["rest api", "endpoint", "crud"])
    )
    ont.add_concept(Concept("v2.1_test", "skill:python", "Python", "language", ["python3"]))
    ont.add_concept(Concept("v2.1_test", "skill:fastapi", "FastAPI", "framework", ["fastapi"]))
    ont.add_concept(Concept("v2.1_test", "skill:postgresql", "PostgreSQL", "database", ["postgres", "psql"]))

    ont.add_edge(ConceptEdge("skill:react", "concept:frontend_ui", RelationType.IMPLIES, "v2.1_test"))
    ont.add_edge(ConceptEdge("skill:redux", "concept:state_management", RelationType.IMPLIES, "v2.1_test"))
    return ont


@pytest.mark.asyncio
async def test_end_to_end_case_1_software_engineer_to_frontend_developer():
    """Test E2E Kasus 1: Problem 1 Solved (Title Bias).

    Kandidat dengan jabatan 'Software Engineer' yang mengerjakan React/Redux
    melamar posisi 'Frontend Developer':
    1. Graph A memprofilkan pengalaman dan mengalokasikan domain 'frontend' (PRIMARY).
    2. Graph B mengompilasi kriteria 'Frontend Developer' menjadi 5 facet.
    3. Matcher Agent membuktikan entailment literal atas bukti React/Redux/Tailwind.
    4. S7 Aggregator menghitung Role Equivalence:
       Semua core facet ENTAILED dan >= 2 core depth >= L2 -> RequirementState.STRONG.
    5. Scorer v2 menetapkan Band A (SHORTLIST).
    """
    ont = _build_test_ontology()
    candidate_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    # 1. Input CV Text and Profile Data
    raw_cv_text = (
        "Budi Santoso\n"
        "Pengalaman Kerja:\n"
        "Software Engineer di PT Solusi Digital (Jan 2022 - Des 2023)\n"
        "- Membangun antarmuka dashboard interaktif menggunakan framework React SPA dan Next.js.\n"
        "- Mengelola client state kompleks menggunakan Redux Toolkit dan Zustand untuk caching data.\n"
        "- Mengimplementasikan slicing desain dari Figma ke antarmuka web responsif dengan Tailwind CSS.\n"
        "- Melakukan integrasi REST API dengan Axios untuk komunikasi layanan backend.\n"
        "Keahlian: React, Redux, TypeScript, Tailwind CSS, Axios"
    )

    candidate_profile = {
        "experiences": [
            {
                "entry_id": "exp_1",
                "title": "Software Engineer",
                "organization": "PT Solusi Digital",
                "start_date": "2022-01",
                "end_date": "2023-12",
                "employment_type": "full-time",
                "bullets": [
                    "Membangun antarmuka dashboard interaktif menggunakan framework React SPA dan Next.js.",
                    "Mengelola client state kompleks menggunakan Redux Toolkit dan Zustand untuk caching data.",
                    "Mengimplementasikan slicing desain dari Figma ke antarmuka web responsif dengan Tailwind CSS.",
                    "Melakukan integrasi REST API dengan Axios untuk komunikasi layanan backend.",
                ],
            }
        ],
        "skills": [
            {"name": "React"},
            {"name": "Redux"},
            {"name": "TypeScript"},
            {"name": "Tailwind CSS"},
            {"name": "Axios"},
        ],
        "summary": "Fullstack/Software Engineer berfokus pada antarmuka pengguna web modern.",
    }

    # Profiler LLM payload
    profiler_payload = {
        "experiences": [
            {
                "entry_ref": "exp_1",
                "title_raw": "Software Engineer",
                "employment_type": "full-time",
                "date_text_start": "2022-01",
                "date_text_end": "2023-12",
                "domain_allocations": [
                    {
                        "domain": "frontend",
                        "level": "PRIMARY",
                        "support_atom_ids": ["E1.B1", "E1.B2", "E1.B3"],
                    }
                ],
            }
        ],
        "atom_tags": [
            {
                "atom_id": "E1.B1",
                "domains": ["frontend"],
                "activities": ["build_ui"],
                "concepts": ["skill:react", "concept:frontend_ui"],
                "evidence_type": "USAGE",
            },
            {
                "atom_id": "E1.B2",
                "domains": ["frontend"],
                "activities": ["state_management"],
                "concepts": ["skill:redux", "concept:state_management"],
                "evidence_type": "USAGE",
            },
            {
                "atom_id": "E1.B3",
                "domains": ["frontend"],
                "activities": ["ui_slicing"],
                "concepts": ["skill:tailwind"],
                "evidence_type": "USAGE",
            },
            {
                "atom_id": "E1.B4",
                "domains": ["frontend"],
                "activities": ["api_integration"],
                "concepts": ["skill:axios"],
                "evidence_type": "USAGE",
            },
        ],
        "flags": [],
    }

    # Matcher LLM payload: Entailed for core facets with L2 depth
    matcher_payload = {
        "evaluations": [
            {
                "facet_key": "F1",
                "analysis": "Bukti literal atom E1.B1 menunjukkan implementasi komponen React SPA secara mandiri.",
                "verdict": "ENTAILED",
                "support_atoms": ["E1.B1"],
                "depth_level": "L2",
                "rationale_code": "DIRECT_EVIDENCE",
            },
            {
                "facet_key": "F2",
                "analysis": "Bukti literal atom E1.B2 mendemonstrasikan pengelolaan client state Redux Toolkit dan Zustand.",
                "verdict": "ENTAILED",
                "support_atoms": ["E1.B2"],
                "depth_level": "L2",
                "rationale_code": "DIRECT_EVIDENCE",
            },
            {
                "facet_key": "F3",
                "analysis": "Bukti literal atom E1.B3 mengonfirmasi slicing desain Figma ke web responsif Tailwind CSS.",
                "verdict": "ENTAILED",
                "support_atoms": ["E1.B3"],
                "depth_level": "L2",
                "rationale_code": "DIRECT_EVIDENCE",
            },
            {
                "facet_key": "F4",
                "analysis": "Bukti literal atom E1.B4 memvalidasi integrasi REST API Axios.",
                "verdict": "ENTAILED",
                "support_atoms": ["E1.B4"],
                "depth_level": "L2",
                "rationale_code": "DIRECT_EVIDENCE",
            },
            {
                "facet_key": "F5",
                "analysis": "Tidak ditemukan bukti eksplisit unit testing frontend pada CV.",
                "verdict": "NOT_ENTAILED",
                "support_atoms": [],
                "depth_level": "L0",
                "rationale_code": "NO_EVIDENCE",
            },
        ],
        "flags": [],
    }

    mock_gateway = MockCombinedGateway(
        profiler_payload=profiler_payload,
        matcher_payload=matcher_payload,
    )

    # ------------------------------------------------------------------
    # Step 1: Execute Graph A (Profiling Pipeline)
    # ------------------------------------------------------------------
    profiling_res: ProfilingResult = await run_profiling_pipeline(
        profile_id=profile_id,
        raw_text=raw_cv_text,
        candidate_profile=candidate_profile,
        tenant_id=tenant_id,
        client=mock_gateway,
        ontology=ont,
        save_to_db=False,
    )

    assert len(profiling_res.atoms) > 0
    assert not profiling_res.has_hidden_text
    exp_allocations = profiling_res.profiler_output.experiences[0].domain_allocations
    assert any(a.domain == "frontend" and a.level.value == "PRIMARY" for a in exp_allocations)

    # ------------------------------------------------------------------
    # Step 2: Execute Graph B (Screening Pipeline)
    # ------------------------------------------------------------------
    jd_frontend = (
        "Posisi: Frontend Developer\n"
        "Kualifikasi:\n"
        "- Pengalaman sebagai Frontend Developer membangun aplikasi web modern\n"
        "- Menguasai React.js atau framework SPA sejenis\n"
        "- Mahir mengelola state sisi klien (Redux/Zustand)\n"
        "- Mampu melakukan slicing responsif dari desain Figma"
    )

    candidate_input = CandidateInput(
        candidate_id=candidate_id,
        profile_id=profile_id,
        atoms=profiling_res.atoms,
        raw_title="Software Engineer",
        experiences=profiling_res.profiler_output.experiences,
        atom_tags={t.atom_id: t for t in profiling_res.profiler_output.atom_tags},
    )

    screening_res: ScreeningResult = await run_screening_pipeline(
        candidates=[candidate_input],
        job_description=jd_frontend,
        tenant_id=tenant_id,
        client=mock_gateway,
        ontology=ont,
    )

    assert len(screening_res.candidates) == 1
    top_cand = screening_res.top_candidate
    assert top_cand is not None

    # Role Equivalence Check (Problem 1 verification)
    # Despite candidate title being 'Software Engineer', core facets of Frontend Developer are ENTAILED
    req_res = list(top_cand.requirement_results.values())[0]
    assert req_res.role_equivalence_met is True
    assert req_res.state == RequirementState.STRONG

    # Final recommendation and band
    assert top_cand.band == "A"
    assert top_cand.recommendation == "SHORTLIST"
    assert top_cand.final_score >= 85.0

    # Grounding transparency check
    assert len(top_cand.grounding_atoms) >= 3
    grounded_keys = {ga["atom_key"] for ga in top_cand.grounding_atoms}
    assert "E1.B1" in grounded_keys
    assert "E1.B2" in grounded_keys


@pytest.mark.asyncio
async def test_end_to_end_case_2_fragmented_temporal_backend_accumulation():
    """Test E2E Kasus 2: Problem 2 Solved (Accurate Fragmented Experience Accumulation).

    Kandidat dengan riwayat pengalaman terfragmentasi:
    - 18 bulan Backend full-time (weight 1.0 * 1.0 = 1.0) -> 18 bulan
    - 6 bulan Magang Backend (weight 1.0 * 0.5 = 0.5) -> 3 bulan
    - 12 bulan Backend full-time (weight 1.0 * 1.0 = 1.0) -> 12 bulan
    Total akumulasi kalender tepat 33 bulan tanpa dobel hitung.
    Melamar posisi 'Backend 3 Tahun' (min_months: 36):
    - 33 bulan < 36 bulan -> status evaluasi PARTIAL (bukan FALSE POSITIVE 36 bulan, bukan FALSE NEGATIVE 0).
    """
    ont = _build_test_ontology()
    candidate_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    experiences = [
        {
            "entry_ref": "exp_1",
            "title": "Backend Developer",
            "date_text_start": "2020-01",
            "date_text_end": "2021-06",  # 18 months
            "employment_type": "full-time",
            "domain_allocations": [{"domain": "backend", "level": "PRIMARY"}],
            "bullets": ["Membangun REST API backend dengan Python FastAPI."],
        },
        {
            "entry_ref": "exp_2",
            "title": "Intern Backend Engineer",
            "date_text_start": "2021-07",
            "date_text_end": "2021-12",  # 6 months internship
            "employment_type": "magang",  # weight 0.5 -> 3.0 effective months
            "domain_allocations": [{"domain": "backend", "level": "PRIMARY"}],
            "bullets": ["Membantu pengembangan endpoint REST API backend."],
        },
        {
            "entry_ref": "exp_3",
            "title": "Backend Engineer",
            "date_text_start": "2022-01",
            "date_text_end": "2022-12",  # 12 months
            "employment_type": "full-time",
            "domain_allocations": [{"domain": "backend", "level": "PRIMARY"}],
            "bullets": ["Mengembangkan arsitektur database PostgreSQL dan microservices."],
        },
    ]

    candidate_atoms = [
        EvidenceAtom(
            atom_key="exp_1_b0",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref="exp_1",
            page=1,
            char_start=0,
            char_end=50,
            red_start=0,
            red_end=50,
            text_redacted="Membangun REST API backend dengan Python FastAPI.",
            visibility="VISIBLE",
        ),
        EvidenceAtom(
            atom_key="exp_2_b0",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref="exp_2",
            page=1,
            char_start=51,
            char_end=100,
            red_start=51,
            red_end=100,
            text_redacted="Membantu pengembangan endpoint REST API backend.",
            visibility="VISIBLE",
        ),
        EvidenceAtom(
            atom_key="exp_3_b0",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref="exp_3",
            page=1,
            char_start=101,
            char_end=170,
            red_start=101,
            red_end=170,
            text_redacted="Mengembangkan arsitektur database PostgreSQL dan microservices.",
            visibility="VISIBLE",
        ),
    ]

    # Requirement Set specifying 3 years (36 months) backend experience
    req_backend_3y = RequirementIR(
        requirement_id="REQ_BACKEND_3Y",
        description="Backend Developer minimal 3 Tahun",
        category="experience",
        weight=1.0,
        importance="MUST_HAVE",
        target_domains=["backend"],
        duration_policy=DurationPolicySchema(
            min_months=36.0,
            alloc_weights={"PRIMARY": 1.0, "SECONDARY": 0.5, "INCIDENTAL": 0.0},
            emp_weights={"full-time": 1.0, "magang": 0.5, "internship": 0.5},
        ),
        facets=[
            RequirementFacet(
                facet_key="F1",
                hypothesis="Mampu mengembangkan API backend dan microservices",
                facet_type="core",
                target_domain="backend",
            )
        ],
    )
    req_set = RequirementSetIR(
        requirement_set_id=uuid.uuid4(),
        role_title="Senior Backend Developer",
        tenant_id=tenant_id,
        requirements=[req_backend_3y],
    )

    # Matcher confirms core competence is demonstrated
    matcher_payload = {
        "evaluations": [
            {
                "facet_key": "F1",
                "analysis": "Bukti pengalaman konsisten mengerjakan API backend dan microservices.",
                "verdict": "ENTAILED",
                "support_atoms": ["exp_1_b0", "exp_3_b0"],
                "depth_level": "L2",
                "rationale_code": "DIRECT_EVIDENCE",
            }
        ],
        "flags": [],
    }
    mock_gateway = MockCombinedGateway(matcher_payload=matcher_payload)

    candidate_input = CandidateInput(
        candidate_id=candidate_id,
        profile_id=profile_id,
        atoms=candidate_atoms,
        raw_title="Backend Engineer",
        experiences=experiences,
    )

    screening_res: ScreeningResult = await run_screening_pipeline(
        candidates=[candidate_input],
        requirement_set=req_set,
        tenant_id=tenant_id,
        client=mock_gateway,
        ontology=ont,
    )

    cand_res = screening_res.top_candidate
    assert cand_res is not None

    # Temporal Duration verification:
    # 18 (full-time) + 3 (magang: 6 * 0.5) + 12 (full-time) = 33.0 months exactly!
    dur_data = cand_res.domain_durations["REQ_BACKEND_3Y"]
    assert dur_data["domain"] == "backend"
    assert dur_data["months_hi"] == 33.0
    assert dur_data["min_months"] == 36.0
    assert dur_data["state"] == "PARTIAL"

    # Evaluated requirement state is accurately PARTIAL (not STRONG because 33 < 36, but not 0)
    req_res = cand_res.requirement_results["REQ_BACKEND_3Y"]
    assert req_res.state == RequirementState.PARTIAL
    assert cand_res.band in ("B", "C")


@pytest.mark.asyncio
async def test_end_to_end_case_3_keyword_stuffing_and_hidden_text_critic_downgrade():
    """Test E2E Kasus 3: Problem 3 Solved (Keyword Stuffing & Hidden Text Defense).

    CV dengan hidden text (font <4pt dan white text) serta keyword stuffing:
    1. Visibility Gate membuang hidden text span dan menetapkan flag HIDDEN_TEXT.
    2. Atomizer hanya menghasilkan atom T0 (skill mentions) dari visible text.
    3. Escalation Trigger E6 (HIDDEN_TEXT) dan E4 (T0 mentions) aktif -> Critic Agent dipanggil.
    4. Critic Agent memverifikasi bahwa klaim tidak didukung oleh pengalaman nyata -> DOWNGRADE.
    5. Scorer v2 mengunci bukti T0 maksimal PARTIAL dan memberi rekomendasi MANUAL_CHECK / Band C.
    """
    ont = _build_test_ontology()
    candidate_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    # Raw CV text: Visible text only lists keywords without bullets
    raw_cv_text = (
        "John Doe\n"
        "Ringkasan:\n"
        "Staff Software Engineer berorientasi arsitektur cloud.\n"
        "Keahlian:\n"
        "Python, React, AWS, Kubernetes, Distributed Systems, Microservices"
    )

    # Simulated PDF spans: Contains micro-font hidden text with keyword stuffing
    pdf_spans = [
        {
            "text": "John Doe",
            "size": 14.0,
            "flags": 0,
            "color": 0x000000,
            "bbox": (50, 50, 200, 70),
            "page": 1,
        },
        {
            "text": "Ringkasan: Staff Software Engineer berorientasi arsitektur cloud.",
            "size": 10.0,
            "flags": 0,
            "color": 0x000000,
            "bbox": (50, 80, 400, 100),
            "page": 1,
        },
        {
            "text": "Keahlian: Python, React, AWS, Kubernetes, Distributed Systems, Microservices",
            "size": 10.0,
            "flags": 0,
            "color": 0x000000,
            "bbox": (50, 110, 450, 130),
            "page": 1,
        },
        {
            # HIDDEN SPAN: micro-font 2.5pt (<4pt) with stuffed keywords
            "text": "Python Architect Lead Staff 10 years experience AWS Kubernetes microservices React Vue Java Go",
            "size": 2.5,
            "flags": 0,
            "color": 0xFFFFFF,  # white-on-white
            "bbox": (50, 140, 500, 145),
            "page": 1,
        },
    ]

    candidate_profile = {
        "summary": "Staff Software Engineer berorientasi arsitektur cloud.",
        "skills": [
            {"name": "Python"},
            {"name": "React"},
            {"name": "AWS"},
            {"name": "Kubernetes"},
        ],
        "experiences": [],  # Hollow: zero actual project/experience bullets
    }

    # Critic Agent payload performing adversarial downgrade
    critic_payload = {
        "candidate_id": str(candidate_id),
        "overall_reasoning": "Candidate lacks real project bullets; text is pure keyword listing.",
        "escalation_triggers": ["E6"],
        "facet_reviews": [
            {
                "facet_key": "F1",
                "analysis": (
                    "Bukti hanya berupa klaim daftar kata kunci (T0) dan teks tersembunyi berukuran 2.5pt "
                    "yang dibuang oleh visibility gate. Tidak ada riwayat proyek atau bukti delivery."
                ),
                "verdict_action": "DOWNGRADE",
                "final_verdict": "NOT_ENTAILED",
                "reasoning": "Keyword stuffing and hollow claims with hidden text detected.",
                "depth_level": "L0",
                "support_atoms": [],
                "flags": ["KEYWORD_STUFFING", "HOLLOW_CLAIM"],
            }
        ],
        "has_disagreement": True,
        "disagreement_flags": ["KEYWORD_STUFFING", "HOLLOW_CLAIM", "AGENT_DISAGREEMENT"],
        "final_recommendation": "MANUAL_CHECK",
    }

    mock_gateway = MockCombinedGateway(critic_payload=critic_payload)

    # ------------------------------------------------------------------
    # Step 1: Execute Graph A (Profiling Pipeline)
    # ------------------------------------------------------------------
    profiling_res: ProfilingResult = await run_profiling_pipeline(
        profile_id=profile_id,
        raw_text=raw_cv_text,
        pdf_spans=pdf_spans,
        candidate_profile=candidate_profile,
        tenant_id=tenant_id,
        client=mock_gateway,
        ontology=ont,
        save_to_db=False,
    )

    # Visibility Gate Verification
    assert profiling_res.has_hidden_text is True
    assert "HIDDEN_TEXT" in profiling_res.flags
    # Verify hidden span did not become an atom
    for atom in profiling_res.atoms:
        assert "10 years experience" not in atom.text_redacted
        assert atom.kind in (AtomKind.SKILL_LIST_ITEM.value, AtomKind.SUMMARY_SENTENCE.value)

    # ------------------------------------------------------------------
    # Step 2: Execute Graph B (Screening Pipeline)
    # ------------------------------------------------------------------
    req_cloud_architect = RequirementIR(
        requirement_id="REQ_CLOUD_ARCH",
        description="Lead Cloud Architect Python & Kubernetes",
        category="core",
        weight=1.0,
        importance="MUST_HAVE",
        facets=[
            RequirementFacet(
                facet_key="F1",
                hypothesis="Memiliki keahlian arsitektur cloud microservices dengan Python dan Kubernetes",
                facet_type="core",
                target_domain="backend",
            )
        ],
    )
    req_set = RequirementSetIR(
        requirement_set_id=uuid.uuid4(),
        role_title="Lead Cloud Architect",
        tenant_id=tenant_id,
        requirements=[req_cloud_architect],
    )

    candidate_input = CandidateInput(
        candidate_id=candidate_id,
        profile_id=profile_id,
        atoms=profiling_res.atoms,
        raw_title="Staff Software Engineer",
        experiences=[],
        metadata={"flags": profiling_res.flags, "has_hidden_text": True},
    )

    screening_res: ScreeningResult = await run_screening_pipeline(
        candidates=[candidate_input],
        requirement_set=req_set,
        tenant_id=tenant_id,
        client=mock_gateway,
        critic_client=mock_gateway,
        ontology=ont,
    )

    cand_res = screening_res.top_candidate
    assert cand_res is not None

    # Verify escalation triggers: E6 (HIDDEN_TEXT) triggered
    assert "E6" in cand_res.escalation_triggers

    # Verify Critic verified downgrade
    assert len(cand_res.critic_reviews) > 0
    assert cand_res.critic_reviews[0].verdict_action == VerdictAction.DOWNGRADE

    # Verify Scorer v2 defense flags and manual check / low priority recommendation
    assert (
        "HIDDEN_TEXT" in cand_res.flags
        or "T0_CAPPED_AT_PARTIAL" in cand_res.flags
        or "T0_DEPTH_FLOOR_ENFORCED" in cand_res.flags
    )
    assert cand_res.recommendation in ("MANUAL_CHECK", "LOW_PRIORITY")
    assert cand_res.band in ("C", "R")


@pytest.mark.asyncio
async def test_end_to_end_database_persistence():
    """Verify that both Graph A and Graph B persist artifacts cleanly to PostgreSQL.

    Tests insertion and retrieval across:
    - redaction_offset_maps
    - evidence_atoms
    - experience_entries & experience_domain_allocations
    - atom_tags
    - requirement_ir & requirement_facets
    - facet_judgments
    - domain_durations
    """
    ont = _build_test_ontology()
    tenant_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    document_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    run_id = uuid.uuid4()

    raw_text = "Jane Doe\nPengalaman:\nFrontend Developer di Startup X\n- Membangun UI SPA React."
    candidate_profile = {
        "experiences": [
            {
                "entry_id": "exp_db_1",
                "title": "Frontend Developer",
                "organization": "Startup X",
                "start_date": "2023-01",
                "end_date": "2023-12",
                "employment_type": "full-time",
                "bullets": ["Membangun UI SPA React."],
            }
        ],
        "skills": [{"name": "React"}],
    }

    profiler_payload = {
        "experiences": [
            {
                "entry_ref": "exp_db_1",
                "title_raw": "Frontend Developer",
                "employment_type": "full-time",
                "date_text_start": "2023-01",
                "date_text_end": "2023-12",
                "domain_allocations": [
                    {
                        "domain": "frontend",
                        "level": "PRIMARY",
                        "support_atom_ids": ["E1.B1"],
                    }
                ],
            }
        ],
        "atom_tags": [
            {
                "atom_id": "E1.B1",
                "domains": ["frontend"],
                "activities": ["build_ui"],
                "concepts": ["skill:react"],
                "evidence_type": "USAGE",
            }
        ],
        "flags": [],
    }

    matcher_payload = {
        "evaluations": [
            {
                "facet_key": "F1",
                "analysis": "Bukti React SPA valid.",
                "verdict": "ENTAILED",
                "support_atoms": ["E1.B1"],
                "depth_level": "L2",
                "rationale_code": "DIRECT_EVIDENCE",
            }
        ],
        "flags": [],
    }

    mock_gateway = MockCombinedGateway(
        profiler_payload=profiler_payload,
        matcher_payload=matcher_payload,
    )

    job_id = uuid.uuid4()
    req_set_id = uuid.uuid4()

    # 1. Prerequisite records for FK integrity
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'Frontend Test', 'JD text')",
            (job_id, tenant_id),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, sha256, status, reasons, flags, created_at, updated_at)
            VALUES (%s, %s, %s, 'cv.pdf', 'sha_db_test', 'READY', '{}', '{}', NOW(), NOW())
            """,
            (document_id, tenant_id, job_id),
        )
        await cur.execute(
            """
            INSERT INTO candidate_profiles (id, tenant_id, document_id, profile, matching_profile, extractor_version, quality, created_at)
            VALUES (%s, %s, %s, '{}', '{}', 'v2.1', '{}', NOW())
            """,
            (profile_id, tenant_id, document_id),
        )
        await cur.execute(
            "INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights) VALUES (%s, %s, %s, 1, 'APPROVED', '{}')",
            (req_set_id, tenant_id, job_id),
        )
        await cur.execute(
            "INSERT INTO candidates (id, tenant_id, candidate_code) VALUES (%s, %s, 'CAND-DB-TEST')",
            (candidate_id, tenant_id),
        )
        await cur.execute(
            """
            INSERT INTO screening_runs (id, tenant_id, job_id, requirement_set_id, as_of, status, versions)
            VALUES (%s, %s, %s, %s, '2026-10-25', 'RUNNING', '{}')
            """,
            (run_id, tenant_id, job_id, req_set_id),
        )
        await conn.commit()

    # 2. Run Graph A with save_to_db=True
    async with get_connection() as conn:
        profiling_res = await run_profiling_pipeline(
            profile_id=profile_id,
            raw_text=raw_text,
            candidate_profile=candidate_profile,
            document_id=document_id,
            tenant_id=tenant_id,
            client=mock_gateway,
            ontology=ont,
            save_to_db=True,
            conn=conn,
        )

        # Verify evidence_atoms inserted
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) as c FROM evidence_atoms WHERE profile_id = %s",
                (profile_id,),
            )
            row = await cur.fetchone()
            assert row["c"] >= 1

            # Verify offset map inserted
            await cur.execute(
                "SELECT COUNT(*) as c FROM redaction_offset_maps WHERE document_id = %s",
                (document_id,),
            )
            row = await cur.fetchone()
            assert row["c"] == 1

        # 2. Run Graph B with save_to_db=True
        req_item = RequirementIR(
            requirement_id="REQ_DB_FE",
            description="Frontend Developer",
            category="core",
            weight=1.0,
            importance="MUST_HAVE",
            target_domains=["frontend"],
            duration_policy=DurationPolicySchema(min_months=12.0),
            facets=[
                RequirementFacet(
                    facet_key="F1",
                    hypothesis="Pengalaman React SPA",
                    facet_type="core",
                    target_domain="frontend",
                )
            ],
        )
        req_set = RequirementSetIR(
            requirement_set_id=req_set_id,
            role_title="Frontend Engineer",
            tenant_id=tenant_id,
            requirements=[req_item],
        )

        candidate_input = CandidateInput(
            candidate_id=candidate_id,
            profile_id=profile_id,
            atoms=profiling_res.atoms,
            raw_title="Frontend Developer",
            experiences=profiling_res.profiler_output.experiences,
        )

        screening_res = await run_screening_pipeline(
            candidates=[candidate_input],
            requirement_set=req_set,
            run_id=run_id,
            tenant_id=tenant_id,
            client=mock_gateway,
            ontology=ont,
            save_to_db=True,
            conn=conn,
        )

        assert len(screening_res.candidates) == 1

        # Verify DB records for Graph B
        async with conn.cursor() as cur:
            # Check requirements and facets
            await cur.execute(
                "SELECT id FROM requirements WHERE requirement_set_id = %s AND requirement_id = %s",
                (req_set.requirement_set_id, "REQ_DB_FE"),
            )
            req_row = await cur.fetchone()
            assert req_row is not None
            req_uuid = req_row["id"]

            await cur.execute(
                "SELECT COUNT(*) as c FROM requirement_facets WHERE requirement_uuid = %s AND facet_key = %s",
                (req_uuid, "F1"),
            )
            row = await cur.fetchone()
            assert row["c"] == 1

            # Check facet judgments
            await cur.execute(
                "SELECT COUNT(*) as c FROM facet_judgments WHERE run_id = %s AND candidate_id = %s",
                (run_id, candidate_id),
            )
            row = await cur.fetchone()
            assert row["c"] >= 1

            # Check domain durations
            await cur.execute(
                "SELECT COUNT(*) as c FROM domain_durations WHERE run_id = %s AND candidate_id = %s",
                (run_id, candidate_id),
            )
            row = await cur.fetchone()
            assert row["c"] == 1
