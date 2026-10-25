#!/usr/bin/env python3
"""Concurrency and load test executing 5 parallel screening runs over 300 candidates (M6)."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path

from src.domain.kind_rules import (
    eval_achievement,
    eval_certification,
    eval_education,
    eval_experience_duration,
    eval_leadership,
    eval_responsibility,
    eval_skill,
)
from src.domain.scorer import score, rank
from src.worker.adapter import extract_candidate_profile
from src.worker.redaction import extract_identity_and_redact

CORE_DIR = Path("docs/spec/golden_dataset/cvs/core")
JD1_PATH = Path("docs/spec/golden_dataset/job_descriptions/JD-01_requirements.approved.json")


def evaluate_single_candidate(matching_prof: dict, req_set: dict) -> tuple[dict, any]:
    states_map = {}
    for r in req_set["requirements"]:
        kind = r["kind"]
        rid = r["requirement_id"]
        if kind == "EXPERIENCE_DURATION":
            st, _, _, _, _ = eval_experience_duration(matching_prof, r)
        elif kind == "SKILL":
            st, _, _, _, _ = eval_skill(matching_prof, r)
        elif kind == "RESPONSIBILITY":
            st, _, _, _, _ = eval_responsibility(matching_prof, r)
        elif kind == "EDUCATION":
            st, _, _, _, _ = eval_education(matching_prof, r)
        elif kind == "CERTIFICATION":
            st, _, _, _, _ = eval_certification(matching_prof, r)
        elif kind == "ACHIEVEMENT":
            st, _, _, _, _ = eval_achievement(matching_prof, r)
        elif kind == "LEADERSHIP":
            st, _, _, _, _ = eval_leadership(matching_prof, r)
        else:
            st = "NOT_DEMONSTRATED"
        states_map[rid] = st

    s_res = score(states_map, req_set)
    return states_map, s_res


def run_screening_iteration(run_idx: int, req_set: dict, candidates_pool: list[dict]) -> dict:
    t0 = time.time()
    scoring_payload = []
    for c in candidates_pool:
        _, s_res = evaluate_single_candidate(c["matching"], req_set)
        scoring_payload.append({
            "candidate_id": c["id"],
            "file": c["file"],
            "result": s_res,
            "strong_count": 5,
        })

    ranked = rank(scoring_payload, run_id=f"parallel_run_{run_idx}")
    elapsed = time.time() - t0
    return {
        "run_idx": run_idx,
        "candidates_scored": len(ranked),
        "top_1": ranked[0]["candidate_id"],
        "top_1_score": ranked[0]["result"].final_score,
        "elapsed_seconds": elapsed,
    }


async def main():
    print("=== M6 LOAD TEST: 300 KANDIDAT × 5 SCREENING RUNS PARALEL ===")

    # 1. Prepare 300 parsed candidates in memory
    core_files = sorted(list(CORE_DIR.glob("*.pdf")) + list(CORE_DIR.glob("*.docx")))
    print(f"Pre-parsing 15 core CVs and building 300 candidates pool...")

    parsed_15 = []
    for f in core_files:
        prof = extract_candidate_profile(f.read_bytes(), f.name)
        _, matching, _ = extract_identity_and_redact(prof)
        parsed_15.append({"file": f.name, "matching": matching})

    pool_300 = []
    for i in range(300):
        src = parsed_15[i % len(parsed_15)]
        pool_300.append({
            "id": f"CAND_{i:04d}_{src['file'][:4]}",
            "file": f"CV_{i:04d}_{src['file']}",
            "matching": src["matching"],
        })

    print(f"Pool size: {len(pool_300)} candidates ready in memory.")

    req_set = json.loads(JD1_PATH.read_text())

    # 2. Launch 5 parallel screening runs simultaneously
    print("Launching 5 concurrent screening runs in parallel threads...")
    t_global_start = time.time()

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, run_screening_iteration, idx + 1, req_set, pool_300)
        for idx in range(5)
    ]

    results = await asyncio.gather(*tasks)
    total_time = time.time() - t_global_start

    print("\n=== HASIL LOAD TEST PARALEL ===")
    for res in results:
        print(f"Run #{res['run_idx']}: Scored {res['candidates_scored']} candidates in {res['elapsed_seconds']:.3f}s | Top: {res['top_1']} (Skor {res['top_1_score']:.1f})")

    avg_time = sum(r["elapsed_seconds"] for r in results) / len(results)
    throughput = (300 * 5) / total_time

    print(f"\nWaktu Total 5 Run Paralel : {total_time:.3f} detik")
    print(f"Rata-rata Waktu per Run  : {avg_time:.3f} detik (Target < 10 detik)")
    print(f"Throughput Scoring Total  : {throughput:.1f} evaluasi kandidat / detik")
    print(f"Status Target             : {'LULUS' if avg_time < 10.0 else 'GAGAL'}\n")

    report_payload = {
        "parallel_runs": 5,
        "candidates_per_run": 300,
        "total_evaluations": 1500,
        "total_wall_time_s": total_time,
        "avg_run_latency_s": avg_time,
        "throughput_eval_per_sec": throughput,
        "status": "PASS" if avg_time < 10.0 else "FAIL",
    }
    Path("scripts/eval_runs/load_test_report.json").write_text(json.dumps(report_payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
