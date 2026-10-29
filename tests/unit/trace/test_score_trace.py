"""Score trace: score -> requirement -> facet -> atom -> verbatim CV sentence."""

from __future__ import annotations

from typing import Any

from src.domain.score_trace import build_score_trace, explain_flag, locate_in_text, source_ref

CV = (
    "Ringkasan\nBackend engineer yang suka belajar.\n\n"
    "Pengalaman Kerja\nBackend Developer di PT Contoh (2021 - 2024)\n"
    "- Membangun REST API pembayaran\n  dengan FastAPI untuk 50 ribu pengguna.\n"
    "- Mengoptimasi query PostgreSQL pada tabel transaksi.\n\n"
    "Keahlian\nPython, Docker, Kubernetes, Redis\n"
)
API_TEXT = "Membangun REST API pembayaran dengan FastAPI untuk 50 ribu pengguna."
DB_TEXT = "Mengoptimasi query PostgreSQL pada tabel transaksi."


def _atom(key: str, kind: str, text: str, hint: int = 0, **extra: Any) -> dict[str, Any]:
    return {
        "atom_key": key,
        "id": f"uuid-{key}",
        "kind": kind,
        "page": 1,
        "char_start": 1,
        "char_end": 9,
        "red_start": hint,
        "red_end": hint + len(text),
        "text_redacted": text,
        **extra,
    }


ATOMS = [
    _atom("E1.B1", "exp_bullet", API_TEXT, hint=0),  # offsets are stale: must be found by search
    _atom("E1.B2", "exp_bullet", DB_TEXT, hint=CV.index(DB_TEXT)),  # exact offsets
    _atom("K1", "skill_list_item", "Python, Docker, Kubernetes, Redis", hint=CV.index("Python, Docker")),
]


def _reqs() -> list[dict[str, Any]]:
    return [
        {
            "requirement_id": "R1",
            "description": "Pengalaman minimal 2 tahun backend",
            "kind": "EXPERIENCE_DURATION",
            "category": "EXPERIENCE",
            "importance": "MUST_HAVE",
            "weight": 40.0,
            "target_domains": ["backend"],
            "duration_policy": {"min_months": 24},
            "lint_flags": [],
            "facets": [{"facet_key": "F1", "hypothesis": "membangun API produksi", "core": True}],
        },
        {
            "requirement_id": "R2",
            "description": "Menguasai basis data relasional",
            "kind": "SKILL",
            "category": "HARD_SKILLS",
            "importance": "MUST_HAVE",
            "weight": 40.0,
            "target_domains": [],
            "duration_policy": {},
            "lint_flags": [],
            "facets": [{"facet_key": "F2", "hypothesis": "mengelola basis data relasional", "core": True}],
        },
        {
            "requirement_id": "R3",
            "description": "Menguasai Kubernetes",
            "kind": "SKILL",
            "category": "HARD_SKILLS",
            "importance": "NICE_TO_HAVE",
            "weight": 20.0,
            "target_domains": [],
            "duration_policy": {},
            "lint_flags": [],
            "facets": [{"facet_key": "F3", "hypothesis": "mengoperasikan Kubernetes", "core": True}],
        },
    ]


def _judgments() -> list[dict[str, Any]]:
    return [
        {
            "facet_key": "F1",
            "verdict": "FacetVerdict.ENTAILED",
            "depth_level": "L2",
            "analysis": "E1.B1 membuktikan API produksi",
            "support_atom_keys": ["E1.B1"],
            "support_atom_ids": [],
            "method": "llm",
        },
        {
            "facet_key": "F2",
            "verdict": "PARTIAL",
            "depth_level": "L1",
            "analysis": "hanya optimasi query",
            "support_atom_keys": ["E1.B2"],
            "support_atom_ids": [],
            "method": "llm",
        },
        {
            "facet_key": "F3",
            "verdict": "PARTIAL",
            "depth_level": "L0",
            "analysis": "hanya disebut di daftar keahlian",
            "support_atom_keys": ["K1"],
            "support_atom_ids": [],
            "method": "llm",
        },
    ]


def _trace(**over: Any) -> dict[str, Any]:
    kw: dict[str, Any] = dict(
        stored={
            "final_score": 70.0,
            "raw_score": 70.0,
            "band": "B",
            "recommendation": "REVIEW",
            "flags": ["AGENT_DISAGREEMENT_REVIEW", "T0_CAPPED_AT_PARTIAL:R3"],
            "coverage": 1.0,
        },
        requirements=_reqs(),
        requirement_states={"R1": "STRONG", "R2": "PARTIAL", "R3": "PARTIAL"},
        category_weights={},
        facet_judgments=_judgments(),
        critic_reviews=[
            {
                "facet_key": "F2",
                "verdict_action": "DOWNGRADE",
                "final_verdict": "PARTIAL",
                "original_verdict": "ENTAILED",
                "reasoning": "Tidak ada bukti desain skema.",
                "analysis": "",
                "is_disagreement": True,
                "support_atoms": [],
            }
        ],
        domain_durations=[
            {
                "domain": "backend",
                "months_lo": 36.0,
                "months_hi": 36.0,
                "month_ledger": [
                    {"month": "2021-01", "weight": 1.0, "contributing_entry": "exp_1"},
                    {"month": "2021-02", "weight": 1.0, "contributing_entry": "exp_1"},
                    {"month": "2021-04", "weight": 1.0, "contributing_entry": "exp_1"},
                ],
            }
        ],
        atoms=ATOMS,
        full_text=CV,
    )
    kw.update(over)
    return build_score_trace(**kw)


# ------------------------------------------------------------------ source
def test_quote_is_a_verbatim_slice_of_the_cv_found_even_with_stale_offsets():
    ref = source_ref(ATOMS[0], CV)
    assert ref["source_found"] and ref["span"] is not None
    start, end = ref["span"]
    assert CV[start:end].split() == API_TEXT.split()  # same words, original line break preserved in the slice
    assert "\n" in CV[start:end]
    assert ref["quote"] == CV[start:end].strip()
    assert (
        "Membangun REST API" in CV[start:end]
        and ref["context_before"].endswith("PT Contoh (2021 - 2024)\n-")
        or ref["context_before"]
    )
    assert ref["context_after"].lstrip().startswith("- Mengoptimasi")


def test_exact_offsets_are_trusted_and_nearest_duplicate_wins():
    ref = source_ref(ATOMS[1], CV)
    assert ref["span"] == [CV.index(DB_TEXT), CV.index(DB_TEXT) + len(DB_TEXT)]
    text = "aaa SAMA bbb SAMA ccc"
    assert locate_in_text(text, "SAMA", hint=14) == (13, 17)
    assert locate_in_text(text, "SAMA", hint=2) == (4, 8)
    assert locate_in_text(text, "tidak ada") is None


def test_atom_missing_from_the_text_is_reported_not_faked():
    ref = source_ref(_atom("X", "exp_bullet", "Kalimat yang tidak ada di CV"), CV)
    assert ref["source_found"] is False and ref["span"] is None and ref["quote"] == "Kalimat yang tidak ada di CV"
    no_text = source_ref(ATOMS[0], None)
    assert no_text["source_found"] is False


def test_tiers_separate_work_evidence_from_claims():
    assert source_ref(ATOMS[0], CV)["tier"] == "T2" and source_ref(ATOMS[0], CV)["is_evidence"]
    k = source_ref(ATOMS[2], CV)
    assert k["tier"] == "T0" and not k["is_evidence"] and "bukan bukti kerja" in k["tier_label"]


# ------------------------------------------------------------------ trace
def test_trace_follows_score_to_requirement_to_facet_to_cv_sentence():
    t = _trace()
    r2 = next(r for r in t["requirements"] if r["requirement_id"] == "R2")
    f2 = r2["facets"][0]
    assert r2["state"] == "PARTIAL" and r2["points"] == 20.0 and r2["max_points"] == 40.0
    assert f2["verdict"] == "PARTIAL" and f2["evidence"][0]["quote"].startswith("Mengoptimasi query PostgreSQL")
    assert f2["critic"]["action"] == "DOWNGRADE" and f2["critic"]["original_verdict"] == "ENTAILED"
    assert "Tidak ada bukti desain skema" in f2["critic"]["reasoning"]
    assert "F2" in r2["why"] and "Sebagian terbukti" in r2["why"]
    assert t["cited_atoms"] == ["E1.B1", "E1.B2", "K1"]


def test_strong_requirement_explains_depth_and_duration():
    r1 = _trace()["requirements"][0]
    assert r1["state"] == "STRONG" and r1["points"] == 40.0
    assert "berkedalaman L2" in r1["why"]
    assert "Durasi relevan 36 bulan, memenuhi minimum 24 bulan" in r1["why"]
    assert [(p["start"], p["end"], p["months"]) for p in r1["duration"]["periods"]] == [
        ("2021-01", "2021-02", 2),
        ("2021-04", "2021-04", 1),
    ]


def test_claim_only_support_is_called_out():
    r3 = _trace()["requirements"][2]
    assert r3["facets"][0]["evidence"][0]["is_evidence"] is False
    assert "Dibatasi PARTIAL karena hanya didukung klaim" in r3["why"]


def test_summary_explains_band_cap_and_recommendation():
    s = _trace()["summary"]
    assert s["band"] == "B" and s["final_score"] == 70.0 and s["capped"] is False
    assert "R2" in s["band_reason"] and "belum terlampaui" in s["band_reason"]
    assert "penilai tidak sepakat" in s["recommendation_reason"]
    assert s["score_interval"] == [70.0, 70.0]
    capped = _trace(
        stored={
            "final_score": 74.0,
            "raw_score": 90.0,
            "band": "B",
            "recommendation": "REVIEW",
            "flags": [],
            "coverage": 1.0,
        }
    )
    assert capped["summary"]["capped"] is True
    assert "dibatasi maksimal 74" in capped["summary"]["band_reason"] and "90" in capped["summary"]["band_reason"]


def test_consistency_check_recomputes_and_flags_mismatch_instead_of_hiding_it():
    ok = _trace(
        stored={
            "final_score": 70.0,
            "raw_score": 70.0,
            "band": "B",
            "recommendation": "REVIEW",
            "flags": [],
            "coverage": 1.0,
        }
    )
    assert ok["consistency"]["consistent"] is True and ok["consistency"]["note"] == ""
    old = _trace(
        stored={
            "final_score": 50.0,
            "raw_score": 50.0,
            "band": "R",
            "recommendation": "MANUAL_CHECK",
            "flags": [],
            "coverage": 1.0,
        }
    )
    assert old["consistency"]["consistent"] is False
    assert "aturan skor versi sebelumnya" in old["consistency"]["note"]
    assert old["summary"]["final_score"] == 50.0  # the stored number stays the one that counts


def test_unknown_requirement_is_not_counted_and_legacy_judgments_are_marked_untracked():
    legacy = [dict(j, support_atom_keys=[], support_atom_ids=[]) for j in _judgments()]
    t = _trace(requirement_states={"R1": "STRONG", "R2": "UNKNOWN", "R3": "PARTIAL"}, facet_judgments=legacy)
    r2 = t["requirements"][1]
    assert r2["counted"] is False and r2["points"] is None
    assert t["summary"]["counted_weight"] == 60.0
    assert all(f["evidence_tracked"] is False and f["evidence"] == [] for r in t["requirements"] for f in r["facets"])


def test_flags_are_explained_in_plain_language():
    assert "teks tersembunyi" in explain_flag("HIDDEN_TEXT").lower()
    assert "klaim" in explain_flag("T0_CAPPED_AT_PARTIAL:R4").lower()
    assert explain_flag("SOMETHING_NEW") == ""
    t = _trace()
    assert {f["flag"] for f in t["flags"]} == {"AGENT_DISAGREEMENT_REVIEW", "T0_CAPPED_AT_PARTIAL:R3"}
    assert all(f["meaning"] for f in t["flags"])
