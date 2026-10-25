"""Scoring domain module (v2.1)."""

from src.domain.scoring.scorer_v2 import (
    BAND_CAP,
    BAND_ORDER,
    DEFAULT_DEPTH_FACTORS,
    MAX_SUPPORTING_ATOMS_PER_FACET,
    ScoreResultV2,
    cap_supporting_atoms,
    is_t0_evidence,
    rank_v2,
    score_v2,
    tie_break_key,
)

__all__ = [
    "BAND_CAP",
    "BAND_ORDER",
    "DEFAULT_DEPTH_FACTORS",
    "MAX_SUPPORTING_ATOMS_PER_FACET",
    "ScoreResultV2",
    "cap_supporting_atoms",
    "is_t0_evidence",
    "rank_v2",
    "score_v2",
    "tie_break_key",
]
