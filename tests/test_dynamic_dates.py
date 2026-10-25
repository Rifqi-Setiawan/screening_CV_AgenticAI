from datetime import date

from src.domain.kind_rules import eval_experience_duration, parse_ym


def test_parse_ym_with_dynamic_as_of():
    # Job currently running evaluated as of 2027-06-01
    y, m = parse_ym("present", as_of="2027-06-01")
    assert y == 2027
    assert m == 6

    # Job currently running evaluated as of today
    today = date.today()
    y_today, m_today = parse_ym("present")
    assert y_today == today.year
    assert m_today == today.month


def test_eval_experience_duration_dynamic_date():
    # Candidate started job in 2025-01 and is still working there
    profile = {
        "experiences": [
            {
                "title": "Backend Engineer",
                "organization": "Tech Corp",
                "start": "2025-01",
                "end": "present",
                "bullets": [{"text": "Python API development"}],
            }
        ]
    }
    req = {
        "requirement_id": "R1",
        "description": "Minimal 3 tahun pengalaman backend engineer",
        "kind": "EXPERIENCE_DURATION",
        "params": {"min_months": 36},
    }

    # As of 2026-01-01 (1 year = 12 months) -> NOT enough for 36 months
    st_2026, _, m_2026, _, _ = eval_experience_duration(profile, req, as_of="2026-01-01")
    assert st_2026 != "STRONG"

    # As of 2028-06-01 (3.5 years = 41 months) -> STRONG
    st_2028, _, m_2028, _, _ = eval_experience_duration(profile, req, as_of="2028-06-01")
    assert st_2028 == "STRONG"
    assert any(v >= 36 for v in m_2028.values())


def test_year_only_inference_and_duration_24_months():
    # 2020 - 2022 -> 2020-07 to 2022-06 = 24 months
    s_ym = parse_ym("2020", is_end=False)
    e_ym = parse_ym("2022", is_end=True)
    assert s_ym == (2020, 7)
    assert e_ym == (2022, 6)

    # 2020-07 to 2022-06 inclusive is 24 months
    months = (e_ym[0] * 12 + e_ym[1]) - (s_ym[0] * 12 + s_ym[1]) + 1
    assert months == 24

    profile = {
        "experiences": [
            {
                "title": "Backend Engineer",
                "organization": "Tech Corp",
                "start": "2020",
                "end": "2022",
                "bullets": [{"text": "Python API development"}],
            }
        ]
    }
    req = {
        "requirement_id": "R1",
        "description": "Minimal 2 tahun pengalaman backend engineer",
        "kind": "EXPERIENCE_DURATION",
        "params": {"min_months": 24},
    }
    st, _, m, _, flags = eval_experience_duration(profile, req, as_of="2026-10-14")
    assert st == "STRONG"
    assert "DATE_YEAR_ONLY_INFERRED" in flags


def test_present_with_dynamic_as_of():
    y, m = parse_ym("Present", as_of="2027-03-15")
    assert (y, m) == (2027, 3)
