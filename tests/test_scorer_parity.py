"""Parity test: port of reference_scorer.py vs golden_dataset/generator/reference_scorer.py."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

# Add golden_dataset/generator to path to import reference_scorer
golden_gen_path = Path("docs/spec/golden_dataset/generator").resolve()
if str(golden_gen_path) not in sys.path:
    sys.path.insert(0, str(golden_gen_path))

import reference_scorer  # type: ignore[import-not-found]

from src.domain.scorer import rank, score


def test_scorer_parity_1000_combinations():
    random.seed(42)
    possible_states = ["STRONG", "PARTIAL", "NOT_DEMONSTRATED"]

    jd1 = json.loads(Path("docs/spec/golden_dataset/job_descriptions/JD-01_requirements.approved.json").read_text())
    jd2 = json.loads(Path("docs/spec/golden_dataset/job_descriptions/JD-02_requirements.approved.json").read_text())

    # 1,000 combinations for JD-01
    for i in range(1000):
        states = {r["requirement_id"]: random.choice(possible_states) for r in jd1["requirements"]}
        ref_res = reference_scorer.score(states, jd1)
        my_res = score(states, jd1)

        assert abs(ref_res.raw_score - my_res.raw_score) < 1e-4, (
            f"Mismatch raw_score at JD-01 #{i}: ref {ref_res.raw_score} vs {my_res.raw_score}"
        )
        assert abs(ref_res.final_score - my_res.final_score) < 1e-4, (
            f"Mismatch final_score at JD-01 #{i}: ref {ref_res.final_score} vs {my_res.final_score}"
        )
        assert ref_res.band == my_res.band, f"Mismatch band at JD-01 #{i}: ref {ref_res.band} vs {my_res.band}"
        assert ref_res.recommendation == my_res.recommendation, (
            f"Mismatch recommendation at JD-01 #{i}: ref {ref_res.recommendation} vs {my_res.recommendation}"
        )

    # 1,000 combinations for JD-02
    for i in range(1000):
        states = {r["requirement_id"]: random.choice(possible_states) for r in jd2["requirements"]}
        ref_res = reference_scorer.score(states, jd2)
        my_res = score(states, jd2)

        assert abs(ref_res.raw_score - my_res.raw_score) < 1e-4, (
            f"Mismatch raw_score at JD-02 #{i}: ref {ref_res.raw_score} vs {my_res.raw_score}"
        )
        assert abs(ref_res.final_score - my_res.final_score) < 1e-4, (
            f"Mismatch final_score at JD-02 #{i}: ref {ref_res.final_score} vs {my_res.final_score}"
        )
        assert ref_res.band == my_res.band, f"Mismatch band at JD-02 #{i}: ref {ref_res.band} vs {my_res.band}"
        assert ref_res.recommendation == my_res.recommendation, (
            f"Mismatch recommendation at JD-02 #{i}: ref {ref_res.recommendation} vs {my_res.recommendation}"
        )


def test_ranking_tie_breaker_parity():
    jd1 = json.loads(Path("docs/spec/golden_dataset/job_descriptions/JD-01_requirements.approved.json").read_text())

    candidates = []
    for cid in ["C1", "C2", "C3", "C4", "C5"]:
        states = {r["requirement_id"]: "STRONG" for r in jd1["requirements"]}
        s_res = score(states, jd1)
        candidates.append({"candidate_id": cid, "file": f"{cid}.pdf", "result": s_res, "strong_count": 10})

    ranked = rank(candidates, run_id="run_test")
    assert len(ranked) == 5
    # Deterministic order
    ranked_again = rank(candidates, run_id="run_test")
    assert [c["candidate_id"] for c in ranked] == [c["candidate_id"] for c in ranked_again]
