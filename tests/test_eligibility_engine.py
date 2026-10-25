import uuid

from src.domain.eligibility import evaluate_all, evaluate_rule


def test_dob_age_max_calculations():
    # DOB 1999-03-12, ref 2026-11-01, AGE_MAX 27 -> age 27 -> ELIGIBLE
    r1 = {
        "id": str(uuid.uuid4()),
        "rule_type": "AGE_MAX",
        "value": {"years": 27},
        "reference_date": "2026-11-01",
    }
    res1 = evaluate_rule(r1, {"dob": "1999-03-12"})
    assert res1["status"] == "ELIGIBLE"
    assert res1["reason_code"] == "AGE_WITHIN_RANGE"

    # DOB 1999-03-12, ref 2026-03-11, AGE_MAX 26 -> age 26 -> ELIGIBLE (day before birthday)
    r2 = {
        "id": str(uuid.uuid4()),
        "rule_type": "AGE_MAX",
        "value": {"years": 26},
        "reference_date": "2026-03-11",
    }
    res2 = evaluate_rule(r2, {"dob": "1999-03-12"})
    assert res2["status"] == "ELIGIBLE"
    assert res2["reason_code"] == "AGE_WITHIN_RANGE"

    # DOB 1998-01-01, ref 2026-11-01, AGE_MAX 27 -> age 28 -> NOT_ELIGIBLE AGE_ABOVE_MAX
    res3 = evaluate_rule(r1, {"dob": "1998-01-01"})
    assert res3["status"] == "NOT_ELIGIBLE"
    assert res3["reason_code"] == "AGE_ABOVE_MAX"


def test_dob_year_only_ambiguity():
    # DOB only year 1999, ref 2026-11-01, AGE_MAX 27 -> range [26, 27] -> ELIGIBLE
    r = {
        "id": str(uuid.uuid4()),
        "rule_type": "AGE_MAX",
        "value": {"years": 27},
        "reference_date": "2026-11-01",
    }
    res = evaluate_rule(r, {"dob": "1999"})
    assert res["status"] == "ELIGIBLE"
    assert res["reason_code"] == "AGE_WITHIN_RANGE"

    # DOB only year 1999, ref 2026-11-01, AGE_MAX 26 -> range [26, 27] -> UNKNOWN DOB_YEAR_ONLY_AMBIGUOUS
    r_amb = {
        "id": str(uuid.uuid4()),
        "rule_type": "AGE_MAX",
        "value": {"years": 26},
        "reference_date": "2026-11-01",
    }
    res_amb = evaluate_rule(r_amb, {"dob": "1999"})
    assert res_amb["status"] == "UNKNOWN"
    assert res_amb["reason_code"] == "DOB_YEAR_ONLY_AMBIGUOUS"

    # DOB only year 1990, AGE_MAX 27 -> range [35, 36] -> NOT_ELIGIBLE
    res_old = evaluate_rule(r, {"dob": "1990"})
    assert res_old["status"] == "NOT_ELIGIBLE"
    assert res_old["reason_code"] == "AGE_ABOVE_MAX"


def test_invariant_I4_missing_dob_is_unknown_not_not_eligible():
    r = {
        "id": str(uuid.uuid4()),
        "rule_type": "AGE_MAX",
        "value": {"years": 27},
        "reference_date": "2026-11-01",
    }
    res = evaluate_rule(r, {})
    assert res["status"] == "UNKNOWN"
    assert res["reason_code"] == "DOB_MISSING"


def test_gender_evaluations():
    r = {
        "id": str(uuid.uuid4()),
        "rule_type": "GENDER",
        "value": {"allowed": ["F"]},
    }
    assert evaluate_rule(r, {"gender": "F"})["status"] == "ELIGIBLE"
    assert evaluate_rule(r, {"gender": "Wanita"})["status"] == "ELIGIBLE"
    assert evaluate_rule(r, {"gender": "M"})["status"] == "NOT_ELIGIBLE"
    assert evaluate_rule(r, {"gender": "Pria"})["status"] == "NOT_ELIGIBLE"
    assert evaluate_rule(r, {})["status"] == "UNKNOWN"


def test_combination_and_not_applicable():
    r_age = {
        "id": str(uuid.uuid4()),
        "rule_type": "AGE_MAX",
        "value": {"years": 25},
        "reference_date": "2026-11-01",
    }
    r_gender = {
        "id": str(uuid.uuid4()),
        "rule_type": "GENDER",
        "value": {"allowed": ["F"]},
    }

    # One UNKNOWN and one NOT_ELIGIBLE -> overall NOT_ELIGIBLE
    res1 = evaluate_all([r_age, r_gender], {"dob": None, "gender": "M"})
    assert res1["overall_status"] == "NOT_ELIGIBLE"

    # One ELIGIBLE and one UNKNOWN -> UNKNOWN
    res2 = evaluate_all([r_age, r_gender], {"dob": "2003-01-01", "gender": None})
    assert res2["overall_status"] == "UNKNOWN"

    # No rules -> NOT_APPLICABLE
    res_none = evaluate_all([], {"dob": "1999-01-01", "gender": "M"})
    assert res_none["overall_status"] == "NOT_APPLICABLE"


def test_invariant_I2_output_never_leaks_age_dob_or_gender():
    r = {
        "id": str(uuid.uuid4()),
        "rule_type": "AGE_MAX",
        "value": {"years": 27},
        "reference_date": "2026-11-01",
    }
    res = evaluate_all([r], {"dob": "1999-03-12", "gender": "F"})
    assert "age" not in res
    assert "dob" not in res
    assert "gender" not in res
    for d in res["details"]:
        assert "age" not in d
        assert "dob" not in d
        assert "gender" not in d
        assert "1999" not in str(d)
        assert "27" not in d.get("message", "")
