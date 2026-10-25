"""Unit tests for Matcher Agent (Directional Entailment), S3 Retriever, S4 Ontology Shortcut, and S7 Aggregator (v2.1).

Tests:
1. Schema strictness, R1 field ordering (`analysis` before `verdict`), and enum validation.
2. Software Engineer -> Frontend Developer directional matching producing STRONG.
3. Depth levels L0..L4 behavior and validation.
4. S4 Ontology shortcut: T2+ atoms satisfying facets via IMPLIES chain without LLM.
5. S7 Aggregator: Role equivalence rules (STRONG, PARTIAL, NOT_DEMONSTRATED) & temporal integration.
6. S3 Evidence Retriever: Visibility gate enforcement & ontology concept expansion.
7. Context expansion loop (`needs_more_context=True`) on neighbor atoms.
8. Database persistence to `facet_judgments` table.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from src.agents import (
    DepthLevel,
    FacetEvaluationInput,
    FacetEvaluationResult,
    FacetVerdict,
    MatcherBatchOutput,
    run_matcher_agent,
    save_matcher_results,
)
from src.domain.atoms import AtomKind, EvidenceAtom
from src.domain.matching import (
    AggregatedRequirementResult,
    RequirementState,
    aggregate_requirement_facets,
    check_facet_ontology_shortcut,
    determine_atom_tier,
    expand_facet_terms,
    partition_facets_by_ontology_shortcut,
    rank_atoms_in_memory,
    retrieve_facet_evidence,
)
from src.domain.ontology import Concept, ConceptEdge, OntologyGraph, RelationType
from src.domain.requirements.facet_templates import ROLE_FACET_TEMPLATES
from src.domain.requirements.schemas import DurationPolicySchema, RequirementFacet, RequirementIR
from src.infrastructure.database import get_connection


def _create_mock_atoms(entry_ref: str = "exp_0") -> list[EvidenceAtom]:
    """Creates a realistic set of atoms for a candidate titled 'Software Engineer'."""
    return [
        EvidenceAtom(
            atom_key=f"{entry_ref}_bullet_0",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref=entry_ref,
            page=1,
            char_start=100,
            char_end=220,
            red_start=100,
            red_end=220,
            text_redacted="Membangun antarmuka dashboard admin interaktif menggunakan framework React SPA, TypeScript, dan Next.js.",
            visibility="VISIBLE",
        ),
        EvidenceAtom(
            atom_key=f"{entry_ref}_bullet_1",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref=entry_ref,
            page=1,
            char_start=221,
            char_end=340,
            red_start=221,
            red_end=340,
            text_redacted="Mengimplementasikan manajemen state client-side menggunakan Redux Toolkit dan Zustand untuk caching data lokal.",
            visibility="VISIBLE",
        ),
        EvidenceAtom(
            atom_key=f"{entry_ref}_bullet_2",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref=entry_ref,
            page=1,
            char_start=341,
            char_end=460,
            red_start=341,
            red_end=460,
            text_redacted="Melakukan slicing UI responsif dari desain Figma dengan Tailwind CSS dan menjamin cross-browser compatibility.",
            visibility="VISIBLE",
        ),
        EvidenceAtom(
            atom_key=f"{entry_ref}_bullet_3",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref=entry_ref,
            page=1,
            char_start=461,
            char_end=580,
            red_start=461,
            red_end=580,
            text_redacted="Mengintegrasikan REST API dan GraphQL endpoint pada sisi frontend dengan Axios dan React Query.",
            visibility="VISIBLE",
        ),
        EvidenceAtom(
            atom_key=f"{entry_ref}_bullet_4",
            kind=AtomKind.EXP_BULLET.value,
            entry_ref=entry_ref,
            page=1,
            char_start=581,
            char_end=700,
            red_start=581,
            red_end=700,
            text_redacted="Menulis unit testing dan component testing frontend menggunakan Jest dan React Testing Library.",
            visibility="VISIBLE",
        ),
    ]


class MockMatcherGateway:
    """Mock gateway returning realistic JSON for Matcher Agent."""

    def __init__(self, evaluations: list[dict[str, Any]] | None = None):
        self.evaluations = evaluations or []
        self.call_count = 0
        self.last_messages: list[dict[str, Any]] = []

    async def call_chat(
        self,
        messages: list[dict[str, Any]],
        task: str = "matcher",
        tenant_id: uuid.UUID | None = None,
        json_mode: bool = True,
        model: str = "ag/gemini-3.8-flash-high",
    ) -> dict[str, Any]:
        self.call_count += 1
        self.last_messages = messages

        if self.evaluations:
            payload = {"evaluations": self.evaluations, "flags": []}
        else:
            payload = {"evaluations": [], "flags": []}

        return {"raw_content": json.dumps(payload)}


def test_matcher_schema_strictness_and_r1_ordering():
    """Verify R1 rule: `analysis` is defined and serialized BEFORE `verdict`."""
    fields = list(FacetEvaluationResult.model_fields.keys())
    assert "analysis" in fields
    assert "verdict" in fields
    analysis_idx = fields.index("analysis")
    verdict_idx = fields.index("verdict")
    assert analysis_idx < verdict_idx, "R1 violation: analysis MUST precede verdict"

    # Test FacetEvaluationInput schema
    f_input = FacetEvaluationInput(
        facet_key="F1",
        hypothesis="Mampu membangun UI SPA dengan React",
        depth_floor="L2",
    )
    assert f_input.depth_floor == "L2"
    assert f_input.hypothesis == "Mampu membangun UI SPA dengan React"

    # Strict enum checks
    res = FacetEvaluationResult(
        facet_key="F1",
        analysis="Literal evidence shows React SPA usage.",
        verdict=FacetVerdict.ENTAILED,
        support_atoms=["exp_0_b0"],
        depth_level=DepthLevel.L2,
    )
    assert res.verdict == FacetVerdict.ENTAILED
    assert res.depth_level == DepthLevel.L2

    # Extra field forbidden
    with pytest.raises(ValidationError):
        FacetEvaluationResult(
            facet_key="F1",
            analysis="test",
            verdict=FacetVerdict.ENTAILED,
            extra_field="disallowed",  # type: ignore[call-arg]
        )

    # Alias support_atom_ids normalized
    dict_data = {
        "facet_key": "F2",
        "analysis": "State management via Redux",
        "verdict": "entailed",
        "support_atom_ids": ["atom_1", "atom_2"],
        "depth_level": "l2",
    }
    parsed = FacetEvaluationResult.model_validate(dict_data)
    assert parsed.support_atoms == ["atom_1", "atom_2"]
    assert parsed.verdict == FacetVerdict.ENTAILED
    assert parsed.depth_level == DepthLevel.L2


@pytest.mark.asyncio
async def test_software_engineer_to_frontend_strong():
    """Verify Problem 1 (Title vs Context): Candidate titled 'Software Engineer' with React

    and UI evidence atoms matches Frontend Developer role and is aggregated as STRONG.
    """
    atoms = _create_mock_atoms("exp_0")
    raw_title = "Software Engineer"

    # Frontend facets F1..F5 from builtin templates
    frontend_facets = [RequirementFacet.model_validate(f) for f in ROLE_FACET_TEMPLATES["frontend"]]
    assert len(frontend_facets) == 5

    # Mock Matcher LLM evaluating the 5 facets
    mock_evals = [
        {
            "facet_key": "F1",
            "analysis": "Atom exp_0_bullet_0 secara harfiah membuktikan pembangunan dashboard React SPA.",
            "verdict": "ENTAILED",
            "support_atoms": ["exp_0_bullet_0"],
            "depth_level": "L2",
            "rationale_code": "DIRECT_EVIDENCE",
            "needs_more_context": False,
        },
        {
            "facet_key": "F2",
            "analysis": "Atom exp_0_bullet_1 membuktikan pengelolaan state client-side dengan Redux Toolkit & Zustand.",
            "verdict": "ENTAILED",
            "support_atoms": ["exp_0_bullet_1"],
            "depth_level": "L2",
            "rationale_code": "DIRECT_EVIDENCE",
            "needs_more_context": False,
        },
        {
            "facet_key": "F3",
            "analysis": "Atom exp_0_bullet_2 membuktikan slicing UI responsif dari Figma dengan Tailwind CSS.",
            "verdict": "ENTAILED",
            "support_atoms": ["exp_0_bullet_2"],
            "depth_level": "L2",
            "rationale_code": "DIRECT_EVIDENCE",
            "needs_more_context": False,
        },
        {
            "facet_key": "F4",
            "analysis": "Atom exp_0_bullet_3 membuktikan integrasi REST dan GraphQL endpoint dengan Axios.",
            "verdict": "ENTAILED",
            "support_atoms": ["exp_0_bullet_3"],
            "depth_level": "L2",
            "rationale_code": "DIRECT_EVIDENCE",
            "needs_more_context": False,
        },
        {
            "facet_key": "F5",
            "analysis": "Atom exp_0_bullet_4 membuktikan pengujian komponen frontend menggunakan Jest.",
            "verdict": "ENTAILED",
            "support_atoms": ["exp_0_bullet_4"],
            "depth_level": "L2",
            "rationale_code": "DIRECT_EVIDENCE",
            "needs_more_context": False,
        },
    ]

    gateway = MockMatcherGateway(evaluations=mock_evals)
    matcher_out = await run_matcher_agent(
        facets=frontend_facets,
        candidate_atoms=atoms,
        client=gateway,
        raw_title=raw_title,
    )

    assert len(matcher_out.evaluations) == 5
    # Verify title prompt injection safety (title is context_only)
    assert "Context Only (Weak Prior)" in gateway.last_messages[1]["content"]
    assert "Software Engineer" in gateway.last_messages[1]["content"]

    # Construct RequirementIR
    req_ir = RequirementIR(
        requirement_id="REQ-FE-ROLE",
        description="Frontend Developer dengan kemampuan React, state management, dan responsive UI",
        category="EXPERIENCE",
        kind="ROLE_EQUIVALENCE",
        importance="MUST_HAVE",
        weight=20.0,
        target_domains=["frontend"],
        facets=frontend_facets,
    )

    # Aggregate judgments
    agg_result = aggregate_requirement_facets(
        requirement=req_ir,
        judgments=matcher_out.evaluations,
        candidate_atoms=atoms,
    )

    # Core rule: STRONG because ALL core facets (F1, F2, F3) are ENTAILED with depth >= L2 from tier >= T2 atoms
    assert isinstance(agg_result, AggregatedRequirementResult)
    assert agg_result.state == RequirementState.STRONG
    assert agg_result.role_equivalence_met is True
    assert agg_result.core_facets_total == 3
    assert agg_result.core_entailed_count == 3
    assert agg_result.core_l2_plus_count == 3
    assert not agg_result.escalation_triggers


def test_depth_levels_l0_to_l4():
    """Verify depth levels L0..L4 behavior and that L1 depth fails STRONG requirement."""
    facets = [
        RequirementFacet(facet_key="F1", hypothesis="membangun komponen UI SPA", core=True),
        RequirementFacet(facet_key="F2", hypothesis="mengelola state client-side", core=True),
    ]
    req_ir = RequirementIR(
        requirement_id="REQ-01",
        description="Frontend Engineer",
        kind="ROLE_EQUIVALENCE",
        facets=facets,
    )

    # Case 1: L1 depth (junior / guided) -> Even if ENTAILED, core depth < L2 fails STRONG -> PARTIAL
    junior_judgments = [
        FacetEvaluationResult(
            facet_key="F1",
            analysis="Junior assisted with bugfixes in React",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L1,
            support_atoms=["exp_0_b0"],
        ),
        FacetEvaluationResult(
            facet_key="F2",
            analysis="Assisted with reading state from Redux store",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L1,
            support_atoms=["exp_0_b1"],
        ),
    ]
    res_junior = aggregate_requirement_facets(requirement=req_ir, judgments=junior_judgments)
    assert res_junior.state == RequirementState.PARTIAL
    assert res_junior.role_equivalence_met is False

    # Case 2: L2 & L3 depth -> Meets STRONG
    senior_judgments = [
        FacetEvaluationResult(
            facet_key="F1",
            analysis="Independently developed React SPA components",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L2,
            support_atoms=["exp_0_b0"],
        ),
        FacetEvaluationResult(
            facet_key="F2",
            analysis="Architected complex normalized client state and caching with Zustand",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L3,
            support_atoms=["exp_0_b1"],
        ),
    ]
    res_senior = aggregate_requirement_facets(requirement=req_ir, judgments=senior_judgments)
    assert res_senior.state == RequirementState.STRONG
    assert res_senior.role_equivalence_met is True


def test_ontology_shortcut():
    """Verify S4 Ontology Shortcut:

    1. Atom with T2+ tier (exp_bullet) implying a facet concept directly satisfies the facet via ontology.
    2. Atom with T0 tier (mention_only or skill_list) is REJECTED by ontology shortcut.
    """
    ontology = OntologyGraph(version="v1")
    ontology.add_concept(Concept("v1", "skill:react", "React", "framework", ["reactjs"]))
    ontology.add_concept(Concept("v1", "skill:javascript", "JavaScript", "language", ["js", "es6"]))
    # Add IMPLIES edge: react -> javascript
    ontology.add_edge(ConceptEdge("v1", "skill:react", "skill:javascript", RelationType.IMPLIES.value, 1.0))

    facet_js = RequirementFacet(
        facet_key="F_JS",
        hypothesis="Menguasai bahasa pemrograman JavaScript modern (ES6+)",
        core=True,
        concepts=["skill:javascript"],
    )

    # 1. T2 atom mentioning React -> satisfies JavaScript facet via IMPLIES chain
    t2_atom = EvidenceAtom(
        atom_key="exp_0_bullet_0",
        kind=AtomKind.EXP_BULLET.value,
        entry_ref="exp_0",
        page=1,
        char_start=0,
        char_end=100,
        red_start=0,
        red_end=100,
        text_redacted="Mengembangkan aplikasi web menggunakan ReactJS dan TypeScript.",
        visibility="VISIBLE",
    )
    assert determine_atom_tier(t2_atom) == "T2"

    shortcut_res = check_facet_ontology_shortcut(
        facet=facet_js,
        candidate_atoms=[t2_atom],
        ontology=ontology,
    )
    assert shortcut_res is not None
    assert shortcut_res.facet_key == "F_JS"
    assert shortcut_res.verdict == FacetVerdict.ENTAILED
    assert shortcut_res.depth_level == DepthLevel.L2
    assert "IMPLIES" in shortcut_res.rationale_code

    # 2. T0 atom (skill list) -> cannot satisfy via shortcut
    t0_atom = EvidenceAtom(
        atom_key="skill_0",
        kind=AtomKind.SKILL_LIST_ITEM.value,
        entry_ref=None,
        page=1,
        char_start=0,
        char_end=20,
        red_start=0,
        red_end=20,
        text_redacted="React, JavaScript",
        visibility="VISIBLE",
    )
    assert determine_atom_tier(t0_atom) == "T0"

    shortcut_fail = check_facet_ontology_shortcut(
        facet=facet_js,
        candidate_atoms=[t0_atom],
        ontology=ontology,
    )
    assert shortcut_fail is None

    # 3. Partition helper
    facet_other = RequirementFacet(
        facet_key="F_DOCKER",
        hypothesis="Menguasai containerization dengan Docker",
        core=False,
        concepts=["skill:docker"],
    )
    satisfied, remaining = partition_facets_by_ontology_shortcut(
        facets=[facet_js, facet_other],
        candidate_atoms=[t2_atom],
        ontology=ontology,
    )
    assert "F_JS" in satisfied
    assert len(remaining) == 1
    assert remaining[0].facet_key == "F_DOCKER"


def test_aggregator_role_equivalence_rules_and_temporal():
    """Verify S7 Aggregator combination logic:

    - STRONG rule: all core ENTAILED and >= 2 core depth >= L2.
    - PARTIAL rule: >= 2 core ENTAILED, or all core >= PARTIAL.
    - NOT_DEMONSTRATED otherwise.
    - Temporal engine integration (sweep-line calendar union).
    - Escalation triggers (E4, E5).
    """
    facets = [
        RequirementFacet(facet_key="F1", hypothesis="H1", core=True),
        RequirementFacet(facet_key="F2", hypothesis="H2", core=True),
        RequirementFacet(facet_key="F3", hypothesis="H3", core=True),
        RequirementFacet(facet_key="F4", hypothesis="H4", core=False),
    ]
    req_ir = RequirementIR(
        requirement_id="REQ-02",
        description="Backend Role",
        kind="ROLE_EQUIVALENCE",
        facets=facets,
        duration_policy=DurationPolicySchema(min_months=24.0, target_domain="backend"),
    )

    # Case A: 2 of 3 core ENTAILED, 1 NOT_ENTAILED -> PARTIAL
    judgments_partial = [
        FacetEvaluationResult(
            facet_key="F1",
            analysis="F1 entailed",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L2,
            support_atoms=["a1"],
        ),
        FacetEvaluationResult(
            facet_key="F2",
            analysis="F2 entailed",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L2,
            support_atoms=["a2"],
        ),
        FacetEvaluationResult(
            facet_key="F3",
            analysis="F3 not demonstrated",
            verdict=FacetVerdict.NOT_ENTAILED,
            depth_level=DepthLevel.L0,
            support_atoms=[],
        ),
    ]
    atom_tiers = {"a1": "T2", "a2": "T2"}
    res_a = aggregate_requirement_facets(
        requirement=req_ir,
        judgments=judgments_partial,
        atom_tiers=atom_tiers,
    )
    assert res_a.state == RequirementState.PARTIAL

    # Case B: 0 or 1 core ENTAILED, not all partial -> NOT_DEMONSTRATED
    judgments_fail = [
        FacetEvaluationResult(
            facet_key="F1",
            analysis="F1 entailed",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L2,
            support_atoms=["a1"],
        ),
        FacetEvaluationResult(
            facet_key="F2",
            analysis="F2 not entailed",
            verdict=FacetVerdict.NOT_ENTAILED,
            depth_level=DepthLevel.L0,
            support_atoms=[],
        ),
        FacetEvaluationResult(
            facet_key="F3",
            analysis="F3 contradicted",
            verdict=FacetVerdict.CONTRADICTED,
            depth_level=DepthLevel.L0,
            support_atoms=[],
        ),
    ]
    res_b = aggregate_requirement_facets(
        requirement=req_ir,
        judgments=judgments_fail,
        atom_tiers=atom_tiers,
    )
    assert res_b.state == RequirementState.NOT_DEMONSTRATED

    # Case C: All core ENTAILED at L2, but temporal tenure is uncertain (lo < min <= hi) -> E5 escalation
    judgments_strong = [
        FacetEvaluationResult(
            facet_key="F1",
            analysis="F1 entailed",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L2,
            support_atoms=["a1"],
        ),
        FacetEvaluationResult(
            facet_key="F2",
            analysis="F2 entailed",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L2,
            support_atoms=["a2"],
        ),
        FacetEvaluationResult(
            facet_key="F3",
            analysis="F3 entailed",
            verdict=FacetVerdict.ENTAILED,
            depth_level=DepthLevel.L2,
            support_atoms=["a3"],
        ),
    ]
    atom_tiers["a3"] = "T2"

    domain_duration_uncertain = {
        "min_months": 24.0,
        "months_lo": 18.0,
        "months_hi": 30.0,
    }
    res_c = aggregate_requirement_facets(
        requirement=req_ir,
        judgments=judgments_strong,
        atom_tiers=atom_tiers,
        domain_duration=domain_duration_uncertain,
    )
    assert res_c.state == RequirementState.PARTIAL
    assert "DATE_UNCERTAIN" in res_c.flags
    assert "E5" in res_c.escalation_triggers

    # Case D: Temporal satisfied (months_lo >= min_months) -> Final state STRONG
    domain_duration_strong = {
        "min_months": 24.0,
        "months_lo": 26.0,
        "months_hi": 30.0,
    }
    res_d = aggregate_requirement_facets(
        requirement=req_ir,
        judgments=judgments_strong,
        atom_tiers=atom_tiers,
        domain_duration=domain_duration_strong,
    )
    assert res_d.state == RequirementState.STRONG
    assert not res_d.escalation_triggers


@pytest.mark.asyncio
async def test_retriever_visibility_gate_and_concept_expansion():
    """Verify S3 Evidence Retriever:

    - Excludes HIDDEN text atoms (Grounding / Security rule).
    - Expands concepts and aliases via ontology.
    """
    ontology = OntologyGraph(version="v1")
    ontology.add_concept(Concept("v1", "skill:react", "React", "framework", ["reactjs", "react.js"]))

    facet = RequirementFacet(
        facet_key="F1",
        hypothesis="Membangun antarmuka dengan framework modern",
        concepts=["skill:react"],
    )

    query_text, terms = expand_facet_terms(facet=facet, ontology=ontology)
    assert "react" in terms
    assert "reactjs" in terms

    # Test atom visibility filtering
    atoms = [
        EvidenceAtom(
            atom_key="atom_visible",
            kind="exp_bullet",
            entry_ref="exp_0",
            page=1,
            char_start=0,
            char_end=50,
            red_start=0,
            red_end=50,
            text_redacted="Mengembangkan modul frontend dengan React dan TypeScript.",
            visibility="VISIBLE",
        ),
        EvidenceAtom(
            atom_key="atom_hidden",
            kind="exp_bullet",
            entry_ref="exp_0",
            page=1,
            char_start=51,
            char_end=100,
            red_start=51,
            red_end=100,
            text_redacted="React React React hidden micro font white text.",
            visibility="HIDDEN",
        ),
    ]

    retrieved = rank_atoms_in_memory(
        atoms=atoms,
        query_text=query_text,
        expanded_terms=terms,
        k=6,
    )
    assert len(retrieved) == 1
    assert retrieved[0].atom_key == "atom_visible"
    assert retrieved[0].visibility == "VISIBLE"

    # Also verify retrieve_facet_evidence with candidate_atoms
    async_retrieved = await retrieve_facet_evidence(
        facet=facet,
        candidate_atoms=atoms,
        ontology=ontology,
        k=6,
    )
    assert len(async_retrieved) == 1
    assert async_retrieved[0].atom_key == "atom_visible"


@pytest.mark.asyncio
async def test_matcher_needs_more_context_loop():
    """Verify Matcher Agent handles `needs_more_context=True` by re-calling

    with neighboring atoms from the same entry (max 1 loop).
    """
    initial_atoms = [
        EvidenceAtom(
            atom_key="exp_0_b0",
            kind="exp_bullet",
            entry_ref="exp_0",
            page=1,
            char_start=0,
            char_end=50,
            red_start=0,
            red_end=50,
            text_redacted="Mengoptimalkan performa halaman.",
            visibility="VISIBLE",
        ),
    ]

    neighbor_atom = EvidenceAtom(
        atom_key="exp_0_b1",
        kind="exp_bullet",
        entry_ref="exp_0",
        page=1,
        char_start=51,
        char_end=120,
        red_start=51,
        red_end=120,
        text_redacted="Implementasi code splitting dan lazy loading di React SPA.",
        visibility="VISIBLE",
    )
    all_atoms = initial_atoms + [neighbor_atom]

    facet = RequirementFacet(
        facet_key="F5",
        hypothesis="testing/performa frontend",
        core=False,
    )

    class DynamicMockGateway:
        def __init__(self):
            self.call_count = 0

        async def call_chat(self, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
            self.call_count += 1
            if self.call_count == 1:
                # First call: requires more context
                payload = {
                    "evaluations": [
                        {
                            "facet_key": "F5",
                            "analysis": "Performa disebutkan tetapi rincian teknologi belum jelas.",
                            "verdict": "PARTIAL",
                            "support_atoms": ["exp_0_b0"],
                            "depth_level": "L1",
                            "needs_more_context": True,
                        }
                    ],
                    "flags": [],
                }
            else:
                # Second call with neighbor atom: resolved as ENTAILED
                payload = {
                    "evaluations": [
                        {
                            "facet_key": "F5",
                            "analysis": "Tetangga exp_0_b1 membuktikan code splitting di React.",
                            "verdict": "ENTAILED",
                            "support_atoms": ["exp_0_b0", "exp_0_b1"],
                            "depth_level": "L2",
                            "needs_more_context": False,
                        }
                    ],
                    "flags": [],
                }
            return {"raw_content": json.dumps(payload)}

    dyn_gateway = DynamicMockGateway()
    batch_out = await run_matcher_agent(
        facets=[facet],
        candidate_atoms=initial_atoms,
        client=dyn_gateway,
        all_candidate_atoms=all_atoms,
    )

    # Verified 2 calls (initial + 1 context expansion loop)
    assert dyn_gateway.call_count == 2
    assert "NEEDS_MORE_CONTEXT_TRIGGERED" in batch_out.flags
    ev = batch_out.get_evaluation("F5")
    assert ev is not None
    assert ev.verdict == FacetVerdict.ENTAILED
    assert "exp_0_b1" in ev.support_atoms


@pytest.mark.asyncio
async def test_matcher_database_persistence():
    """Verify persisting Matcher evaluations to the `facet_judgments` table in PostgreSQL."""
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    set_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    run_id = uuid.uuid4()

    output = MatcherBatchOutput(
        evaluations=[
            FacetEvaluationResult(
                facet_key="F1",
                analysis="Kandidat membangun 12 komponen React UI dengan kualitas kode tinggi.",
                verdict=FacetVerdict.ENTAILED,
                depth_level=DepthLevel.L2,
                support_atoms=["exp_0_b0"],
                rationale_code="DIRECT_EVIDENCE",
            ),
        ],
        flags=[],
    )

    async with get_connection() as conn, conn.cursor() as cur:
        # Insert prerequisite records
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'FE Lead', 'JD')",
            (job_id, tenant_id),
        )
        await cur.execute(
            "INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights) VALUES (%s, %s, %s, 1, 'DRAFT', '{}')",
            (set_id, tenant_id, job_id),
        )
        await cur.execute(
            "INSERT INTO candidates (id, tenant_id, candidate_code) VALUES (%s, %s, 'CAND-MATCHER-TEST')",
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

        # Save results
        atom_uuid = uuid.uuid4()
        saved = await save_matcher_results(
            conn=conn,
            run_id=run_id,
            candidate_id=cand_id,
            requirement_id="REQ-FE-01",
            output=output,
            tenant_id=tenant_id,
            atom_key_to_uuid={"exp_0_b0": atom_uuid},
        )
        assert saved == 1

        # Query back
        await cur.execute(
            """
            SELECT verdict, depth_level, method, analysis, rationale_code, support_atom_ids
            FROM facet_judgments
            WHERE run_id = %s AND candidate_id = %s AND requirement_id = %s AND facet_key = %s
            """,
            (run_id, cand_id, "REQ-FE-01", "F1"),
        )
        row = await cur.fetchone()
        assert row is not None
        assert row["verdict"] == "ENTAILED"
        assert row["depth_level"] == "L2"
        assert row["method"] == "matcher"
        assert "React UI" in row["analysis"]
        assert row["rationale_code"] == "DIRECT_EVIDENCE"
        assert row["support_atom_ids"] == [atom_uuid]
