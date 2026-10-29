"""Model-change gate for fairness.

Bias direction can flip between model generations, so a change to any configured model must be followed by a
live counterfactual run (`scripts/run_live_fairness.py`) that records the models it exercised. This test fails
when the recorded report does not match the models now configured, or recorded any flip.

Skipped until the first live report exists (docs/eval/fairness_last_run.json).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.infrastructure.config import settings

REPORT = Path(__file__).resolve().parents[2] / "docs" / "eval" / "fairness_last_run.json"
MODEL_FIELDS = (
    "LLM_MODEL_PROFILER",
    "LLM_MODEL_MATCHER",
    "LLM_MODEL_CRITIC",
    "LLM_MODEL_JD_COMPILER",
    "LLM_MODEL_VERIFIER",
)


def _report() -> dict:
    if not REPORT.exists():
        pytest.skip("no live fairness report yet: run scripts/run_live_fairness.py")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_report_covers_the_configured_models():
    report = _report()
    current = {f: getattr(settings, f) for f in MODEL_FIELDS}
    assert report["models"] == current, (
        "A configured model changed since the last live fairness run. "
        "Re-run scripts/run_live_fairness.py and commit docs/eval/fairness_last_run.json."
    )


def test_report_recorded_no_counterfactual_flips():
    report = _report()
    assert report["flip_count"] == 0, report.get("flips")
