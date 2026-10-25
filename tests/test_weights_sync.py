from src.domain.scorer import score


def test_score_renormalizes_when_categories_empty():
    # Only HARD_SKILLS is present (configured weight 30 in overall weights)
    req_set = {
        "category_weights": {
            "EXPERIENCE": 40,
            "HARD_SKILLS": 30,
            "EDUCATION_CERT": 15,
            "ACHIEVEMENT": 15,
        },
        "requirements": [
            {
                "requirement_id": "R1",
                "category": "HARD_SKILLS",
                "importance": "MUST_HAVE",
                "weight": 10,
            },
            {
                "requirement_id": "R2",
                "category": "HARD_SKILLS",
                "importance": "MUST_HAVE",
                "weight": 20,
            },
        ],
    }

    # Candidate satisfies all requirements
    states = {"R1": "STRONG", "R2": "STRONG"}
    res = score(states, req_set)

    # Must be 100.0, NOT 30.0!
    assert res.final_score == 100.0
    assert res.raw_score == 100.0
    assert res.band == "A"
    assert res.recommendation == "SHORTLIST"


def test_score_intra_category_weights_proportional():
    req_set = {
        "category_weights": {"HARD_SKILLS": 100},
        "requirements": [
            {
                "requirement_id": "R1",
                "category": "HARD_SKILLS",
                "importance": "NICE_TO_HAVE",
                "weight": 10,
            },
            {
                "requirement_id": "R2",
                "category": "HARD_SKILLS",
                "importance": "NICE_TO_HAVE",
                "weight": 20,
            },
        ],
    }

    # Case 1: R1 STRONG (weight 10), R2 NOT_DEMONSTRATED (weight 20) -> 10/30 = 33.3%
    res1 = score({"R1": "STRONG", "R2": "NOT_DEMONSTRATED"}, req_set)
    assert res1.raw_score == 33.3
    assert res1.category_scores["HARD_SKILLS"] == 33.3

    # Case 2: R1 NOT_DEMONSTRATED (weight 10), R2 STRONG (weight 20) -> 20/30 = 66.7%
    res2 = score({"R1": "NOT_DEMONSTRATED", "R2": "STRONG"}, req_set)
    assert res2.raw_score == 66.7
    assert res2.category_scores["HARD_SKILLS"] == 66.7
