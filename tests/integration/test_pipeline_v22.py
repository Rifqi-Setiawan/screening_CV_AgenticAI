"""Graph B v2.2: facet reuse, facet narrowing, Critic routing and Critic propagation."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import pytest

from src.agents.critic import decide_critic_routing
from src.domain.atoms import AtomKind, EvidenceAtom
from src.domain.matching.aggregator import RequirementState
from src.domain.ontology import OntologyGraph
from src.domain.pipeline import CandidateInput, run_screening_pipeline
from src.domain.requirements.facet_narrowing import apply_facet_narrowing, facet_signature, narrow_facets
from src.domain.requirements.facet_templates import ROLE_FACET_TEMPLATES
from src.domain.requirements.schemas import (
    DurationPolicySchema,
    RequirementFacet,
    RequirementIR,
    RequirementSetIR,
)
from src.infrastructure.config import settings
from src.infrastructure.gateway import llm_semaphore


class CountingGateway:
    """Mock gateway: fixed matcher / critic payloads and call counters."""

    def __init__(self, matcher_verdicts: dict[str, str], critic_payload: dict[str, Any] | None = None):
        self.matcher_verdicts = matcher_verdicts
        self.critic_payload = critic_payload or {"facet_reviews": [], "has_disagreement": False}
        self.calls: dict[str, int] = {}
        self.matcher_facets: list[list[str]] = []

    def verify_redacted_text(self, text: str) -> None:
        pass

    async def call_chat(self, messages, task="matcher", tenant_id=None, json_mode=True, model=None):
        self.calls[task] = self.calls.get(task, 0) + 1
        if task == "critic":
            return {"raw_content": json.dumps(self.critic_payload)}
        asked = [
            k
            for k in self.matcher_verdicts
            if f'"{k}"' in messages[-1]["content"]
            or f"[{k}]" in messages[-1]["content"]
            or k in messages[-1]["content"]
        ]
        self.matcher_facets.append(asked)
        evals = [
            {
                "facet_key": k,
                "analysis": "bukti literal pada atom A1",
                "verdict": v,
                "support_atoms": ["A1"] if v == "ENTAILED" else [],
                "depth_level": "L2" if v == "ENTAILED" else "L0",
                "rationale_code": "DIRECT_EVIDENCE" if v == "ENTAILED" else "NO_EVIDENCE",
            }
            for k, v in self.matcher_verdicts.items()
        ]
        return {"raw_content": json.dumps({"evaluations": evals, "flags": []})}


def _atom() -> EvidenceAtom:
    text = "Membangun dan memelihara layanan backend produksi."
    return EvidenceAtom(
        atom_key="A1",
        kind=AtomKind.EXP_BULLET.value,
        entry_ref="exp_1",
        page=1,
        char_start=0,
        char_end=len(text),
        red_start=0,
        red_end=len(text),
        text_redacted=text,
    )


def _facets() -> list[RequirementFacet]:
    return [
        RequirementFacet(facet_key="X1", hypothesis="hipotesis pertama", core=True, concepts=["skill:x1"]),
        RequirementFacet(facet_key="X2", hypothesis="hipotesis kedua", core=True, concepts=["skill:x2"]),
        RequirementFacet(facet_key="X3", hypothesis="hipotesis ketiga", core=True, concepts=["skill:x3"]),
    ]


def _shared_facet_req_set(n_requirements: int = 3) -> RequirementSetIR:
    reqs = [
        RequirementIR(
            requirement_id=f"R{i}",
            description=f"Kriteria nomor {i}",
            category="EXPERIENCE",
            kind="ROLE_EQUIVALENCE",
            importance="MUST_HAVE",
            weight=10.0,
            facets=_facets(),
        )
        for i in range(1, n_requirements + 1)
    ]
    return RequirementSetIR(job_title="Uji", requirements=reqs, category_weights={})


def _candidate(i: int = 0) -> CandidateInput:
    return CandidateInput(candidate_id=uuid.uuid4(), profile_id=uuid.uuid4(), atoms=[_atom()], raw_title=f"Eng {i}")


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    monkeypatch.setattr(settings, "FACET_NARROWING_ENABLED", False)
    monkeypatch.setattr(settings, "CRITIC_RANDOM_AUDIT_RATE", 0.0)
    monkeypatch.setattr(settings, "CRITIC_TOP_K", 0)


@pytest.mark.asyncio
async def test_shared_facets_are_judged_once_for_all_requirements():
    gw = CountingGateway({"X1": "ENTAILED", "X2": "ENTAILED", "X3": "ENTAILED"})
    res = await run_screening_pipeline(
        candidates=[_candidate()],
        requirement_set=_shared_facet_req_set(6),
        tenant_id=uuid.uuid4(),
        client=gw,
        ontology=OntologyGraph(version="t"),
    )
    assert gw.calls.get("matcher", 0) == 1  # v2.1 made one call per requirement (6)
    cand = res.top_candidate
    assert cand is not None
    assert {r.state for r in cand.requirement_results.values()} == {RequirementState.STRONG}
    assert len(cand.facet_judgments) == 3  # one judgment per distinct facet, not 6 x 3


@pytest.mark.asyncio
async def test_candidates_run_concurrently_but_ranking_stays_deterministic():
    gw = CountingGateway({"X1": "ENTAILED", "X2": "ENTAILED", "X3": "ENTAILED"})
    cands = [_candidate(i) for i in range(6)]
    kwargs = dict(
        requirement_set=_shared_facet_req_set(2),
        run_id=uuid.UUID(int=7),
        tenant_id=uuid.uuid4(),
        client=gw,
        ontology=OntologyGraph(version="t"),
    )
    r1 = await run_screening_pipeline(candidates=cands, **kwargs)
    r2 = await run_screening_pipeline(candidates=list(reversed(cands)), **kwargs)
    assert [c.candidate_id for c in r1.candidates] == [c.candidate_id for c in r2.candidates]
    assert gw.calls["matcher"] == 12  # 6 candidates x 1 call x 2 runs


@pytest.mark.asyncio
async def test_critic_is_routed_not_blanket(monkeypatch):
    # Every candidate fails its MUST_HAVEs (E1 only): without top-K / random audit nobody is audited.
    gw = CountingGateway({"X1": "NOT_ENTAILED", "X2": "NOT_ENTAILED", "X3": "NOT_ENTAILED"})
    cands = [_candidate(i) for i in range(5)]
    common = dict(
        requirement_set=_shared_facet_req_set(2),
        run_id=uuid.UUID(int=11),
        tenant_id=uuid.uuid4(),
        client=gw,
        critic_client=gw,
        ontology=OntologyGraph(version="t"),
    )
    await run_screening_pipeline(candidates=cands, **common)
    assert gw.calls.get("critic", 0) == 0

    monkeypatch.setattr(settings, "CRITIC_TOP_K", 2)
    gw.calls.clear()
    res = await run_screening_pipeline(candidates=cands, **common)
    assert gw.calls.get("critic", 0) == 2
    audited = [c for c in res.candidates if "TOP_K" in c.escalation_triggers]
    assert len(audited) == 2

    monkeypatch.setattr(settings, "CRITIC_TOP_K", 0)
    monkeypatch.setattr(settings, "CRITIC_RANDOM_AUDIT_RATE", 1.0)
    gw.calls.clear()
    await run_screening_pipeline(candidates=cands, **common)
    assert gw.calls.get("critic", 0) == 5


@pytest.mark.asyncio
async def test_critic_downgrade_on_shared_facet_reaches_every_requirement(monkeypatch):
    monkeypatch.setattr(settings, "CRITIC_TOP_K", 1)
    critic = {
        "candidate_id": "x",
        "overall_reasoning": "x1 hanya klaim",
        "escalation_triggers": ["TOP_K"],
        "facet_reviews": [
            {
                "facet_key": "X1",
                "analysis": "Tidak ada bukti pelaksanaan.",
                "verdict_action": "DOWNGRADE",
                "final_verdict": "NOT_ENTAILED",
                "reasoning": "klaim kosong",
                "depth_level": "L0",
                "support_atoms": [],
                "flags": [],
            }
        ],
        "has_disagreement": True,
        "disagreement_flags": ["AGENT_DISAGREEMENT"],
        "final_recommendation": "REVIEW",
    }
    gw = CountingGateway({"X1": "ENTAILED", "X2": "ENTAILED", "X3": "ENTAILED"}, critic_payload=critic)
    res = await run_screening_pipeline(
        candidates=[_candidate()],
        requirement_set=_shared_facet_req_set(3),
        tenant_id=uuid.uuid4(),
        client=gw,
        critic_client=gw,
        ontology=OntologyGraph(version="t"),
    )
    cand = res.top_candidate
    assert cand is not None
    states = {rid: r.state for rid, r in cand.requirement_results.items()}
    # v2.1 re-aggregated only the last requirement that used the facet; all three must now change.
    assert all(s != RequirementState.STRONG for s in states.values()), states


# --------------------------------------------------------------------- narrowing / routing units
def _backend_req(description: str, **kw: Any) -> RequirementIR:
    return RequirementIR(
        requirement_id="R",
        description=description,
        kind="ROLE_EQUIVALENCE",
        facets=[RequirementFacet(**t) for t in ROLE_FACET_TEMPLATES["backend"]],
        **kw,
    )


def test_narrowing_keeps_whole_template_for_general_role_statements():
    req = _backend_req(
        "Pengalaman kerja minimal 2 tahun sebagai Backend Developer",
        duration_policy=DurationPolicySchema(min_months=24.0),
    )
    assert len(narrow_facets(req)) == 5


def test_narrowing_selects_database_facet_for_database_requirement():
    req = _backend_req("Mahir dalam pengelolaan basis data relasional PostgreSQL atau MySQL dan optimasi kueri SQL")
    keys = [f.facet_key for f in narrow_facets(req)]
    assert keys == ["B2"]
    assert all(f.core for f in narrow_facets(req))


def test_narrowing_falls_back_to_all_facets_when_nothing_matches():
    req = _backend_req("Menguasai salah satu bahasa Golang, Python, atau PHP")
    assert len(narrow_facets(req)) == 5


def test_apply_facet_narrowing_is_idempotent_and_records_origin():
    req = _backend_req("Mahir dalam pengelolaan basis data relasional PostgreSQL")
    req_set = RequirementSetIR(job_title="t", requirements=[req])
    assert apply_facet_narrowing(req_set) == 1
    assert req.params["facets_narrowed_from"] == 5
    assert apply_facet_narrowing(req_set) == 0
    assert [f.facet_key for f in req.facets] == ["B2"]


def test_facet_signature_ignores_case_and_whitespace():
    a = RequirementFacet(facet_key="F1", hypothesis="Bangun  API", concepts=["b", "a"])
    b = RequirementFacet(facet_key="F1", hypothesis="bangun api", concepts=["a", "b"])
    assert facet_signature(a) == facet_signature(b)


def test_critic_routing_rules():
    rid, cid = "run-1", "cand-1"
    assert decide_critic_routing(["E1"], False, rid, cid, 0.0) == []
    assert decide_critic_routing(["E1"], True, rid, cid, 0.0) == ["E1", "TOP_K"]
    assert decide_critic_routing(["E4"], False, rid, cid, 0.0) == ["E4"]
    assert decide_critic_routing([], True, rid, cid, 0.0) == ["TOP_K"]
    assert decide_critic_routing([], False, rid, cid, 1.0) == ["RANDOM_AUDIT"]
    # the random draw is reproducible
    assert decide_critic_routing([], False, rid, cid, 0.5) == decide_critic_routing([], False, rid, cid, 0.5)


@pytest.mark.asyncio
async def test_llm_semaphore_is_shared_and_sized_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "LLM_MAX_CONCURRENCY", 3)
    from src.infrastructure import gateway

    gateway._semaphores.clear()
    sem = llm_semaphore()
    assert sem is llm_semaphore()
    held = 0
    peak = 0

    async def worker():
        nonlocal held, peak
        async with llm_semaphore():
            held += 1
            peak = max(peak, held)
            await asyncio.sleep(0.01)
            held -= 1

    await asyncio.gather(*(worker() for _ in range(10)))
    assert peak == 3


def test_bare_role_name_resolves_to_its_own_template():
    from src.domain.requirements.facet_templates import resolve_role_family

    assert resolve_role_family("backend") == "backend"
    assert resolve_role_family("Frontend") == "frontend"
    assert resolve_role_family("Backend Developer") == "backend"


# --------------------------------------------------------------------- facets per requirement kind
def _templated(kind: str, description: str, **kw: Any) -> RequirementIR:
    return RequirementIR(
        requirement_id=kw.pop("requirement_id", "R4"),
        description=description,
        kind=kind,
        facets=[RequirementFacet(**t) for t in ROLE_FACET_TEMPLATES["backend"]],
        **kw,
    )


def test_skill_requirement_filled_with_the_role_template_gets_its_own_facet():
    from src.domain.requirements.facet_narrowing import looks_like_template

    req = _templated(
        "SKILL", "Menguasai payment gateway dan integrasi API pihak ketiga", concepts=["skill:payment_gateway"]
    )
    assert looks_like_template(req.facets)
    req_set = RequirementSetIR(job_title="t", requirements=[req])
    assert apply_facet_narrowing(req_set) == 1
    assert [f.facet_key for f in req.facets] == ["R4.F1"]
    facet = req.facets[0]
    assert facet.core and facet.hypothesis.startswith("Menguasai payment gateway")
    assert facet.concepts == ["skill:payment_gateway"]


def test_general_experience_statement_keeps_the_whole_role_template():
    req = _templated(
        "EXPERIENCE_DURATION", "Pengalaman kerja minimal 2 tahun sebagai Backend Developer", requirement_id="R1"
    )
    assert apply_facet_narrowing(RequirementSetIR(job_title="t", requirements=[req])) == 0
    assert len(req.facets) == 5


def test_authored_facets_are_never_replaced():
    authored = RequirementIR(
        requirement_id="R9",
        description="Menguasai Kubernetes",
        kind="SKILL",
        facets=[RequirementFacet(facet_key="K1", hypothesis="mengoperasikan cluster Kubernetes produksi")],
    )
    assert apply_facet_narrowing(RequirementSetIR(job_title="t", requirements=[authored])) == 0
    assert [f.facet_key for f in authored.facets] == ["K1"]


def test_flat_cluster_regression_one_weak_facet_no_longer_sinks_every_criterion():
    """v2.1: all six criteria shared five facets, so one PARTIAL core facet made every criterion PARTIAL."""
    descriptions = [
        ("EXPERIENCE_DURATION", "Pengalaman kerja minimal 2 tahun sebagai Backend Developer"),
        ("SKILL", "Menguasai bahasa pemrograman backend Python"),
        ("SKILL", "Mahir perancangan REST API"),
        ("SKILL", "Mahir basis data relasional PostgreSQL"),
        ("SKILL", "Memahami clean code dan unit testing"),
        ("SKILL", "Integrasi payment gateway"),
    ]
    reqs = [
        _templated(kind, text, requirement_id=f"R{i}", importance="MUST_HAVE", weight=10.0)
        for i, (kind, text) in enumerate(descriptions, 1)
    ]
    req_set = RequirementSetIR(job_title="t", requirements=reqs)
    apply_facet_narrowing(req_set)
    keys = [tuple(f.facet_key for f in r.facets) for r in reqs]
    assert keys[0] == ("B1", "B2", "B3", "B4", "B5")  # general experience statement keeps the template
    assert all(k == (f"R{i}.F1",) for i, k in enumerate(keys[1:], 2))  # every other criterion is judged on its own


@pytest.mark.asyncio
async def test_skill_requirements_are_judged_independently_end_to_end(monkeypatch):
    monkeypatch.setattr(settings, "FACET_NARROWING_ENABLED", True)
    reqs = [
        _templated(
            "SKILL", f"Kriteria keterampilan {name}", requirement_id=f"R{i}", importance="MUST_HAVE", weight=10.0
        )
        for i, name in enumerate(["api", "database", "testing"], 1)
    ]
    req_set = RequirementSetIR(job_title="t", requirements=reqs)
    # one verdict per own facet: R1 ENTAILED, R2 PARTIAL, R3 NOT_ENTAILED
    gw = CountingGateway({})

    async def call_chat(messages, task="matcher", tenant_id=None, json_mode=True, model=None):
        gw.calls[task] = gw.calls.get(task, 0) + 1
        evals = [
            {
                "facet_key": "R1.F1",
                "analysis": "ok",
                "verdict": "ENTAILED",
                "support_atoms": ["A1"],
                "depth_level": "L2",
            },
            {
                "facet_key": "R2.F1",
                "analysis": "ok",
                "verdict": "PARTIAL",
                "support_atoms": ["A1"],
                "depth_level": "L1",
            },
            {
                "facet_key": "R3.F1",
                "analysis": "ok",
                "verdict": "NOT_ENTAILED",
                "support_atoms": [],
                "depth_level": "L0",
            },
        ]
        return {"raw_content": json.dumps({"evaluations": evals, "flags": []})}

    gw.call_chat = call_chat  # type: ignore[method-assign]
    res = await run_screening_pipeline(
        candidates=[_candidate()],
        requirement_set=req_set,
        tenant_id=uuid.uuid4(),
        client=gw,
        ontology=OntologyGraph(version="t"),
    )
    states = {rid: r.state for rid, r in res.top_candidate.requirement_results.items()}
    assert states == {
        "R1": RequirementState.STRONG,
        "R2": RequirementState.PARTIAL,
        "R3": RequirementState.NOT_DEMONSTRATED,
    }
    assert gw.calls["matcher"] == 1  # three single-facet criteria still cost one batched Matcher call
