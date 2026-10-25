"""Unit tests for temporal date normalization and anomaly detection."""

from src.domain.temporal.date_normalizer import (
    abs_month_to_str,
    abs_month_to_ym,
    normalize_date_range,
    ym_to_abs_month,
)


def test_abs_month_helpers():
    """Verify conversion between (year, month), absolute month, and string representation."""
    abs_m = ym_to_abs_month(2020, 1)
    assert abs_m == 2020 * 12 + 1
    y, m = abs_month_to_ym(abs_m)
    assert (y, m) == (2020, 1)
    assert abs_month_to_str(abs_m) == "2020-01"

    abs_m_dec = ym_to_abs_month(2025, 12)
    assert abs_month_to_ym(abs_m_dec) == (2025, 12)
    assert abs_month_to_str(abs_m_dec) == "2025-12"


def test_standard_indonesian_english_month_names():
    """Verify Indonesian and English month names and abbreviations parse accurately."""
    as_of = (2026, 10)

    # Standard Indonesian Jan - Des
    iv = normalize_date_range("Jan 2020 - Des 2021", as_of=as_of)
    assert iv.is_valid
    assert iv.precision == "month"
    assert iv.start_lo == ym_to_abs_month(2020, 1)
    assert iv.end_hi == ym_to_abs_month(2021, 12)
    assert iv.optimistic_months == 24
    assert iv.pessimistic_months == 24

    # Indonesian Agust / Agu / Agt / Ags variations
    for aug_str in ["Agt 2021", "Agu 2021", "Ags 2021", "Agst 2021", "Agust 2021", "Agustus 2021"]:
        iv_aug = normalize_date_range(start_raw=aug_str, end_raw="Okt 2021", as_of=as_of)
        assert iv_aug.is_valid
        assert iv_aug.start_lo == ym_to_abs_month(2021, 8)
        assert iv_aug.end_hi == ym_to_abs_month(2021, 10)
        assert iv_aug.optimistic_months == 3

    # English August / Oct
    iv_en = normalize_date_range("August 2021 to October 2021", as_of=as_of)
    assert iv_en.is_valid
    assert iv_en.start_lo == ym_to_abs_month(2021, 8)
    assert iv_en.end_hi == ym_to_abs_month(2021, 10)

    # Peb / Feb, Mrt / Mar, Mei / May
    iv_peb = normalize_date_range("Peb 2021 s.d. Mrt 2021", as_of=as_of)
    assert iv_peb.is_valid
    assert iv_peb.start_lo == ym_to_abs_month(2021, 2)
    assert iv_peb.end_hi == ym_to_abs_month(2021, 3)
    assert iv_peb.optimistic_months == 2


def test_range_separators():
    """Verify various ID and EN range separators (s.d., s/d, hingga, sampai, to, etc.)."""
    as_of = (2026, 10)

    separators = [
        " - ",
        " – ",
        " — ",
        " s.d. ",
        " s/d ",
        " sd ",
        " hingga ",
        " sampai ",
        " sampai dengan ",
        " to ",
        " until ",
    ]
    for sep in separators:
        text = f"Jan 2021{sep}Mar 2021"
        iv = normalize_date_range(text, as_of=as_of)
        assert iv.is_valid, f"Failed for separator: {sep!r}"
        assert iv.start_lo == ym_to_abs_month(2021, 1)
        assert iv.end_hi == ym_to_abs_month(2021, 3)
        assert iv.optimistic_months == 3


def test_present_and_ongoing():
    """Verify present and Indonesian ongoing keywords resolve to as_of date."""
    as_of_str = "2026-10-01"
    as_of_abs = ym_to_abs_month(2026, 10)

    ongoing_keywords = [
        "present",
        "sekarang",
        "saat ini",
        "kini",
        "now",
        "current",
        "ongoing",
        "masih bekerja",
        "aktif",
    ]

    for kw in ongoing_keywords:
        iv = normalize_date_range(start_raw="Jan 2025", end_raw=kw, as_of=as_of_str)
        assert iv.is_valid
        assert iv.end_lo == as_of_abs
        assert iv.end_hi == as_of_abs
        assert iv.optimistic_months == (as_of_abs - ym_to_abs_month(2025, 1) + 1)


def test_year_only_interval_and_inference():
    """Verify year-only intervals output optimistic & pessimistic intervals per Blueprint §C4."""
    as_of = (2026, 10)

    # "2018–2019" -> start in [2018-01, 2018-12], end in [2019-01, 2019-12]
    iv = normalize_date_range("2018–2019", as_of=as_of)
    assert iv.is_valid
    assert iv.precision == "year"
    assert "DATE_YEAR_ONLY_INFERRED" in iv.flags
    assert iv.start_lo == ym_to_abs_month(2018, 1)
    assert iv.start_hi == ym_to_abs_month(2018, 12)
    assert iv.end_lo == ym_to_abs_month(2019, 1)
    assert iv.end_hi == ym_to_abs_month(2019, 12)

    # Optimistic = [2018-01, 2019-12] = 24 months
    assert iv.optimistic_months == 24
    # Pessimistic = [2018-12, 2019-01] = 2 months
    assert iv.pessimistic_months == 2

    # Single year "2020" -> start in [2020-01, 2020-12], end in [2020-01, 2020-12]
    iv_single = normalize_date_range("2020", as_of=as_of)
    assert iv_single.is_valid
    assert iv_single.precision == "year"
    assert iv_single.optimistic_months == 12
    assert iv_single.pessimistic_months == 1


def test_inherited_year_from_end():
    """Verify start without year inherits year from end (e.g. 'Jan - Des 2020')."""
    as_of = (2026, 10)
    iv = normalize_date_range("Jan - Des 2020", as_of=as_of)
    assert iv.is_valid
    assert iv.start_lo == ym_to_abs_month(2020, 1)
    assert iv.end_hi == ym_to_abs_month(2020, 12)
    assert iv.optimistic_months == 12


def test_anomaly_inverted_dates_swapped_vs_rejected():
    """Verify inverted dates <= 1 month are swapped with flag; > 1 month are DATE_ANOMALY."""
    as_of = (2026, 10)

    # Swapped case (diff = 1 month)
    iv_swap = normalize_date_range(start_raw="Feb 2020", end_raw="Jan 2020", as_of=as_of)
    assert iv_swap.is_valid
    assert "DATE_SWAPPED" in iv_swap.flags
    assert iv_swap.start_lo == ym_to_abs_month(2020, 1)
    assert iv_swap.end_hi == ym_to_abs_month(2020, 2)
    assert iv_swap.optimistic_months == 2

    # Anomaly case (diff > 1 month)
    iv_anom = normalize_date_range(start_raw="Des 2021", end_raw="Jan 2020", as_of=as_of)
    assert not iv_anom.is_valid
    assert "DATE_ANOMALY" in iv_anom.flags
    assert iv_anom.optimistic_months == 0
    assert iv_anom.pessimistic_months == 0


def test_anomaly_future_start_date():
    """Verify start date strictly greater than as_of raises DATE_ANOMALY."""
    as_of = (2026, 10)
    iv_future = normalize_date_range("Jan 2028 - Des 2028", as_of=as_of)
    assert not iv_future.is_valid
    assert "DATE_ANOMALY" in iv_future.flags


def test_anomaly_career_duration_exceeds_40_years():
    """Verify experience duration exceeding 40 years (480 months) raises DATE_ANOMALY."""
    as_of = (2026, 10)
    # 1980 to 2025 = 45 years = 541 months > 480
    iv_long = normalize_date_range("Jan 1980 - Jan 2025", as_of=as_of)
    assert not iv_long.is_valid
    assert "DATE_ANOMALY" in iv_long.flags


def test_invalid_or_garbage_strings():
    """Verify completely unparseable or empty strings raise DATE_ANOMALY."""
    as_of = (2026, 10)
    iv_empty = normalize_date_range("", as_of=as_of)
    assert not iv_empty.is_valid
    assert "DATE_ANOMALY" in iv_empty.flags

    iv_garbage = normalize_date_range("pengalaman kerja terdahulu", as_of=as_of)
    assert not iv_garbage.is_valid
    assert "DATE_ANOMALY" in iv_garbage.flags
