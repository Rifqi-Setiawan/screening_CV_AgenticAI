"""Domain-context implication: conservative, grounded, visible."""

from __future__ import annotations

import pytest

from src.agents.schemas.matcher import DepthLevel, FacetEvaluationResult, FacetVerdict
from src.domain.atoms import EvidenceAtom
from src.domain.matching.domain_inference import apply_domain_inference


def _atom(key, kind, text):
    return EvidenceAtom(key, kind, "exp_1", 1, 0, len(text), 0, len(text), text)


def _j(key, verdict, depth=DepthLevel.L0):
    return FacetEvaluationResult(facet_key=key, analysis="x", verdict=verdict, depth_level=depth)


HYP = {"R4.F1": "Keahlian manajemen basis data relasional PostgreSQL atau MySQL", "R3.F1": "Merancang REST API"}
TRADING = _atom(
    "E1.B1", "exp_bullet", "Mengembangkan order matching engine dan sistem deposit/withdrawal platform trading kripto."
)


@pytest.mark.parametrize("verdict", [FacetVerdict.NOT_ENTAILED, FacetVerdict.UNKNOWN])
def test_transaction_system_work_lifts_database_facet_to_partial_l1(verdict):
    out, flags = apply_domain_inference([_j("R4.F1", verdict)], HYP, [TRADING])
    j = out[0]
    assert (j.verdict, j.depth_level, j.rationale_code) == (FacetVerdict.PARTIAL, DepthLevel.L1, "DOMAIN_INFERENCE")
    assert j.support_atoms == ["E1.B1"]
    assert flags == ["DOMAIN_INFERENCE:R4.F1"]


def test_never_reaches_entailed_and_never_touches_stronger_verdicts():
    out, _ = apply_domain_inference([_j("R4.F1", FacetVerdict.PARTIAL, DepthLevel.L2)], HYP, [TRADING])
    assert (out[0].verdict, out[0].depth_level, out[0].rationale_code) == (
        FacetVerdict.PARTIAL,
        DepthLevel.L2,
        "DIRECT_EVIDENCE",
    )
    out, _ = apply_domain_inference([_j("R4.F1", FacetVerdict.ENTAILED, DepthLevel.L3)], HYP, [TRADING])
    assert out[0].verdict == FacetVerdict.ENTAILED


def test_only_experience_and_project_bullets_count_as_evidence():
    claims = [
        _atom("S1", "summary_sentence", "Berpengalaman di fintech dan payment"),
        _atom("K1", "skill_list_item", "payment gateway, banking"),
    ]
    out, flags = apply_domain_inference([_j("R4.F1", FacetVerdict.NOT_ENTAILED)], HYP, claims)
    assert out[0].verdict == FacetVerdict.NOT_ENTAILED and flags == []


def test_unrelated_facets_and_unrelated_work_are_left_alone():
    out, flags = apply_domain_inference([_j("R3.F1", FacetVerdict.NOT_ENTAILED)], HYP, [TRADING])
    assert out[0].verdict == FacetVerdict.NOT_ENTAILED and flags == []
    blog = _atom("E2.B1", "exp_bullet", "Menulis konten dan mengelola media sosial perusahaan.")
    out, flags = apply_domain_inference([_j("R4.F1", FacetVerdict.NOT_ENTAILED)], HYP, [blog])
    assert out[0].verdict == FacetVerdict.NOT_ENTAILED and flags == []
