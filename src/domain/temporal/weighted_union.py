"""Weighted calendar union temporal engine for CV screening.

Implements the O(N log N) sweep-line algorithm for weighted calendar union
per domain:
    months_d = sum_{m in active_months} max_{e active in m} w(e, d)

Prevents double-counting across overlapping jobs while allowing parallel
contributions across different domains (e.g. Frontend and Backend).
Produces month-by-month transparency ledgers for UI inspection.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sortedcontainers import SortedList

from src.domain.temporal.date_normalizer import (
    Interval,
    _resolve_as_of,
    abs_month_to_str,
    ym_to_abs_month,
)

DEFAULT_ALLOC_WEIGHTS: dict[str, float] = {
    "PRIMARY": 1.0,
    "SECONDARY": 0.5,
    "INCIDENTAL": 0.0,
}

DEFAULT_EMP_WEIGHTS: dict[str, float] = {
    "full-time": 1.0,
    "full_time": 1.0,
    "kontrak": 1.0,
    "contract": 1.0,
    "permanent": 1.0,
    "part-time": 0.5,
    "part_time": 0.5,
    "magang": 0.5,
    "internship": 0.5,
    "intern": 0.5,
    "freelance": 0.75,
    "unknown": 1.0,
}


@dataclass
class DurationPolicy:
    """Configurable duration weighting policy per requirement set."""

    alloc_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_ALLOC_WEIGHTS))
    emp_weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_EMP_WEIGHTS))
    recency_window_months: int | None = None


def compute_entry_weight(
    allocation_level: str | None = "PRIMARY",
    employment_type: str | None = "full-time",
    policy: DurationPolicy | None = None,
) -> tuple[float, list[str]]:
    """Compute w(e, d) = alloc[level(e, d)] * emp[type(e)].

    Returns (weight, flags).
    """
    p = policy or DurationPolicy()
    flags: list[str] = []

    alloc_key = (allocation_level or "PRIMARY").strip().upper()
    alloc_w = p.alloc_weights.get(alloc_key, 1.0)

    emp_raw = (employment_type or "unknown").strip().lower()
    if emp_raw in p.emp_weights:
        emp_w = p.emp_weights[emp_raw]
    else:
        emp_w = p.emp_weights.get("unknown", 1.0)
        flags.append("EMPLOYMENT_TYPE_UNKNOWN")

    return round(alloc_w * emp_w, 4), flags


@dataclass
class TemporalEntry:
    """An experience entry with temporal interval and domain weights."""

    entry_id: str
    interval: Interval | tuple[int, int]
    weight: float = 1.0
    domain_weights: dict[str, float] = field(default_factory=dict)
    role_title: str | None = None
    employment_type: str | None = None
    allocation_level: str | None = None

    def get_weight(
        self,
        domain: str | None = None,
        policy: DurationPolicy | None = None,
    ) -> float:
        """Resolve weight for a target domain."""
        if domain and domain in self.domain_weights:
            return self.domain_weights[domain]
        if self.allocation_level or self.employment_type:
            w, _ = compute_entry_weight(
                allocation_level=self.allocation_level,
                employment_type=self.employment_type,
                policy=policy,
            )
            return w
        return self.weight


@dataclass
class WeightedUnionResult:
    """Result of weighted calendar union evaluation."""

    months_lo: float
    months_hi: float
    month_ledger: list[dict[str, Any]]
    ledger_lo: list[dict[str, Any]] = field(default_factory=list)
    state: str = "NOT_DEMONSTRATED"
    flags: list[str] = field(default_factory=list)

    @property
    def total_months(self) -> float:
        """Alias for optimistic duration months_hi."""
        return self.months_hi

    @property
    def months_d(self) -> float:
        """Blueprint alias for calculated domain months."""
        return self.months_hi


def weighted_calendar_union_sweep_line(
    intervals: Sequence[tuple[int, int, float, str]],
    recency_window: tuple[int, int] | None = None,
) -> tuple[float, list[dict[str, Any]]]:
    """Sweep-line O(N log N) weighted calendar union algorithm.

    Given a list of (start_month, end_month, weight, entry_id) in absolute
    calendar months:
        months_d = sum_{month m} max_{e active in m} w(e, d)

    Args:
        intervals: Sequence of (start_month, end_month, weight, entry_id).
        recency_window: Optional (start_bound, end_bound) to clip intervals.

    Returns:
        (total_months, month_ledger) where month_ledger is a list of
        {'month': 'YYYY-MM', 'contributing_entry': str, 'weight': float}.
    """
    if not intervals:
        return 0.0, []

    events: dict[int, list[tuple[str, float, str, int]]] = defaultdict(list)

    for idx, (s, e, w, entry_id) in enumerate(intervals):
        if w <= 0.0:
            continue
        cur_s, cur_e = s, e
        if recency_window:
            r_start, r_end = recency_window
            cur_s = max(cur_s, r_start)
            cur_e = min(cur_e, r_end)

        if cur_s > cur_e:
            continue

        # Add event at start month cur_s
        events[cur_s].append(("ADD", w, entry_id, idx))
        # Remove event after end month cur_e (i.e. at cur_e + 1)
        events[cur_e + 1].append(("REMOVE", w, entry_id, idx))

    if not events:
        return 0.0, []

    sorted_points = sorted(events.keys())

    # Active container stores (weight, entry_id, idx)
    # Highest weight wins; ties broken deterministically by entry_id, then idx
    active: SortedList = SortedList()

    total_months = 0.0
    ledger: list[dict[str, Any]] = []

    for i in range(len(sorted_points) - 1):
        cur_m = sorted_points[i]
        next_m = sorted_points[i + 1]

        # Apply events at cur_m
        for action, w, entry_id, idx in events[cur_m]:
            item = (w, entry_id, idx)
            if action == "ADD":
                active.add(item)
            elif action == "REMOVE":
                active.remove(item)

        if active:
            max_w, best_entry, _ = active[-1]
            if max_w > 0:
                span_len = next_m - cur_m
                total_months += max_w * span_len

                for m in range(cur_m, next_m):
                    ledger.append(
                        {
                            "month": abs_month_to_str(m),
                            "contributing_entry": best_entry,
                            "weight": round(max_w, 4),
                        }
                    )

    return round(total_months, 2), ledger


def evaluate_duration_state(
    months_lo: float,
    months_hi: float,
    min_months: float,
) -> tuple[str, list[str]]:
    """Determine state (STRONG, PARTIAL, NOT_DEMONSTRATED) and flags per Blueprint §C4.

    lo >= min            -> STRONG
    hi < min             -> PARTIAL (>0) / NOT_DEMONSTRATED (0)
    lo < min <= hi       -> PARTIAL + DATE_UNCERTAIN (escalation E5)
    """
    flags: list[str] = []
    if months_lo >= min_months:
        return "STRONG", flags
    if months_hi < min_months:
        state = "PARTIAL" if months_hi > 0 else "NOT_DEMONSTRATED"
        return state, flags

    # months_lo < min_months <= months_hi
    flags.append("DATE_UNCERTAIN")
    return "PARTIAL", flags


def calculate_weighted_union(
    entries: Sequence[TemporalEntry],
    domain: str | None = None,
    min_months: float | None = None,
    policy: DurationPolicy | None = None,
    as_of: str | date | tuple[int, int] | None = None,
) -> WeightedUnionResult:
    """Calculate pessimistic and optimistic weighted calendar union for a given domain.

    Args:
        entries: Sequence of candidate's temporal experience entries.
        domain: Target skill / role domain (e.g. 'backend', 'frontend').
        min_months: Requirement threshold for duration gating.
        policy: Duration weighting policy (allocations, employment types, recency).
        as_of: Evaluation reference date.

    Returns:
        WeightedUnionResult containing months_lo, months_hi, month_ledger,
        state, and flags.
    """
    p = policy or DurationPolicy()
    recency_window: tuple[int, int] | None = None
    if p.recency_window_months and p.recency_window_months > 0:
        as_of_y, as_of_m = _resolve_as_of(as_of)
        as_of_abs = ym_to_abs_month(as_of_y, as_of_m)
        recency_window = (as_of_abs - p.recency_window_months + 1, as_of_abs)

    opt_intervals: list[tuple[int, int, float, str]] = []
    pess_intervals: list[tuple[int, int, float, str]] = []
    flags: list[str] = []

    for entry in entries:
        w = entry.get_weight(domain=domain, policy=p)

        if isinstance(entry.interval, Interval):
            if not entry.interval.is_valid:
                # Discard invalid anomalies
                for f in entry.interval.flags:
                    if f not in flags:
                        flags.append(f)
                continue

            for f in entry.interval.flags:
                if f not in flags:
                    flags.append(f)

            opt_r = entry.interval.optimistic_range
            if opt_r:
                opt_intervals.append((opt_r[0], opt_r[1], w, entry.entry_id))

            pess_r = entry.interval.pessimistic_range
            if pess_r:
                pess_intervals.append((pess_r[0], pess_r[1], w, entry.entry_id))
        elif isinstance(entry.interval, tuple) and len(entry.interval) == 2:
            s, e = entry.interval
            if s <= e:
                opt_intervals.append((s, e, w, entry.entry_id))
                pess_intervals.append((s, e, w, entry.entry_id))

    months_hi, ledger_hi = weighted_calendar_union_sweep_line(opt_intervals, recency_window=recency_window)
    months_lo, ledger_lo = weighted_calendar_union_sweep_line(pess_intervals, recency_window=recency_window)

    state = "NOT_DEMONSTRATED"
    if min_months is not None:
        state, state_flags = evaluate_duration_state(months_lo, months_hi, min_months)
        for sf in state_flags:
            if sf not in flags:
                flags.append(sf)
    else:
        if months_lo > 0:
            state = "STRONG"
        elif months_hi > 0:
            state = "PARTIAL"

    return WeightedUnionResult(
        months_lo=months_lo,
        months_hi=months_hi,
        month_ledger=ledger_hi,
        ledger_lo=ledger_lo,
        state=state,
        flags=flags,
    )


def calculate_multidomain_weighted_union(
    entries: Sequence[TemporalEntry],
    domains: Sequence[str] | None = None,
    min_months_per_domain: dict[str, float] | None = None,
    policy: DurationPolicy | None = None,
    as_of: str | date | tuple[int, int] | None = None,
) -> dict[str, WeightedUnionResult]:
    """Calculate weighted calendar union across multiple domains."""
    min_map = min_months_per_domain or {}
    if not domains:
        domain_set: set[str] = set()
        for e in entries:
            domain_set.update(e.domain_weights.keys())
        target_domains = sorted(domain_set) if domain_set else ["backend"]
    else:
        target_domains = list(domains)

    results: dict[str, WeightedUnionResult] = {}
    for d in target_domains:
        min_m = min_map.get(d)
        results[d] = calculate_weighted_union(
            entries=entries,
            domain=d,
            min_months=min_m,
            policy=policy,
            as_of=as_of,
        )
    return results
