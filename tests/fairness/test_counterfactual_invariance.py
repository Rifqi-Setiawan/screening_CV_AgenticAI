"""Fase 4 fairness: counterfactual invariance and protected-attribute leakage at the LLM boundary.

Swapping gender, religion, age, marital status, campus tier or address in an otherwise identical CV must not
change any score, state, band or flag, and none of those attributes may appear in a prompt sent to the model.
These tests use a content-driven oracle in place of the LLM: they prove the *pipeline* (retrieval, scoring,
prompt building) adds no demographic dependence. The live-model version of this check is
`tests/fairness/test_live_model_gate.py`.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

import pytest

from src.domain.atoms import EvidenceAtom
from src.domain.ontology import OntologyGraph
from src.domain.pipeline import CandidateInput, run_screening_pipeline
from src.domain.protected_attributes import scrub_protected_attributes
from src.domain.requirements.schemas import RequirementFacet, RequirementIR, RequirementSetIR
from src.infrastructure.config import settings

EVIDENCE = [
    ("E1", "exp_bullet", "Membangun REST API pembayaran untuk 50 ribu pengguna."),
    ("E2", "exp_bullet", "Merancang skema database dan optimasi query PostgreSQL."),
    ("E3", "exp_bullet", "Menulis automated testing dan CI untuk layanan backend."),
]
KEYWORDS = {"X1": "api", "X2": "database", "X3": "testing"}

VARIANTS = {
    "base": {
        "summary": "Backend engineer berpengalaman membangun REST API.",
        "education": "S1 Teknik Informatika, Institut Teknologi Bandung, lulus 2016",
        "extra": "Organisasi: Himpunan Mahasiswa Informatika",
    },
    "female_muslim_young_single": {
        "summary": "Wanita muslimah, 27 tahun, belum menikah. Backend engineer berpengalaman membangun REST API.",
        "education": "S1 Teknik Informatika, Universitas Islam Antah Berantah, lulus 2019",
        "extra": "Organisasi: Rohis; Alamat: Jl. Melati 5, Bekasi",
    },
    "male_christian_older_married": {
        "summary": "Pria, 45 tahun, menikah, beragama Kristen. Backend engineer berpengalaman membangun REST API.",
        "education": "S1 Teknik Informatika, Universitas Kristen Petra, lulus 1999",
        "extra": "Organisasi: Pemuda Gereja; Domisili: Surabaya",
    },
}
FORBIDDEN = [
    "muslimah",
    "Rohis",
    "Kristen",
    "Gereja",
    "Bekasi",
    "Surabaya",
    "Wanita",
    "Pria",
    "27 tahun",
    "45 tahun",
    "menikah",
    "Petra",
    "Islam Antah",
    "Melati",
    "Agama",
]


class OracleGateway:
    """Verdicts depend only on the evidence bullets; every prompt is recorded for leakage checks."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def verify_redacted_text(self, text: str) -> None:
        pass

    async def call_chat(self, messages, task="matcher", tenant_id=None, json_mode=True, model=None):
        user = "\n".join(m["content"] for m in messages)
        self.prompts.append(user)
        if task == "critic":
            return {"raw_content": json.dumps({"facet_reviews": [], "has_disagreement": False})}
        atoms = re.findall(r"- \[(\w+)\] \(kind: (\w+)[^)]*\): (.*)", user)
        evals = []
        for key in dict.fromkeys(re.findall(r"Facet \[(\w+)\]", user)):
            hits = [a for a, kind, text in atoms if kind == "exp_bullet" and KEYWORDS[key] in text.lower()]
            evals.append(
                {
                    "facet_key": key,
                    "analysis": "bukti literal" if hits else "tidak ada bukti",
                    "verdict": "ENTAILED" if hits else "NOT_ENTAILED",
                    "support_atoms": hits[:1],
                    "depth_level": "L2" if hits else "L0",
                    "rationale_code": "DIRECT_EVIDENCE" if hits else "NO_EVIDENCE",
                }
            )
        return {"raw_content": json.dumps({"evaluations": evals, "flags": []})}


def _atoms(variant: dict[str, str]) -> list[EvidenceAtom]:
    rows = [(k, kind, text) for k, kind, text in EVIDENCE]
    rows += [
        ("S1", "summary_sentence", variant["summary"]),
        ("ED1", "education", variant["education"]),
        ("K1", "skill_list_item", variant["extra"]),
    ]
    atoms, pos = [], 0
    for key, kind, text in rows:
        atoms.append(EvidenceAtom(key, kind, "exp_1", 1, pos, pos + len(text), pos, pos + len(text), text))
        pos += len(text) + 1
    return atoms


def _req_set() -> RequirementSetIR:
    facets = [
        RequirementFacet(facet_key=k, hypothesis=f"hipotesis {k}", core=True, concepts=[f"skill:{k.lower()}"])
        for k in KEYWORDS
    ]
    req = RequirementIR(
        requirement_id="R1",
        description="Kemampuan backend",
        kind="ROLE_EQUIVALENCE",
        importance="MUST_HAVE",
        weight=100.0,
        facets=facets,
    )
    return RequirementSetIR(job_title="Backend", requirements=[req])


async def _screen(variant_name: str) -> tuple[Any, OracleGateway]:
    gw = OracleGateway()
    res = await run_screening_pipeline(
        candidates=[
            CandidateInput(candidate_id=uuid.UUID(int=1), atoms=_atoms(VARIANTS[variant_name]), raw_title="Engineer")
        ],
        requirement_set=_req_set(),
        run_id=uuid.UUID(int=2),
        tenant_id=uuid.UUID(int=3),
        client=gw,
        critic_client=gw,
        ontology=OntologyGraph(version="t"),
    )
    return res.top_candidate, gw


def _fingerprint(c: Any) -> dict[str, Any]:
    return {
        "band": c.band,
        "score": c.final_score,
        "raw": c.raw_score,
        "recommendation": c.recommendation,
        "states": {k: v.state.value for k, v in c.requirement_results.items()},
        "depths": c.depth_breakdown,
        "flags": sorted(c.flags),
        "support": sorted({a for j in c.facet_judgments for a in j.support_atoms}),
    }


@pytest.fixture(autouse=True)
def _policy(monkeypatch):
    monkeypatch.setattr(settings, "FACET_NARROWING_ENABLED", False)
    monkeypatch.setattr(settings, "CRITIC_TOP_K", 5)
    monkeypatch.setattr(settings, "CRITIC_RANDOM_AUDIT_RATE", 0.0)
    monkeypatch.setattr(settings, "SCRUB_PROTECTED_ATTRIBUTES", True)
    monkeypatch.setattr(settings, "MATCHER_EXCLUDED_ATOM_KINDS", ["education"])


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", [v for v in VARIANTS if v != "base"])
async def test_demographic_variants_score_identically_to_the_base_cv(variant):
    base, _ = await _screen("base")
    other, _ = await _screen(variant)
    assert _fingerprint(other) == _fingerprint(base)
    assert base.band == "A" and base.final_score == 100.0  # the oracle really rewarded the evidence


@pytest.mark.asyncio
@pytest.mark.parametrize("variant", list(VARIANTS))
async def test_no_protected_attribute_reaches_any_prompt(variant):
    _, gw = await _screen(variant)
    assert gw.prompts, "the matcher/critic must have been called"
    blob = "\n".join(gw.prompts)
    leaked = [t for t in FORBIDDEN if t.lower() in blob.lower()]
    assert leaked == [], leaked


@pytest.mark.asyncio
async def test_without_scrubbing_the_leak_would_be_real(monkeypatch):
    """Guards the guard: with the policy off the attributes do reach the prompt, so the tests above bite."""
    monkeypatch.setattr(settings, "SCRUB_PROTECTED_ATTRIBUTES", False)
    _, gw = await _screen("female_muslim_young_single")
    blob = "\n".join(gw.prompts).lower()
    assert "muslimah" in blob and "bekasi" in blob


@pytest.mark.asyncio
async def test_education_atoms_are_not_sent_to_the_model():
    _, gw = await _screen("base")
    blob = "\n".join(gw.prompts)
    assert "Institut Teknologi Bandung" not in blob and "lulus 2016" not in blob


@pytest.mark.parametrize(
    ("text", "expected_gone", "categories"),
    [
        (
            "Wanita muslimah, 27 tahun, belum menikah",
            ["Wanita", "muslimah", "27 tahun", "belum menikah"],
            ["AGE", "GENDER", "MARITAL", "RELIGION"],
        ),
        ("Tempat/Tanggal Lahir: Bandung, 12 Mei 1996", ["Bandung", "1996"], ["BIRTH"]),
        ("Alamat: Jl. Merdeka 10, Jakarta Selatan", ["Merdeka", "Jakarta"], ["ADDRESS"]),
        ("Agama: Islam", ["Islam"], ["RELIGION"]),
        ("S1 Universitas Kristen Petra", ["Petra", "Kristen"], ["RELIGION"]),
        ("Tinggi badan: 170 cm, golongan darah O", ["170", "darah"], ["PHYSICAL"]),
    ],
)
def test_scrub_removes_statements_and_reports_categories(text, expected_gone, categories):
    out, found = scrub_protected_attributes(text)
    assert all(word not in out for word in expected_gone), out
    assert found == categories


@pytest.mark.parametrize(
    "text",
    [
        "Membangun platform Islamic finance dan syariah banking dengan FastAPI.",
        "Memimpin tim 5 engineer; menurunkan latensi p95 dari 800ms ke 200ms.",
        "Menerapkan age verification pada layanan onboarding fintech.",
    ],
)
def test_scrub_keeps_domain_vocabulary_intact(text):
    out, found = scrub_protected_attributes(text)
    assert out == text and found == []
