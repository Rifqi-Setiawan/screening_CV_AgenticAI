from src.domain.scorer import score


def test_scorer_flags_low_coverage_and_downgrades_shortlist():
    # 10 requirements of weight 10 each (total weight 100)
    reqs = [
        {
            "requirement_id": f"R{i}",
            "category": "HARD_SKILLS",
            "importance": "MUST_HAVE" if i == 1 else "NICE_TO_HAVE",
            "weight": 10,
        }
        for i in range(1, 11)
    ]
    req_set = {"category_weights": {"HARD_SKILLS": 100}, "requirements": reqs}

    # Only R1 is STRONG, other 9 are UNKNOWN
    states = {"R1": "STRONG"}
    for i in range(2, 11):
        states[f"R{i}"] = "UNKNOWN"

    res = score(states, req_set)

    # 1. Coverage must be 0.1 (10 / 100)
    assert res.coverage == 0.1

    # 2. LOW_COVERAGE flag must be present
    assert "LOW_COVERAGE" in res.flags

    # 3. Recommendation must NOT be SHORTLIST (downgraded to MANUAL_CHECK)
    assert res.recommendation != "SHORTLIST"
    assert res.recommendation == "MANUAL_CHECK"
