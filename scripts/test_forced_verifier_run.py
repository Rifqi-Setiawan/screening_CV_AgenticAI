"""Forced LLM Verifier run on 15 core CVs for RESPONSIBILITY, ACHIEVEMENT, and LEADERSHIP."""
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
from src.domain.verifier import verify_requirement_with_llm
from src.worker.adapter import extract_candidate_profile
from src.worker.redaction import extract_identity_and_redact

CORE_DIR = Path("docs/spec/golden_dataset/cvs/core")
JD1_PATH = Path("docs/spec/golden_dataset/job_descriptions/JD-01_requirements.approved.json")
LABELS_PATH = Path("docs/spec/golden_dataset/labels/expected_JD-01.json")


def main():
    jd1 = json.loads(JD1_PATH.read_text())
    labels = json.loads(LABELS_PATH.read_text())
    cand_map = {c["file"].split("/")[-1]: c for c in labels["candidates"]}

    core_files = sorted(list(CORE_DIR.glob("*.pdf")) + list(CORE_DIR.glob("*.docx")))

    total_verifier_calls = 0
    verifier_calls_by_kind = {"RESPONSIBILITY": 0, "ACHIEVEMENT": 0, "LEADERSHIP": 0}
    changed_results = []
    grounding_fails = 0

    rule_states_all = {}
    verifier_states_all = {}

    print(f"Running forced LLM verifier evaluation across {len(core_files)} core CVs...")

    for idx, f in enumerate(core_files, 1):
        prof = extract_candidate_profile(f.read_bytes(), f.name)
        _, matching, chunks = extract_identity_and_redact(prof)
        full_text = " ".join(c.get("text_redacted", "") for c in chunks)

        rule_st = {}
        ver_st = {}

        for r in jd1["requirements"]:
            rid = r["requirement_id"]
            kind = r["kind"]
            if kind == "EXPERIENCE_DURATION":
                st, conf, m, evs, flgs = eval_experience_duration(matching, r)
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

            rule_st[rid] = st

            # Force verifier on RESPONSIBILITY, ACHIEVEMENT, and LEADERSHIP
            if kind in ("RESPONSIBILITY", "ACHIEVEMENT", "LEADERSHIP"):
                total_verifier_calls += 1
                verifier_calls_by_kind[kind] += 1
                snippets = [e.get("quote", "") for e in evs]
                if not snippets:
                    snippets = [c.get("text_redacted", "")[:150] for c in chunks[:3]]

                v_st, v_quote, v_flgs = verify_requirement_with_llm(
                    full_text, r, st, snippets
                )
                if "GROUNDING_FAIL" in v_flgs:
                    grounding_fails += 1

                if v_st != st:
                    changed_results.append({
                        "file": f.name,
                        "requirement_id": rid,
                        "kind": kind,
                        "rule_state": st,
                        "verifier_state": v_st,
                        "flags": v_flgs,
                    })
                ver_st[rid] = v_st
            else:
                ver_st[rid] = st

        rule_states_all[f.name] = rule_st
        verifier_states_all[f.name] = ver_st
        print(f"[{idx}/{len(core_files)}] {f.name} processed.")

    # Accuracy comparison
    rule_correct = 0
    verifier_correct = 0
    total_checks = 0

    for fname, exp_info in cand_map.items():
        ok_states = exp_info["expected_states"]
        r_got = rule_states_all.get(fname, {})
        v_got = verifier_states_all.get(fname, {})

        for rid, valid_list in ok_states.items():
            total_checks += 1
            if r_got.get(rid) in valid_list:
                rule_correct += 1
            if v_got.get(rid) in valid_list:
                verifier_correct += 1

    rule_acc = (rule_correct / total_checks) * 100
    verifier_acc = (verifier_correct / total_checks) * 100

    summary = {
        "total_verifier_calls": total_verifier_calls,
        "verifier_calls_by_kind": verifier_calls_by_kind,
        "grounding_fails": grounding_fails,
        "changed_results_count": len(changed_results),
        "changed_results": changed_results,
        "rule_accuracy": f"{rule_correct}/{total_checks} ({rule_acc:.2f}%)",
        "verifier_accuracy": f"{verifier_correct}/{total_checks} ({verifier_acc:.2f}%)",
    }
    print("\n=== SUMMARY VERIFIER RUN ===")
    print(json.dumps(summary, indent=2))
    Path("scripts/eval_runs/verifier_report.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
