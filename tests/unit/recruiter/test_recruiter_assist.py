"""Fase 5: interview probes (value of information), interview re-scoring, Copilot HR tools."""

from __future__ import annotations

import pytest

from src.domain.copilot import (
    CopilotStore,
    check_query,
    compare,
    enforce_citations,
    explain_score,
    get_atoms,
    short_id,
    timeline,
)
from src.domain.interview import InterviewAnswer, apply_interview_answers, build_probes, rescore, validate_probe
from src.domain.interview.probe import blocked_terms_in
from src.domain.matching.ontology_shortcut import determine_atom_tier


def _facet(key, hyp, core=True):
    return {"facet_key": key, "hypothesis": hyp, "core": core, "concepts": []}


def _req_set(extra_hypothesis: str | None = None) -> dict:
    return {
        "category_weights": {},
        "requirements": [
            {
                "requirement_id": "R1",
                "description": "backend inti",
                "category": "EXPERIENCE",
                "kind": "ROLE_EQUIVALENCE",
                "importance": "MUST_HAVE",
                "weight": 50.0,
                "facets": [
                    _facet("X1", "merancang REST API"),
                    _facet("X2", extra_hypothesis or "mengelola database relasional"),
                ],
            },
            {
                "requirement_id": "R2",
                "description": "kualitas",
                "category": "HARD_SKILLS",
                "kind": "ROLE_EQUIVALENCE",
                "importance": "MUST_HAVE",
                "weight": 30.0,
                "facets": [_facet("X3", "menulis automated testing")],
            },
            {
                "requirement_id": "R3",
                "description": "bonus",
                "category": "HARD_SKILLS",
                "kind": "ROLE_EQUIVALENCE",
                "importance": "NICE_TO_HAVE",
                "weight": 20.0,
                "facets": [_facet("X4", "mengoperasikan message queue")],
            },
        ],
    }


def _j(key, verdict, depth="L2", atoms=None):
    return {
        "facet_key": key,
        "verdict": verdict,
        "depth_level": depth,
        "support_atoms": atoms if atoms is not None else (["A1"] if verdict == "ENTAILED" else []),
    }


JUDGMENTS = [
    _j("X1", "ENTAILED"),
    _j("X2", "UNKNOWN", "L0"),
    _j("X3", "PARTIAL", "L1", ["A3"]),
    _j("X4", "NOT_ENTAILED", "L0"),
]


# ------------------------------------------------------------------ probes
def test_probes_skip_settled_facets_and_rank_by_expected_swing():
    probes = build_probes(_req_set(), JUDGMENTS, "cand-1", budget=5)
    keys = [p.facet_key for p in probes]
    assert "X1" not in keys  # already ENTAILED at L2
    assert keys and keys[0] in {"X2", "X3"}  # MUST_HAVE facets outrank the nice-to-have one
    assert [p.voi for p in probes] == sorted((p.voi for p in probes), reverse=True)
    assert all(p.status == "PENDING_APPROVAL" for p in probes)


def test_budget_is_respected_and_identical_for_every_candidate():
    a = build_probes(_req_set(), JUDGMENTS, "cand-a", budget=2)
    b = build_probes(_req_set(), JUDGMENTS, "cand-b", budget=2)
    assert len(a) == len(b) == 2
    assert [p.facet_key for p in a] == [p.facet_key for p in b]
    assert build_probes(_req_set(), JUDGMENTS, "cand-a", budget=0) == []


def test_probe_carries_target_atoms_listen_for_and_followup_ladder():
    probe = next(p for p in build_probes(_req_set(), JUDGMENTS, "cand-1") if p.facet_key == "X3")
    assert probe.target_atom_ids == ["A3"]
    assert "menulis automated testing" in probe.question
    assert len(probe.follow_ups) == 3 and probe.listen_for_strong and probe.listen_for_weak
    assert probe.score_if_all_resolved >= probe.score_without_this
    assert probe.why.startswith("Facet")


def test_unknown_is_a_reason_to_ask_not_a_penalty():
    all_unknown = [_j(k, "UNKNOWN", "L0") for k in ("X1", "X2", "X3", "X4")]
    probes = build_probes(_req_set(), all_unknown, "cand-1", budget=10)
    assert {p.facet_key for p in probes} == {"X1", "X2", "X3", "X4"}
    assert all(p.current_verdict == "UNKNOWN" for p in probes)


def test_probe_touching_a_protected_topic_is_dropped_not_softened():
    probes = build_probes(
        _req_set(extra_hypothesis="memahami usia pengguna dan status pernikahan"), JUDGMENTS, "cand-1", budget=10
    )
    assert "X2" not in {p.facet_key for p in probes}


@pytest.mark.parametrize(
    "text",
    ["Apakah Anda berencana hamil?", "Berapa usia Anda?", "Apa agama Anda?", "Sudah menikah?", "Berapa anak Anda?"],
)
def test_blocked_topics_are_detected(text):
    assert blocked_terms_in(text)


def test_default_question_text_is_clean():
    for p in build_probes(_req_set(), JUDGMENTS, "cand-1", budget=10):
        assert validate_probe(p) == []


# ------------------------------------------------------------------ interview answers -> atoms -> re-score
def test_strong_answer_raises_the_score_and_records_a_t2_interview_atom():
    res = apply_interview_answers(
        _req_set(),
        JUDGMENTS,
        [InterviewAnswer("X2", "STRONG", "Saya merancang skema 40 tabel di PostgreSQL ...", probe_id="p1")],
        "cand-1",
    )
    assert res.after["final_score"] > res.before["final_score"]
    assert "INTERVIEW_ADJUSTED" in res.after["flags"]
    assert res.adjusted_facets == ["X2"]
    atom = res.interview_atoms[0]
    assert atom["kind"] == "interview_answer" and atom["rating"] == "STRONG"
    assert determine_atom_tier(atom) == "T2"


def test_weak_answer_does_not_improve_and_adequate_is_t1():
    res = apply_interview_answers(_req_set(), JUDGMENTS, [InterviewAnswer("X3", "WEAK", "tidak ingat")], "cand-1")
    assert res.after["final_score"] <= res.before["final_score"]
    assert determine_atom_tier({"kind": "interview_answer", "rating": "ADEQUATE", "visibility": "VISIBLE"}) == "T1"


def test_original_result_is_left_intact_and_invalid_rating_rejected():
    before, _ = rescore(_req_set(), JUDGMENTS)
    apply_interview_answers(_req_set(), JUDGMENTS, [InterviewAnswer("X2", "STRONG", "ok")], "cand-1")
    again, _ = rescore(_req_set(), JUDGMENTS)
    assert (before.final_score, before.band) == (again.final_score, again.band)
    with pytest.raises(ValueError):
        apply_interview_answers(_req_set(), JUDGMENTS, [InterviewAnswer("X2", "AMAZING", "ok")], "cand-1")


def test_interview_answer_text_is_scrubbed_of_protected_attributes():
    res = apply_interview_answers(
        _req_set(),
        JUDGMENTS,
        [InterviewAnswer("X2", "ADEQUATE", "Saya wanita berusia 30 tahun, pernah membangun database")],
        "c",
    )
    text = res.interview_atoms[0]["text_redacted"]
    assert "wanita" not in text.lower()


# ------------------------------------------------------------------ copilot
CID_A, CID_B = "aaaaaaaa-1111-2222-3333-444444444444", "bbbbbbbb-1111-2222-3333-444444444444"


def _payload():
    def row(cid, rank, band, score, atoms, judgments, months):
        return {
            "candidate_id": cid,
            "rank": rank,
            "band": band,
            "final_score": score,
            "recommendation": "REVIEW",
            "file_name": "1234_Nama Asli Pelamar.pdf",
            "flags": ["T0_CAPPED_AT_PARTIAL:R2"],
            "requirement_states": {"R1": "STRONG", "R2": "PARTIAL"},
            "grounding_atoms": [
                {"atom_key": k, "kind": "exp_bullet", "page": 1, "char_start": 1, "char_end": 9, "text_redacted": t}
                for k, t in atoms
            ],
            "facet_judgments": judgments,
            "critic_reviews": [
                {"facet_key": "X1", "verdict_action": "CONFIRM", "final_verdict": "ENTAILED", "is_disagreement": False}
            ],
            "domain_durations": [
                {
                    "domain": "backend",
                    "months_lo": 5,
                    "months_hi": 5,
                    "month_ledger": [{"month": m, "weight": 1.0, "contributing_entry": "exp_1"} for m in months],
                }
            ],
        }

    return {
        "rankings": [
            row(
                CID_A,
                1,
                "A",
                100.0,
                [("E1.B1", "Membangun REST API pembayaran"), ("E1.B2", "Optimasi query PostgreSQL")],
                [
                    {
                        "requirement_id": "R1",
                        "facet_key": "X1",
                        "verdict": "FacetVerdict.ENTAILED",
                        "depth_level": "L2",
                        "support_atom_ids": ["E1.B1"],
                        "method": "llm",
                    }
                ],
                ["2024-11", "2024-12", "2025-01", "2025-02", "2025-04"],
            ),
            row(
                CID_B,
                2,
                "B",
                74.0,
                [("E9.B1", "Menulis unit test pytest")],
                [
                    {
                        "requirement_id": "R2",
                        "facet_key": "X3",
                        "verdict": "PARTIAL",
                        "depth_level": "L1",
                        "support_atom_ids": ["E9.B1"],
                        "method": "llm",
                    }
                ],
                ["2023-01"],
            ),
        ]
    }


def _store():
    return CopilotStore.from_rankings_payload(_payload())


def test_get_atoms_filters_by_facet_and_never_exposes_file_names():
    out = get_atoms(_store(), CID_A, facet="X1")
    assert [a["atom"] for a in out["atoms"]] == ["E1.B1"]
    assert out["candidate"] == short_id(CID_A) == "aaaaaaaa"
    assert "Nama Asli" not in str(out) and "Nama Asli" not in str(compare(_store(), [CID_A, CID_B]))


def test_compare_and_explain_score_use_stored_results():
    cmp_ = compare(_store(), [short_id(CID_A), short_id(CID_B)], requirement_id="R2")
    assert [r["candidate"] for r in cmp_["rows"]] == ["aaaaaaaa", "bbbbbbbb"]
    assert cmp_["rows"][0]["requirement_state"] == "PARTIAL"
    exp = explain_score(_store(), CID_A)
    assert exp["facets"][0]["verdict"] == "ENTAILED"
    assert exp["facets"][0]["evidence"][0]["text"] == "Membangun REST API pembayaran"


def test_timeline_merges_consecutive_months_and_splits_on_gaps():
    periods = timeline(_store(), CID_A, "backend")["periods"]
    assert [(p["start"], p["end"], p["months"]) for p in periods] == [
        ("2024-11", "2025-02", 4),
        ("2025-04", "2025-04", 1),
    ]


def test_unknown_candidate_raises():
    with pytest.raises(KeyError):
        _store().candidate("zzzz")


def test_citation_enforcement_keeps_only_grounded_sentences():
    answer = (
        "Kandidat A membangun REST API pembayaran [E1.B1]. "
        "Kandidat A juga ahli Kubernetes. "
        "Kandidat A menyebut pengalaman cloud [E7.B7]. "
        "Tidak ada bukti pengalaman message queue."
    )
    rep = enforce_citations(answer, _store(), [CID_A])
    lines = rep.cleaned.split("\n")
    assert lines[0].endswith("[E1.B1].") and "kalimat dihapus" in lines[1] and "kalimat dihapus" in lines[2]
    assert lines[3].startswith("Tidak ada bukti")
    assert not rep.ok and {v["reason"] for v in rep.violations} == {"no_citation", "unknown_citation"}


def test_citation_must_belong_to_the_candidates_under_discussion():
    rep = enforce_citations("B memakai pytest [E9.B1].", _store(), [CID_A])
    assert not rep.ok  # E9.B1 belongs to candidate B, not A
    assert enforce_citations("B memakai pytest [E9.B1].", _store(), [CID_B]).ok


def test_protected_attribute_inference_queries_are_refused():
    allowed, msg = check_query("Apakah kandidat C-0003 beragama Islam dan sudah menikah?")
    assert not allowed and "atribut terlindungi" in msg
    assert check_query("Bandingkan pengalaman PostgreSQL kandidat teratas.") == (True, "")
