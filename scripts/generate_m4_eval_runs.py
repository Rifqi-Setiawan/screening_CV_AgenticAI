"""Generates golden dataset evaluation runs for evaluate.py (--jd01, --jd02, --edge, --repeat)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
from src.domain.verifier import verify_requirement_with_llm
from src.worker.adapter import extract_candidate_profile
from src.worker.redaction import extract_identity_and_redact
from src.worker.sanitizer import sanitize_file

CORE_DIR = Path("docs/spec/golden_dataset/cvs/core")
EDGE_DIR = Path("docs/spec/golden_dataset/cvs/edge")
JD1_PATH = Path("docs/spec/golden_dataset/job_descriptions/JD-01_requirements.approved.json")
JD2_PATH = Path("docs/spec/golden_dataset/job_descriptions/JD-02_requirements.approved.json")


def evaluate_cv(
    file_path: Path,
    req_set: dict[str, Any],
    as_of: str = "2026-10-01",
    use_verifier: bool = False,
    existing_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    file_bytes = file_path.read_bytes()
    file_name = file_path.name

    # 1. Sanitize
    san_res = sanitize_file(file_bytes, file_name)

    import hashlib
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    flags = list(san_res.flags)
    reasons = list(san_res.reasons)
    status_val = san_res.status
    duplicate_of = None

    if existing_hashes and file_hash in existing_hashes:
        status_val = "DUPLICATE"
        duplicate_of = existing_hashes[file_hash]

    if status_val in ("REJECTED", "NEEDS_REVIEW", "DUPLICATE"):
        return {
            "file": file_name,
            "status": status_val,
            "rank": 999,
            "band": "R",
            "score": 0.0,
            "raw_score": 0.0,
            "recommendation": "MANUAL_CHECK",
            "requirement_states": {},
            "metrics": {},
            "flags": flags,
            "reasons": reasons,
            "duplicate_of": duplicate_of,
        }

    # 2. Extract profile & redact
    raw_prof = extract_candidate_profile(file_bytes, file_name)
    _, matching, chunks = extract_identity_and_redact(raw_prof)
    full_text = " ".join(c.get("text_redacted", "") for c in chunks)

    # 3. Evaluate requirements
    states_map: dict[str, str] = {}
    metrics_map: dict[str, Any] = {}
    ev_map: dict[str, list[dict[str, Any]]] = {}

    for r in req_set.get("requirements", []):
        rid = r["requirement_id"]
        kind = r["kind"]
        if kind == "EXPERIENCE_DURATION":
            st, conf, m, evs, flgs = eval_experience_duration(matching, r, as_of=as_of)
            metrics_map.update(m)
        elif kind == "SKILL":
            st, conf, m, evs, flgs = eval_skill(matching, r)
        elif kind == "RESPONSIBILITY":
            st, conf, m, evs, flgs = eval_responsibility(matching, r)
        elif kind == "EDUCATION":
            st, conf, m, evs, flgs = eval_education(matching, r)
        elif kind == "CERTIFICATION":
            st, conf, m, evs, flgs = eval_certification(matching, r)
        elif kind == "ACHIEVEMENT":
            st, conf, m, evs, flgs = eval_achievement(matching, r)
        elif kind == "LEADERSHIP":
            st, conf, m, evs, flgs = eval_leadership(matching, r)
        else:
            st, conf, m, evs, flgs = "NOT_DEMONSTRATED", 0.9, {}, [], []

        flags.extend(flgs)

        # Optional LLM verifier via 9Router for ambiguous criteria
        if use_verifier and kind in ("RESPONSIBILITY", "ACHIEVEMENT", "LEADERSHIP") and st in ("PARTIAL", "STRONG") and evs:
            v_st, v_quote, v_flgs = verify_requirement_with_llm(
                full_text, r, st, [e.get("quote", "") for e in evs]
            )
            st = v_st
            flags.extend(v_flgs)

        states_map[rid] = st
        ev_map[rid] = evs

    s_res = score(states_map, req_set)
    strong_count = sum(1 for v in states_map.values() if v == "STRONG")

    return {
        "file": file_name,
        "status": "SCORED",
        "band": s_res.band,
        "score": s_res.final_score,
        "raw_score": s_res.raw_score,
        "recommendation": s_res.recommendation,
        "requirement_states": states_map,
        "metrics": metrics_map,
        "flags": sorted(list(set(flags))),
        "reasons": sorted(list(set(reasons))),
        "result_obj": s_res,
        "strong_count": strong_count,
    }


def build_run(
    files: list[Path],
    req_set_path: Path,
    job_code: str,
    run_id: str,
    as_of: str = "2026-10-01",
    use_verifier: bool = False,
    existing_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    req_set = json.loads(req_set_path.read_text())
    evaluated = []

    for f in sorted(files):
        item = evaluate_cv(f, req_set, as_of=as_of, use_verifier=use_verifier, existing_hashes=existing_hashes)
        evaluated.append(item)

    # Rank scored items
    scored_items = [it for it in evaluated if it["status"] == "SCORED"]
    scoring_payload = []
    for it in scored_items:
        scoring_payload.append({
            "candidate_id": it["file"].split("_")[0],
            "file": it["file"],
            "result": it["result_obj"],
            "strong_count": it["strong_count"],
        })

    ranked_scored = rank(scoring_payload, run_id=job_code)
    rank_map = {it["file"]: idx + 1 for idx, it in enumerate(ranked_scored)}

    final_results = []
    for it in evaluated:
        clean_it = {k: v for k, v in it.items() if k not in ("result_obj", "strong_count")}
        if clean_it["status"] == "SCORED":
            clean_it["rank"] = rank_map[clean_it["file"]]
        else:
            clean_it["rank"] = 999
        final_results.append(clean_it)

    return {
        "job_id": job_code,
        "run_id": run_id,
        "as_of": as_of,
        "results": final_results,
    }


def main():
    core_files = sorted(list(CORE_DIR.glob("*.pdf")) + list(CORE_DIR.glob("*.docx")))
    edge_files = sorted(list(EDGE_DIR.glob("*.pdf")) + list(EDGE_DIR.glob("*.docx")))

    # Existing hashes for duplicate detection (S1 hash mapped to S1 filename)
    s1_file = CORE_DIR / "S1_senior_backend_id.pdf"
    import hashlib
    s1_hash = hashlib.sha256(s1_file.read_bytes()).hexdigest()
    hashes = {s1_hash: "S1_senior_backend_id.pdf"}

    out_dir = Path("scripts/eval_runs")
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. JD-01 without verifier
    print("Generating JD-01 run without verifier...")
    run_jd01_no_ver = build_run(core_files, JD1_PATH, "JD-01", "run_jd01_no_verifier", use_verifier=False)
    (out_dir / "run_jd01_no_verifier.json").write_text(json.dumps(run_jd01_no_ver, indent=2))

    # 2. JD-01 with verifier (9Router)
    print("Generating JD-01 run with verifier (9Router)...")
    run_jd01_ver = build_run(core_files, JD1_PATH, "JD-01", "run_jd01_verifier", use_verifier=True)
    (out_dir / "run_jd01_verifier.json").write_text(json.dumps(run_jd01_ver, indent=2))

    # 3. JD-01 repeat
    print("Generating JD-01 repeat run...")
    run_jd01_rep = build_run(core_files, JD1_PATH, "JD-01", "run_jd01_no_verifier_repeat", use_verifier=False)
    (out_dir / "run_jd01_repeat.json").write_text(json.dumps(run_jd01_rep, indent=2))

    # 4. JD-02
    print("Generating JD-02 run...")
    run_jd02 = build_run(core_files, JD2_PATH, "JD-02", "run_jd02", use_verifier=False)
    (out_dir / "run_jd02.json").write_text(json.dumps(run_jd02, indent=2))

    # 5. Edge cases (core + edge)
    print("Generating Edge cases run...")
    all_files = core_files + edge_files
    run_edge = build_run(all_files, JD1_PATH, "JD-01", "run_edge", existing_hashes=hashes)
    (out_dir / "run_edge.json").write_text(json.dumps(run_edge, indent=2))

    print("All evaluation runs generated in scripts/eval_runs/")


if __name__ == "__main__":
    main()
