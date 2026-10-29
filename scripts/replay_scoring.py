#!/usr/bin/env python3
"""Offline replay of aggregation + scoring on a stored run (no LLM, no database).

    PYTHONPATH=. python scripts/replay_scoring.py --rankings rankings.json --requirements requirements.json \
        --out replay_export.json [--legacy] [--narrow-with-stored-judgments]

Reads the stored facet judgments of a finished run and re-runs requirement aggregation and Scorer v2 with the
current code. Use it to see what a scoring change does to bands and ranks before spending any tokens.

--legacy      reproduce v2.1 behaviour (AGENT_DISAGREEMENT forces Band R): fidelity check against the original run.
--stored-states  keep the requirement states stored by the run and only re-apply Scorer v2 (isolates scoring rules).
                 Without it, states are re-aggregated from the stored (post-Critic) facet judgments for *every*
                 requirement that uses a facet, which is what v2.2 does and v2.1 did not (see note below).

Note: v2.1 re-aggregated a Critic downgrade only for the last requirement that used the facet, so with five shared
facets the stored states are internally inconsistent (some requirements keep the pre-Critic state). Re-aggregating
correctly while every requirement still shares the same five facets sinks *all* criteria together, which is why
facets per requirement must ship together with the propagation fix.
The output has the eval-export shape, so `run_eval.py --run replay_export.json ...` can score it.

Limits: facet judgments are the ones stored by the original run. Changes to *which facets exist per requirement*
cannot be replayed (the new facets were never judged); they need a live run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.domain.interview.probe import rescore  # noqa: E402
from src.domain.requirements.facet_templates import ROLE_FACET_TEMPLATES  # noqa: E402
from src.domain.scoring.scorer_v2 import rank_v2  # noqa: E402
from src.infrastructure.config import settings  # noqa: E402

MIN_MONTHS_RE = {"R1": 24.0}


def _requirement_set(reqs: list[dict[str, Any]], template: str = "backend") -> dict[str, Any]:
    """The stored job requirements, each with the facets v2.1 assigned (the full role template)."""
    out = []
    for r in reqs:
        facets = [dict(t) for t in ROLE_FACET_TEMPLATES[template]]
        policy = None
        if (r.get("kind") or "").upper() == "EXPERIENCE_DURATION":
            policy = {"min_months": MIN_MONTHS_RE.get(r["requirement_id"], 24.0)}
        out.append(
            {
                "requirement_id": r["requirement_id"],
                "description": r.get("description", ""),
                "category": r.get("category", "HARD_SKILLS"),
                "kind": r.get("kind", "SKILL"),
                "importance": r.get("importance", "MUST_HAVE"),
                "weight": float(r.get("weight", 10.0)),
                "target_domains": ["general"] if policy else [],
                "duration_policy": policy,
                "facets": facets,
            }
        )
    return {"category_weights": {}, "requirements": out}


def replay(rankings: dict[str, Any], reqs: list[dict[str, Any]], stored_states: bool = False) -> dict[str, Any]:
    req_set = _requirement_set(reqs)
    scored = []
    for row in rankings["rankings"]:
        judgments, seen = [], set()
        for j in row.get("facet_judgments", []):
            if j["facet_key"] not in seen:
                seen.add(j["facet_key"])
                judgments.append(dict(j, support_atoms=j.get("support_atom_ids") or []))
        result, states = rescore(req_set, judgments, row.get("domain_durations"), list(row.get("flags") or []))
        if stored_states:
            from src.domain.scoring.scorer_v2 import score_v2

            states = dict(row.get("requirement_states") or states)
            result = score_v2(
                states=states,
                requirement_set=req_set,
                facet_judgments=[dict(j, support_atoms=j.get("support_atom_ids") or []) for j in judgments],
                flags=list(row.get("flags") or []),
                apply_depth=settings.SCORER_DEPTH_FACTORS_ENABLED,
            )
        scored.append(
            {
                "row": row,
                "result": result,
                "states": states,
                "candidate_id": str(row["candidate_id"]),
                "strong_count": sum(s == "STRONG" for s in states.values()),
            }
        )
    ranked = rank_v2(scored, run_id="replay")
    results = []
    for i, item in enumerate(ranked, 1):
        r, row = item["result"], item["row"]
        results.append(
            {
                "file": row["file_name"],
                "status": "SCORED",
                "rank": i,
                "band": r.band,
                "score": r.final_score,
                "raw_score": r.raw_score,
                "recommendation": r.recommendation,
                "requirement_states": item["states"],
                "flags": sorted(r.flags),
                "score_lo": r.score_lo,
                "score_hi": r.score_hi,
            }
        )
    return {
        "job_id": "replay",
        "run_id": rankings.get("screening_run_id", "replay"),
        "as_of": "replay",
        "results": results,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rankings", required=True)
    ap.add_argument("--requirements", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--legacy", action="store_true")
    ap.add_argument("--stored-states", action="store_true")
    args = ap.parse_args()
    settings.AGENT_DISAGREEMENT_FORCES_BAND_R = bool(args.legacy)
    rankings = json.loads(Path(args.rankings).read_text(encoding="utf-8"))
    reqs = json.loads(Path(args.requirements).read_text(encoding="utf-8"))
    export = replay(rankings, reqs, stored_states=args.stored_states)
    Path(args.out).write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")
    bands: dict[str, int] = {}
    for r in export["results"]:
        bands[r["band"]] = bands.get(r["band"], 0) + 1
    print(f"replayed {len(export['results'])} candidates, bands: {bands}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
