"""Temporal Engine module for CV Screening.

Provides date normalization, absolute month algebra, and sweep-line
weighted calendar union for accurate, transparent duration calculations.
"""

from src.domain.temporal.date_normalizer import (
    Interval,
    abs_month_to_str,
    abs_month_to_ym,
    normalize_date_range,
    normalize_date_text,
    parse_single_date,
    ym_to_abs_month,
)
from src.domain.temporal.weighted_union import (
    DurationPolicy,
    TemporalEntry,
    WeightedUnionResult,
    calculate_multidomain_weighted_union,
    calculate_weighted_union,
    compute_entry_weight,
    evaluate_duration_state,
    weighted_calendar_union_sweep_line,
)

__all__ = [
    "DurationPolicy",
    "Interval",
    "TemporalEntry",
    "WeightedUnionResult",
    "abs_month_to_str",
    "abs_month_to_ym",
    "calculate_multidomain_weighted_union",
    "calculate_weighted_union",
    "compute_entry_weight",
    "evaluate_duration_state",
    "normalize_date_range",
    "normalize_date_text",
    "parse_single_date",
    "weighted_calendar_union_sweep_line",
    "ym_to_abs_month",
]
