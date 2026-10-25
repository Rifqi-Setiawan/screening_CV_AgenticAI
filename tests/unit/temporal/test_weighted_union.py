"""Unit and property tests for sweep-line weighted calendar union temporal engine."""

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from src.domain.temporal.date_normalizer import (
    normalize_date_range,
    ym_to_abs_month,
)
from src.domain.temporal.weighted_union import (
    DurationPolicy,
    TemporalEntry,
    calculate_multidomain_weighted_union,
    calculate_weighted_union,
)


def test_concrete_rifqi_case_fragmented_backend_duration():
    """Golden case: Rifqi backend experience with fragmented roles.

    Candidate has:
      - Entry A: Backend 18 months, PRIMARY (1.0), full-time (1.0) -> w = 1.0
      - Entry B: Magang Backend 6 months, PRIMARY (1.0), magang (0.5) -> w = 0.5
      - Entry C: Software Engineer (fokus BE) 12 months, PRIMARY (1.0), full-time (1.0) -> w = 1.0
    Min requirement: 36 months backend.

    Under default policy:
      18 * 1.0 + 6 * 0.5 + 12 * 1.0 = 33.0 months -> PARTIAL
    Under recruiter policy (magang = 1.0):
      18 * 1.0 + 6 * 1.0 + 12 * 1.0 = 36.0 months -> STRONG
    """
    as_of = (2026, 10)

    # Entry A: 2020-01 to 2021-06 (18 months)
    iv_a = normalize_date_range(start_raw="Jan 2020", end_raw="Jun 2021", as_of=as_of)
    assert iv_a.optimistic_months == 18
    entry_a = TemporalEntry(
        entry_id="exp_A",
        interval=iv_a,
        role_title="Backend Developer",
        allocation_level="PRIMARY",
        employment_type="full-time",
    )

    # Entry B: 2021-07 to 2021-12 (6 months internship)
    iv_b = normalize_date_range(start_raw="Jul 2021", end_raw="Des 2021", as_of=as_of)
    assert iv_b.optimistic_months == 6
    entry_b = TemporalEntry(
        entry_id="exp_B",
        interval=iv_b,
        role_title="Backend Intern",
        allocation_level="PRIMARY",
        employment_type="magang",
    )

    # Entry C: 2022-01 to 2022-12 (12 months SE backend)
    iv_c = normalize_date_range(start_raw="Jan 2022", end_raw="Des 2022", as_of=as_of)
    assert iv_c.optimistic_months == 12
    entry_c = TemporalEntry(
        entry_id="exp_C",
        interval=iv_c,
        role_title="Software Engineer",
        allocation_level="PRIMARY",
        employment_type="full-time",
    )

    entries = [entry_a, entry_b, entry_c]

    # Evaluation 1: Default policy (magang = 0.5)
    default_policy = DurationPolicy()
    res_default = calculate_weighted_union(
        entries=entries,
        domain="backend",
        min_months=36,
        policy=default_policy,
        as_of=as_of,
    )
    assert res_default.months_hi == 33.0
    assert res_default.months_lo == 33.0
    assert res_default.state == "PARTIAL"
    assert len(res_default.month_ledger) == 36

    # Verify ledger transparency for Entry B
    b_ledger = [row for row in res_default.month_ledger if row["contributing_entry"] == "exp_B"]
    assert len(b_ledger) == 6
    assert all(row["weight"] == 0.5 for row in b_ledger)

    # Evaluation 2: Recruiter custom policy (magang = 1.0)
    custom_policy = DurationPolicy(emp_weights={**default_policy.emp_weights, "magang": 1.0, "internship": 1.0})
    res_custom = calculate_weighted_union(
        entries=entries,
        domain="backend",
        min_months=36,
        policy=custom_policy,
        as_of=as_of,
    )
    assert res_custom.months_hi == 36.0
    assert res_custom.months_lo == 36.0
    assert res_custom.state == "STRONG"

    b_custom_ledger = [row for row in res_custom.month_ledger if row["contributing_entry"] == "exp_B"]
    assert len(b_custom_ledger) == 6
    assert all(row["weight"] == 1.0 for row in b_custom_ledger)


def test_overlap_handling_anti_double_counting():
    """Verify concurrent jobs in the same domain take MAX weight, not SUM."""
    # Entry 1: Primary Full-time backend (months 100 to 117 = 18 months, weight = 1.0)
    # Entry 2: Part-time backend (months 110 to 115 = 6 months, weight = 0.5)
    entry_1 = TemporalEntry(entry_id="exp_main", interval=(100, 117), weight=1.0)
    entry_2 = TemporalEntry(entry_id="exp_side", interval=(110, 115), weight=0.5)

    res = calculate_weighted_union([entry_1, entry_2])
    # Total duration must be 18 months, not 18 + 3 = 21 months
    assert res.months_hi == 18.0

    # For overlapping months 110 to 115, contributing entry must be exp_main with weight 1.0
    overlap_months = [row for row in res.month_ledger if row["month"] in [f"{110 // 12:04d}-{110 % 12 + 1:02d}"]]
    if overlap_months:
        assert overlap_months[0]["contributing_entry"] == "exp_main"
        assert overlap_months[0]["weight"] == 1.0


def test_multidomain_parallel_separation():
    """Verify parallel jobs across different domains (FE and BE) accumulate in their respective domains."""
    # Job from month 24241 to 24252 (12 months in 2020)
    # Role 1: Backend Developer (BE: 1.0, FE: 0.0)
    # Role 2: Freelance Frontend (BE: 0.0, FE: 0.75)
    entry_be = TemporalEntry(
        entry_id="be_job",
        interval=(24241, 24252),
        domain_weights={"backend": 1.0, "frontend": 0.0},
    )
    entry_fe = TemporalEntry(
        entry_id="fe_freelance",
        interval=(24241, 24252),
        domain_weights={"backend": 0.0, "frontend": 0.75},
    )

    results = calculate_multidomain_weighted_union(
        entries=[entry_be, entry_fe],
        domains=["backend", "frontend"],
    )

    assert results["backend"].months_hi == 12.0
    assert results["frontend"].months_hi == 9.0  # 12 * 0.75 = 9.0


def test_uncertainty_escalation_trigger_e5():
    """Verify months_lo < min <= months_hi triggers PARTIAL + DATE_UNCERTAIN."""
    # "2018–2020":
    # start in [2018-01, 2018-12], end in [2020-01, 2020-12]
    # start_lo = 24217, start_hi = 24228
    # end_lo = 24241, end_hi = 24252
    # pessimistic = [24228, 24241] = 14 months
    # optimistic = [24217, 24252] = 36 months
    iv = normalize_date_range("2018–2020", as_of=(2026, 10))
    assert iv.pessimistic_months == 14
    assert iv.optimistic_months == 36

    entry = TemporalEntry(entry_id="exp_approx", interval=iv, weight=1.0)

    # min_months = 24: lo (14) < 24 <= hi (36)
    res = calculate_weighted_union([entry], min_months=24)
    assert res.months_lo == 14.0
    assert res.months_hi == 36.0
    assert res.state == "PARTIAL"
    assert "DATE_UNCERTAIN" in res.flags


def test_recency_window_filtering():
    """Verify recency window clips or filters older experiences."""
    # as_of = 2026-10 (month 24322)
    # 24 months recency window = [24322 - 24 + 1, 24322] = [24299, 24322] (from Nov 2024 to Oct 2026)
    as_of = (2026, 10)

    # Old job: 2020-01 to 2021-12 (completely outside recency window)
    old_entry = TemporalEntry(entry_id="old", interval=(24241, 24264), weight=1.0)
    # Recent job: 2025-01 to 2026-06 (completely inside recency window, 18 months)
    recent_entry = TemporalEntry(
        entry_id="recent",
        interval=(ym_to_abs_month(2025, 1), ym_to_abs_month(2026, 6)),
        weight=1.0,
    )

    policy = DurationPolicy(recency_window_months=24)
    res = calculate_weighted_union([old_entry, recent_entry], policy=policy, as_of=as_of)
    assert res.months_hi == 18.0
    assert all(row["contributing_entry"] == "recent" for row in res.month_ledger)


# =========================================================================
# Hypothesis Property-Based Tests
# =========================================================================


@st.composite
def temporal_entry_strategy(draw):
    """Generate arbitrary valid temporal entries for property testing."""
    start_m = draw(st.integers(min_value=24000, max_value=24500))
    duration = draw(st.integers(min_value=1, max_value=60))
    end_m = start_m + duration - 1
    weight = draw(st.sampled_from([0.0, 0.5, 0.75, 1.0]))
    entry_id = draw(st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnopqrstuvwxyz0123456789"))
    return TemporalEntry(entry_id=entry_id, interval=(start_m, end_m), weight=weight)


@settings(max_examples=100)
@given(st.lists(temporal_entry_strategy(), min_size=1, max_size=15))
def test_property_union_le_sum_durations(entries):
    """Property 1: Weighted calendar union is always <= sum of individual weighted durations."""
    res = calculate_weighted_union(entries)
    sum_individual = sum(
        (e.interval[1] - e.interval[0] + 1) * e.weight  # type: ignore[index]
        for e in entries
        if e.interval[0] <= e.interval[1]  # type: ignore[index]
    )
    assert res.months_hi <= round(sum_individual, 2) + 1e-4


@settings(max_examples=100)
@given(st.lists(temporal_entry_strategy(), min_size=1, max_size=15))
def test_property_lo_le_hi(entries):
    """Property 2: months_lo is always <= months_hi."""
    res = calculate_weighted_union(entries)
    assert res.months_lo <= res.months_hi + 1e-4


@settings(max_examples=50)
@given(st.lists(temporal_entry_strategy(), min_size=2, max_size=10))
def test_property_order_invariance(entries):
    """Property 3: Order invariance - shuffling entries produces identical duration."""
    res_original = calculate_weighted_union(entries)

    shuffled = list(entries)
    random.shuffle(shuffled)
    res_shuffled = calculate_weighted_union(shuffled)

    assert res_original.months_hi == res_shuffled.months_hi
    assert res_original.months_lo == res_shuffled.months_lo
    assert len(res_original.month_ledger) == len(res_shuffled.month_ledger)


@settings(max_examples=50)
@given(st.lists(temporal_entry_strategy(), min_size=1, max_size=8))
def test_property_zero_weight_entries_have_no_effect(entries):
    """Property 4: Adding zero-weight entries does not affect months or ledger."""
    res_base = calculate_weighted_union(entries)

    zero_entry = TemporalEntry(
        entry_id="zero_weight",
        interval=(24100, 24200),
        weight=0.0,
    )
    res_with_zero = calculate_weighted_union(entries + [zero_entry])

    assert res_base.months_hi == res_with_zero.months_hi
    assert res_base.months_lo == res_with_zero.months_lo
    assert len(res_base.month_ledger) == len(res_with_zero.month_ledger)


@settings(max_examples=50)
@given(st.lists(temporal_entry_strategy(), min_size=1, max_size=8))
def test_property_duplicate_entries_do_not_increase_duration(entries):
    """Property 5: Duplicate entries (max over active weights) do not increase months."""
    res_base = calculate_weighted_union(entries)

    # Duplicate each entry exactly
    duplicates = [TemporalEntry(entry_id=f"dup_{e.entry_id}", interval=e.interval, weight=e.weight) for e in entries]
    res_duplicated = calculate_weighted_union(entries + duplicates)

    assert res_base.months_hi == res_duplicated.months_hi
    assert res_base.months_lo == res_duplicated.months_lo
