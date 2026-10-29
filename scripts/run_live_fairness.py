#!/usr/bin/env python3
"""Live counterfactual fairness run against the real Matcher/Critic models (synthetic CV only).

    PYTHONPATH=. python scripts/run_live_fairness.py            # needs LLM_GATEWAY_KEY in the environment/.env

Runs the same CV with gender / religion / age / marital status / campus / address swapped, through the real
gateway, and writes docs/eval/fairness_last_run.json with the models exercised and the flips found.
Exit code 1 if any variant changes an outcome. Uses synthetic data only (never real applicant CVs).
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.domain.atoms import EvidenceAtom  # noqa: E402
from src.domain.pipeline import CandidateInput, run_screening_pipeline  # noqa: E402
from src.domain.requirements.schemas import RequirementFacet, RequirementIR, RequirementSetIR  # noqa: E402
from src.infrastructure.config import settings  # noqa: E402
from tests.fairness.test_counterfactual_invariance import EVIDENCE, FORBIDDEN, VARIANTS  # noqa: E402
from tests.fairness.test_live_model_gate import MODEL_FIELDS, REPORT  # noqa: E402

FACETS = [
    ("X1", "merancang dan mengimplementasikan REST API"),
    ("X2", "pengelolaan database dan optimasi query"),
    ("X3", "automated testing dan CI untuk layanan backend"),
]


def _atoms(variant: dict[str, str]) -> list[EvidenceAtom]:
    rows = list(EVIDENCE) + [
        ("S1", "summary_sentence", variant["summary"]),
        ("ED1", "education", variant["education"]),
        ("K1", "skill_list_item", variant["extra"]),
    ]
    atoms, pos = [], 0
    for key, kind, text in rows:
        atoms.append(EvidenceAtom(key, kind, "exp_1", 1, pos, pos + len(text), pos, pos + len(text), text))
        pos += len(text) + 1
    return atoms


def _req_set() -> RequirementSetIR:
    facets = [RequirementFacet(facet_key=k, hypothesis=h, core=True) for k, h in FACETS]
    req = RequirementIR(
        requirement_id="R1",
        description="Kemampuan backend",
        kind="ROLE_EQUIVALENCE",
        importance="MUST_HAVE",
        weight=100.0,
        facets=facets,
    )
    return RequirementSetIR(job_title="Backend", requirements=[req])


async def _run(name: str) -> dict:
    res = await run_screening_pipeline(
        candidates=[CandidateInput(candidate_id=uuid.UUID(int=1), atoms=_atoms(VARIANTS[name]), raw_title="Engineer")],
        requirement_set=_req_set(),
        run_id=uuid.UUID(int=2),
        tenant_id=uuid.UUID(int=3),
    )
    c = res.top_candidate
    return {
        "band": c.band,
        "recommendation": c.recommendation,
        "score": c.final_score,
        "states": {k: v.state.value for k, v in c.requirement_results.items()},
    }


async def main() -> int:
    if not settings.LLM_GATEWAY_KEY:
        print("LLM_GATEWAY_KEY is not set; cannot run the live fairness suite.", file=sys.stderr)
        return 2
    outcomes = {name: await _run(name) for name in VARIANTS}
    base = outcomes["base"]
    flips = [
        {"variant": n, "base": base, "variant_outcome": o}
        for n, o in outcomes.items()
        if n != "base"
        and (o["band"], o["recommendation"], o["states"]) != (base["band"], base["recommendation"], base["states"])
    ]
    report = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "suite": "counterfactual-live-v1",
        "models": {f: getattr(settings, f) for f in MODEL_FIELDS},
        "attributes_checked": FORBIDDEN,
        "outcomes": outcomes,
        "flip_count": len(flips),
        "flips": flips,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if flips else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
