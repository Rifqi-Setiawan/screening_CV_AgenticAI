"""Unit tests for Scorer v2 (Anti-Keyword Stuffing, Depth Rubric L0..L4, and Deterministic Ranking).

Tests:
1. Anti-stuffing T0 evidence ceiling: evidence from skill_list_item, summary_sentence,
   or MENTION_ONLY is strictly capped at PARTIAL.
2. Competency depth weighting L0..L4 (0.2, 0.4, 0.7, 0.9, 1.0) and score scaling.
3. Supporting atom cap per facet (maximum 3 atoms) to prevent verbose CV bias.
4. Deterministic tie-breaking and stable SHA-256 ranking.
5. Band capping rules (Band A <= 100, Band B <= 74, Band C <= 49) and Band R on AGENT_DISAGREEMENT.
"""

from __future__ import annotations

from typing import Any

from src.agents.schemas.matcher import DepthLevel, FacetEvaluationResult, FacetVerdict
from src.domain.atoms import AtomKind, EvidenceAtom
from src.domain.scoring.scorer_v2 import (
    MAX_SUPPORTING_ATOMS_PER_FACET,
    ScoreResultV2,
    cap_supporting_atoms,
    is_t0_evidence,
    rank_v2,
    score_v2,
    tie_break_key,
)


def _make_sample_req_set() -> dict[str, Any]:
    """Creates a sample requirement set for testing."""
    return {
        "requirements": [
            {
                "requirement_id": "R1",
                "description": "Pengalaman minimal 3 tahun Frontend Development",
                "category": "EXPERIENCE",
                "importance": "MUST_HAVE",
                "weight": 50.0,
                "facets": [
                    {"facet_key": "F1", "hypothesis": "Membangun UI SPA dengan React", "core": True},
                    {"facet_key": "F2", "hypothesis": "Mengelola client-side state", "core": True},
                ],
            },
            {
                "requirement_id": "R2",
                "description": "Penguasaan TypeScript dan Next.js",
                "category": "HARD_SKILLS",
                "importance": "MUST_HAVE",
                "weight": 30.0,
                "facets": [
                    {"facet_key": "F3", "hypothesis": "Slicing UI responsive", "core": False},
                ],
            },
            {
                "requirement_id": "R3",
                "description": "Sertifikasi frontend atau cloud",
                "category": "EDUCATION_CERT",
                "importance": "NICE_TO_HAVE",
                "weight": 20.0,
                "facets": [],
            },
        ],
        "category_weights": {
            "EXPERIENCE": 50.0,
            "HARD_SKILLS": 30.0,
            "EDUCATION_CERT": 20.0,
        },
    }


def test_t0_evidence_detection():
    """Verify is_t0_evidence identifies skill lists, summaries, and mention-only flags."""
    skill_atom = EvidenceAtom(
        atom_key="a_skill",
        kind=AtomKind.SKILL_LIST_ITEM.value,
        entry_ref="skills",
        page=1,
        char_start=0,
        char_end=20,
        red_start=0,
        red_end=20,
        text_redacted="React, Next.js",
    )
    assert is_t0_evidence(skill_atom) is True

    summary_atom = EvidenceAtom(
        atom_key="a_summary",
        kind=AtomKind.SUMMARY_SENTENCE.value,
        entry_ref="summary",
        page=1,
        char_start=0,
        char_end=50,
        red_start=0,
        red_end=50,
        text_redacted="I am a dedicated React developer with 5 years experience.",
    )
    assert is_t0_evidence(summary_atom) is True

    # Real exp bullet should NOT be T0
    exp_atom = EvidenceAtom(
        atom_key="a_exp",
        kind=AtomKind.EXP_BULLET.value,
        entry_ref="exp_0",
        page=1,
        char_start=0,
        char_end=80,
        red_start=0,
        red_end=80,
        text_redacted="Architected React microfrontends serving 1M daily active users.",
    )
    assert is_t0_evidence(exp_atom) is False


def test_t0_capped_at_partial_anti_stuffing():
    """Verify that a requirement with only T0 evidence is capped at PARTIAL even if initial state was STRONG."""
    req_set = _make_sample_req_set()

    # Candidate provided only a skill list atom
    skill_atom = EvidenceAtom(
        atom_key="atom_skill_list",
        kind=AtomKind.SKILL_LIST_ITEM.value,
        entry_ref="skills",
        page=1,
        char_start=0,
        char_end=30,
        red_start=0,
        red_end=30,
        text_redacted="Skills: React, Redux, Next.js",
    )

    judgments = [
        FacetEvaluationResult(
            facet_key="F1",
            analysis="Candidate listed React in skills section",
            verdict=FacetVerdict.ENTAILED,
            support_atoms=["atom_skill_list"],
            depth_level=DepthLevel.L0,
        ),
        FacetEvaluationResult(
            facet_key="F2",
            analysis="Candidate listed Redux in skills section",
            verdict=FacetVerdict.ENTAILED,
            support_atoms=["atom_skill_list"],
            depth_level=DepthLevel.L0,
        ),
    ]

    # Pipeline initially claimed STRONG for R1
    states = {
        "R1": "STRONG",
        "R2": "STRONG",
        "R3": "STRONG",
    }

    result = score_v2(
        states=states,
        requirement_set=req_set,
        facet_judgments=judgments,
        atoms=[skill_atom],
    )

    # R1 MUST be capped at PARTIAL due to T0 ceiling rule
    assert result.effective_states["R1"] == "PARTIAL", "R1 should have been capped at PARTIAL"
    assert any("T0_CAPPED_AT_PARTIAL:R1" in f for f in result.anti_stuffing_flags)
    # Because MUST_HAVE R1 is PARTIAL, band drops to Band B
    assert result.band == "B"
    assert result.final_score <= 74.0


def test_depth_factor_weighting_l0_to_l4():
    """Verify that depth level scaling (L0..L4) properly influences final scores."""
    req_set = _make_sample_req_set()
    states = {"R1": "STRONG", "R2": "STRONG", "R3": "STRONG"}

    # Evaluate candidate with high competency depth (L4: Principal/Architect)
    res_l4 = score_v2(
        states=states,
        requirement_set=req_set,
        depth_levels={"R1": "L4", "R2": "L4", "R3": "L4"},
    )

    # Evaluate candidate with intermediate depth (L2: Autonomous Practitioner)
    res_l2 = score_v2(
        states=states,
        requirement_set=req_set,
        depth_levels={"R1": "L2", "R2": "L2", "R3": "L2"},
    )

    # Evaluate candidate with basic / guided depth (L1: Guided / Coursework)
    res_l1 = score_v2(
        states=states,
        requirement_set=req_set,
        depth_levels={"R1": "L1", "R2": "L1", "R3": "L1"},
    )

    # Evaluate candidate with mention-only depth (L0: Mention only)
    res_l0 = score_v2(
        states=states,
        requirement_set=req_set,
        depth_levels={"R1": "L0", "R2": "L0", "R3": "L0"},
    )

    # Scores must strictly follow L4 > L2 > L1 > L0
    assert res_l4.final_score > res_l2.final_score
    assert res_l2.final_score > res_l1.final_score
    assert res_l1.final_score > res_l0.final_score

    # Check exact proportions: L4 = 100%, L2 = 70%, L1 = 40%, L0 = 20%
    assert res_l4.raw_score == 100.0
    assert res_l2.raw_score == 70.0
    assert res_l1.raw_score == 40.0
    assert res_l0.raw_score == 20.0


def test_supporting_atoms_cap_at_three():
    """Verify that supporting atoms are capped at 3 per facet to neutralize verbose CV stuffing."""
    capped_list, was_capped = cap_supporting_atoms(["a1", "a2", "a3", "a4", "a5", "a6"])
    assert len(capped_list) == MAX_SUPPORTING_ATOMS_PER_FACET
    assert was_capped is True
    assert capped_list == ["a1", "a2", "a3"]

    capped_exact, was_capped_exact = cap_supporting_atoms(["a1", "a2", "a3"])
    assert len(capped_exact) == 3
    assert was_capped_exact is False

    capped_under, was_capped_under = cap_supporting_atoms(["a1", "a2"])
    assert len(capped_under) == 2
    assert was_capped_under is False


def test_deterministic_tie_breaking_and_ranking():
    """Verify stable, reproducible SHA-256 tie breaking independent of candidate order."""
    run_id = "test_run_2026"
    cand_a = "cand_alpha"
    cand_b = "cand_beta"

    key_a = tie_break_key(cand_a, run_id)
    key_b = tie_break_key(cand_b, run_id)

    # Key must be deterministic and reproducible
    assert key_a == tie_break_key(cand_a, run_id)
    assert key_a != key_b

    # Rank two candidates with identical scores and strong counts
    res_equal = ScoreResultV2(
        raw_score=80.0,
        final_score=80.0,
        band="A",
        capped=False,
        recommendation="SHORTLIST",
        color="green",
    )

    item1 = {"candidate_id": cand_a, "result": res_equal, "strong_count": 3}
    item2 = {"candidate_id": cand_b, "result": res_equal, "strong_count": 3}

    # Sorting order must be identical regardless of input ordering
    order_1 = rank_v2([item1, item2], run_id=run_id)
    order_2 = rank_v2([item2, item1], run_id=run_id)

    assert [x["candidate_id"] for x in order_1] == [x["candidate_id"] for x in order_2]


def test_band_capping_and_disagreement_manual_check():
    """Verify Band caps (A=100, B=74, C=49) and Band R / MANUAL_CHECK when AGENT_DISAGREEMENT is present."""
    req_set = _make_sample_req_set()

    # 1 MUST_HAVE failed (R1 is PARTIAL) -> Band B capped at 74.0
    states_b = {"R1": "PARTIAL", "R2": "STRONG", "R3": "STRONG"}
    res_b = score_v2(states=states_b, requirement_set=req_set)
    assert res_b.band == "B"
    assert res_b.capped is True
    assert res_b.final_score == 74.0

    # 2 MUST_HAVEs failed (R1 and R2 are PARTIAL) -> Band C capped at 49.0
    states_c = {"R1": "PARTIAL", "R2": "PARTIAL", "R3": "STRONG"}
    res_c = score_v2(states=states_c, requirement_set=req_set)
    assert res_c.band == "C"
    assert res_c.capped is True
    assert res_c.final_score == 49.0


def test_agent_disagreement_is_a_review_signal_by_default():
    """v2.2: disagreement keeps the score band, downgrades SHORTLIST to REVIEW and adds a review flag."""
    req_set = _make_sample_req_set()
    states = {"R1": "STRONG", "R2": "STRONG", "R3": "STRONG"}
    res = score_v2(states=states, requirement_set=req_set, flags=["AGENT_DISAGREEMENT"])
    assert res.band == "A"
    assert res.recommendation == "REVIEW"
    assert "AGENT_DISAGREEMENT_REVIEW" in res.flags


def test_agent_disagreement_legacy_mode_forces_band_r(monkeypatch):
    """v2.1 behaviour stays available behind AGENT_DISAGREEMENT_FORCES_BAND_R."""
    from src.infrastructure.config import settings

    monkeypatch.setattr(settings, "AGENT_DISAGREEMENT_FORCES_BAND_R", True)
    req_set = _make_sample_req_set()
    states = {"R1": "STRONG", "R2": "STRONG", "R3": "STRONG"}
    res = score_v2(states=states, requirement_set=req_set, flags=["AGENT_DISAGREEMENT"])
    assert res.band == "R"
    assert res.recommendation == "MANUAL_CHECK"
    assert res.color == "gray"


def test_score_interval_collapses_without_unknown_and_widens_with_it():
    req_set = _make_sample_req_set()
    exact = score_v2(states={"R1": "STRONG", "R2": "STRONG", "R3": "STRONG"}, requirement_set=req_set)
    assert exact.score_lo == exact.score_hi == exact.final_score
    assert exact.interval_straddles_boundary is False

    # R3 (NICE_TO_HAVE, weight 20) unknown: worst case 80, best case 100, point estimate 100.
    wide = score_v2(states={"R1": "STRONG", "R2": "STRONG", "R3": "UNKNOWN"}, requirement_set=req_set)
    assert wide.score_lo == 80.0
    assert wide.score_hi == 100.0


def test_interval_straddling_shortlist_cutoff_is_flagged():
    req_set = _make_sample_req_set()
    res2 = score_v2(states={"R1": "PARTIAL", "R2": "STRONG", "R3": "UNKNOWN"}, requirement_set=req_set)
    # best case (25+30+20)/100 = 75 capped by band B at 74; worst case (25+30)/100 = 55
    assert res2.score_lo < 70 <= res2.score_hi
    assert res2.interval_straddles_boundary is True
    assert "SCORE_INTERVAL_STRADDLES_SHORTLIST" in res2.flags


def test_rank_orders_capped_candidates_by_raw_score_before_hash():
    """Band caps give equal final scores; raw score decides the order inside the group, not the hash."""
    req_set = _make_sample_req_set()
    strongish = score_v2(
        states={"R1": "PARTIAL", "R2": "STRONG", "R3": "STRONG"}, requirement_set=req_set
    )  # B, raw 100 -> 74
    weaker = score_v2(
        states={"R1": "PARTIAL", "R2": "STRONG", "R3": "NOT_DEMONSTRATED"}, requirement_set=req_set
    )  # B, raw lower
    assert strongish.band == weaker.band == "B"
    assert strongish.raw_score > weaker.raw_score
    # force a final-score tie by capping both at the band cap
    weaker.final_score = strongish.final_score = 74.0
    items = [
        {"candidate_id": "a", "result": weaker, "strong_count": 1},
        {"candidate_id": "b", "result": strongish, "strong_count": 1},
    ]
    for run in ("r1", "r2", "r3", "r4", "r5", "r6"):
        assert [x["candidate_id"] for x in rank_v2(items, run_id=run)] == ["b", "a"]
