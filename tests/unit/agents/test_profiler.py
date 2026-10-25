"""Unit tests for Profiler Agent schemas, validation, and domain profiling (v2.1)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from src.agents import (
    AtomTag,
    DomainAllocation,
    DomainAllocationLevel,
    EvidenceType,
    ProfilerExperience,
    ProfilerOutput,
    run_profiler_agent,
    save_profiler_results,
    validate_profiler_output,
)
from src.domain.atoms import AtomKind, EvidenceAtom
from src.domain.ontology import Concept, OntologyGraph
from src.infrastructure.database import get_connection


def _make_sample_atoms(entry_ref: str = "exp_0") -> list[EvidenceAtom]:
    return [
        EvidenceAtom(
            atom_key=f"{entry_ref}_bullet_0",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref=entry_ref,
            page=1,
            char_start=100,
            char_end=200,
            red_start=100,
            red_end=200,
            text_redacted="Membangun antarmuka dashboard admin menggunakan React, TypeScript, dan Tailwind CSS.",
        ),
        EvidenceAtom(
            atom_key=f"{entry_ref}_bullet_1",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref=entry_ref,
            page=1,
            char_start=201,
            char_end=310,
            red_start=201,
            red_end=310,
            text_redacted="Mengoptimalkan performa rendering halaman dan implementasi client-side state management.",
        ),
        EvidenceAtom(
            atom_key=f"{entry_ref}_bullet_2",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref=entry_ref,
            page=1,
            char_start=311,
            char_end=420,
            red_start=311,
            red_end=420,
            text_redacted="Melakukan slicing UI responsif dari Figma ke komponen web dengan cross-browser compatibility.",
        ),
    ]


def test_profiler_schema_strictness():
    """Verify strict Pydantic schemas forbid extraneous fields and enforce valid enums."""
    # Extra field forbidden
    with pytest.raises(ValidationError):
        DomainAllocation(
            domain="frontend",
            level=DomainAllocationLevel.PRIMARY,
            extra_field="disallowed",  # type: ignore[call-arg]
        )

    # Invalid enum rejected
    with pytest.raises(ValidationError):
        DomainAllocation(
            domain="frontend",
            level="INVALID_LEVEL",  # type: ignore[arg-type]
        )

    # Singular 'domain_allocation' alias accepted
    exp_dict = {
        "entry_ref": "exp_0",
        "title_raw": "Software Engineer",
        "domain_allocation": [{"domain": "frontend", "level": "PRIMARY", "support_atom_ids": ["exp_0_b0"]}],
    }
    exp = ProfilerExperience.model_validate(exp_dict)
    assert len(exp.domain_allocations) == 1
    assert exp.domain_allocations[0].domain == "frontend"


def test_software_engineer_to_frontend_primary():
    """Verify that a candidate with generic title 'Software Engineer' but dominant React/UI

    atoms is correctly validated as Frontend PRIMARY with 100% code_atom_ratio.
    """
    atoms = _make_sample_atoms(entry_ref="exp_0")
    ontology = OntologyGraph(version="v1")
    ontology.add_concept(Concept("v1", "skill:react", "React", "framework", ["reactjs"]))
    ontology.add_concept(Concept("v1", "skill:typescript", "TypeScript", "language", ["ts"]))

    raw_output = {
        "experiences": [
            {
                "entry_ref": "exp_0",
                "title_raw": "Software Engineer",
                "employment_type": "full-time",
                "date_text_start": "Jan 2021",
                "date_text_end": "Des 2022",
                "is_current": False,
                "domain_allocations": [
                    {
                        "domain": "frontend",
                        "level": "PRIMARY",
                        "support_atom_ids": [
                            "exp_0_bullet_0",
                            "exp_0_bullet_1",
                            "exp_0_bullet_2",
                        ],
                    }
                ],
            }
        ],
        "atom_tags": [
            {
                "atom_id": "exp_0_bullet_0",
                "domains": ["frontend"],
                "activities": ["ui_development"],
                "concepts": ["skill:react", "skill:typescript"],
                "evidence_type": "USAGE",
                "impact_quantified": False,
            },
            {
                "atom_id": "exp_0_bullet_1",
                "domains": ["frontend"],
                "activities": ["rendering_optimization"],
                "concepts": ["skill:react"],
                "evidence_type": "OWNERSHIP",
                "impact_quantified": True,
                "impact_kind": "performance",
            },
        ],
        "flags": [],
    }

    validated = validate_profiler_output(raw_output, atoms=atoms, ontology=ontology)

    assert len(validated.experiences) == 1
    exp = validated.experiences[0]
    assert exp.title_raw == "Software Engineer"
    assert len(exp.domain_allocations) == 1

    alloc = exp.domain_allocations[0]
    assert alloc.domain == "frontend"
    assert alloc.level == DomainAllocationLevel.PRIMARY
    assert alloc.code_atom_ratio == 1.0  # 3 support atoms / 3 exp atoms
    assert "INCONSISTENT_ALLOCATION" not in alloc.flags
    assert "INCONSISTENT_ALLOCATION" not in validated.flags


def test_inconsistent_allocation_flag_on_low_atom_ratio():
    """Verify that an experience allocated as PRIMARY with <0.3 code_atom_ratio

    receives the INCONSISTENT_ALLOCATION diagnostic flag.
    """
    # 5 atoms in exp_0
    atoms = [
        EvidenceAtom(
            atom_key=f"exp_0_bullet_{i}",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref="exp_0",
            page=1,
            char_start=i * 50,
            char_end=(i + 1) * 50,
            red_start=i * 50,
            red_end=(i + 1) * 50,
            text_redacted=f"Bullet {i}",
        )
        for i in range(5)
    ]

    # Output claims Backend is PRIMARY but only 1 out of 5 atoms supports it (ratio 0.2 < 0.3)
    raw_output = {
        "experiences": [
            {
                "entry_ref": "exp_0",
                "title_raw": "Software Engineer",
                "employment_type": "full-time",
                "date_text_start": "Jan 2020",
                "date_text_end": "Des 2021",
                "domain_allocations": [
                    {
                        "domain": "backend",
                        "level": "PRIMARY",
                        "support_atom_ids": ["exp_0_bullet_0"],  # only 1 atom
                    }
                ],
            }
        ],
        "atom_tags": [],
        "flags": [],
    }

    validated = validate_profiler_output(raw_output, atoms=atoms)

    alloc = validated.experiences[0].domain_allocations[0]
    assert alloc.code_atom_ratio == 0.2
    assert "INCONSISTENT_ALLOCATION" in alloc.flags
    assert "INCONSISTENT_ALLOCATION" in validated.flags


def test_referential_validation_flags_unknown_atoms_and_concepts():
    """Verify referential checks flag unknown atom keys and unknown ontology concepts."""
    atoms = _make_sample_atoms(entry_ref="exp_0")
    ontology = OntologyGraph(version="v1")
    ontology.add_concept(Concept("v1", "skill:react", "React", "framework", []))

    raw_output = {
        "experiences": [],
        "atom_tags": [
            {
                "atom_id": "non_existent_atom_key",
                "domains": ["frontend"],
                "activities": ["testing"],
                "concepts": ["skill:react", "skill:unknown_random_framework", "unmapped:custom_lib"],
                "evidence_type": "USAGE",
            }
        ],
        "flags": [],
    }

    validated = validate_profiler_output(raw_output, atoms=atoms, ontology=ontology)

    assert "INVALID_ATOM_REF:non_existent_atom_key" in validated.flags
    assert "UNKNOWN_CONCEPT:skill:unknown_random_framework" in validated.flags
    # 'unmapped:custom_lib' should not be flagged as unknown
    assert "UNKNOWN_CONCEPT:unmapped:custom_lib" not in validated.flags


class MockModelGateway:
    """Mock gateway returning realistic JSON profiling payload."""

    def __init__(self, response_json: dict[str, Any]):
        self.response_json = response_json

    async def call_chat(self, *args, **kwargs) -> dict[str, Any]:
        return self.response_json


@pytest.mark.asyncio
async def test_run_profiler_agent_with_mock_gateway():
    """Verify run_profiler_agent end-to-end with mock gateway returning JSON."""
    atoms = _make_sample_atoms(entry_ref="exp_0")
    mock_payload = {
        "experiences": [
            {
                "entry_ref": "exp_0",
                "title_raw": "Software Engineer",
                "employment_type": "full-time",
                "date_text_start": "Jan 2021",
                "date_text_end": "Des 2022",
                "is_current": False,
                "domain_allocations": [
                    {
                        "domain": "frontend",
                        "level": "PRIMARY",
                        "support_atom_ids": ["exp_0_bullet_0", "exp_0_bullet_1", "exp_0_bullet_2"],
                    }
                ],
            }
        ],
        "atom_tags": [
            {
                "atom_id": "exp_0_bullet_0",
                "domains": ["frontend"],
                "activities": ["ui_development"],
                "concepts": ["skill:react"],
                "evidence_type": "USAGE",
                "impact_quantified": False,
            }
        ],
        "flags": [],
    }

    mock_client = MockModelGateway(mock_payload)
    profile_id = uuid.uuid4()

    output = await run_profiler_agent(
        profile_id=profile_id,
        atoms=atoms,
        client=mock_client,
    )

    assert isinstance(output, ProfilerOutput)
    assert len(output.experiences) == 1
    assert output.experiences[0].domain_allocations[0].domain == "frontend"
    assert output.experiences[0].domain_allocations[0].code_atom_ratio == 1.0


@pytest.mark.asyncio
async def test_save_profiler_results_to_database():
    """Verify persistence of profiler output into experience_entries, atom_tags,

    and experience_domain_allocations tables.
    """
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    profile_id = uuid.uuid4()
    atom_id = uuid.uuid4()

    async with get_connection() as conn, conn.cursor() as cur:
        # 1. Create prerequisites: job, candidate, document, candidate_profile, evidence_atom
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'Dev', 'JD')",
            (job_id, tenant_id),
        )
        await cur.execute(
            "INSERT INTO candidates (id, tenant_id, candidate_code) VALUES (%s, %s, 'CAND-TEST-99')",
            (candidate_id, tenant_id),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, candidate_id, original_filename, sha256, storage_key, status)
            VALUES (%s, %s, %s, %s, 'cv.pdf', %s, 'cv.pdf', 'READY')
            """,
            (doc_id, tenant_id, job_id, candidate_id, uuid.uuid4().hex),
        )
        await cur.execute(
            """
            INSERT INTO candidate_profiles (id, tenant_id, document_id, profile, matching_profile, extractor_version)
            VALUES (%s, %s, %s, '{}'::jsonb, '{}'::jsonb, 'v2.1')
            """,
            (profile_id, tenant_id, doc_id),
        )
        await cur.execute(
            """
            INSERT INTO evidence_atoms (id, tenant_id, profile_id, atom_key, kind, visibility, entry_ref, text_redacted)
            VALUES (%s, %s, %s, 'exp_0_bullet_0', 'exp_bullet', 'VISIBLE', 'exp_0', 'React frontend development')
            """,
            (atom_id, tenant_id, profile_id),
        )

        # 2. Build ProfilerOutput
        output = ProfilerOutput(
            experiences=[
                ProfilerExperience(
                    entry_ref="exp_0",
                    title_raw="Software Engineer",
                    employment_type="full-time",
                    date_text_start="Jan 2021",
                    date_text_end="Des 2022",
                    is_current=False,
                    domain_allocations=[
                        DomainAllocation(
                            domain="frontend",
                            level=DomainAllocationLevel.PRIMARY,
                            support_atom_ids=["exp_0_bullet_0"],
                            code_atom_ratio=1.0,
                        )
                    ],
                )
            ],
            atom_tags=[
                AtomTag(
                    atom_id="exp_0_bullet_0",
                    domains=["frontend"],
                    activities=["ui_development"],
                    concepts=["skill:react"],
                    evidence_type=EvidenceType.USAGE,
                    impact_quantified=False,
                )
            ],
            flags=[],
        )

        # 3. Save profiler results
        res = await save_profiler_results(
            conn=conn,
            profile_id=profile_id,
            output=output,
            atoms=[{"atom_key": "exp_0_bullet_0", "id": atom_id, "entry_ref": "exp_0"}],
        )

        assert res["experiences"] == 1
        assert res["allocations"] == 1
        assert res["atom_tags"] == 1

        # 4. Verify DB rows
        await cur.execute(
            "SELECT * FROM experience_entries WHERE profile_id = %s",
            (profile_id,),
        )
        exp_row = await cur.fetchone()
        assert exp_row is not None
        assert exp_row["entry_ref"] == "exp_0"
        assert exp_row["title_raw"] == "Software Engineer"
        assert exp_row["start_lo"] is not None
        assert exp_row["end_hi"] is not None

        await cur.execute(
            "SELECT * FROM experience_domain_allocations WHERE experience_id = %s",
            (exp_row["id"],),
        )
        alloc_row = await cur.fetchone()
        assert alloc_row is not None
        assert alloc_row["domain"] == "frontend"
        assert alloc_row["level"] == "PRIMARY"
        assert alloc_row["code_atom_ratio"] == 1.0
        assert atom_id in alloc_row["support_atom_ids"]

        await cur.execute(
            "SELECT * FROM atom_tags WHERE atom_id = %s",
            (atom_id,),
        )
        tag_row = await cur.fetchone()
        assert tag_row is not None
        assert "frontend" in tag_row["domains"]
        assert "skill:react" in tag_row["concepts"]
        assert tag_row["evidence_type"] == "USAGE"
