#!/usr/bin/env python3
"""
Evaluator golden dataset.

Sistem yang dibangun harus bisa mengekspor hasil satu screening run ke JSON dengan
format di 06_GOLDEN_TEST_DATASET.md bagian 5 (lihat juga contoh di --self-test).

Contoh:
    python evaluate.py --jd01 out/run_jd01.json
    python evaluate.py --jd02 out/run_jd02.json
    python evaluate.py --edge out/run_edge.json
    python evaluate.py --repeat out/run_jd01_a.json out/run_jd01_b.json
    python evaluate.py --extraction out/extraction.json
    python evaluate.py --self-test
    python evaluate.py --jd01 out/run_jd01.json --report out/eval_report.md

Exit code 0 = semua asersi lulus, 1 = ada yang gagal.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "generator"))

LABELS = HERE / "labels"
LINES: list[str] = []


def log(s=""):
    print(s)
    LINES.append(s)


def load(p):
    return json.loads(Path(p).read_text())


def by_file(run):
    return {Path(r["file"]).name: r for r in run["results"]}


def check(name, ok, detail=""):
    log(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def ndcg_at_k(ranked_ids, grade, k=10):
    dcg = sum((2 ** grade.get(cid, 0) - 1) / math.log2(i + 2) for i, cid in enumerate(ranked_ids[:k]))
    ideal = sorted(grade.values(), reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


# --------------------------------------------------------------------- JD-01
def eval_jd01(run) -> bool:
    lab = load(LABELS / "expected_JD-01.json")
    A = lab["assertions"]
    res = by_file(run)
    ok_all = True
    log("== JD-01 (Backend Engineer) ==")

    file_to_id = {Path(c["file"]).name: c["cv_id"] for c in lab["candidates"]}
    missing = [f for f in file_to_id if f not in res]
    ok_all &= check("semua 15 CV inti ada di output", not missing, f"hilang: {missing}" if missing else "")

    scored = [r for f, r in res.items() if f in file_to_id and r.get("status") == "SCORED"]
    ranked_ids = [file_to_id[Path(r["file"]).name] for r in sorted(scored, key=lambda r: r["rank"])]
    pos = {cid: i + 1 for i, cid in enumerate(ranked_ids)}

    top5 = set(ranked_ids[:5])
    ok_all &= check("Precision@5 = 1.0 (top-5 = S1..S5)", top5 == set(A["top5_exact_set"]), f"top-5 sistem: {ranked_ids[:5]}")

    mid = set(ranked_ids[5:10]) & set(A["ranks_6_to_10_min_overlap"]["set"])
    ok_all &= check(f"peringkat 6-10 memuat >= {A['ranks_6_to_10_min_overlap']['min']} CV marginal", len(mid) >= A["ranks_6_to_10_min_overlap"]["min"],
                    f"peringkat 6-10: {ranked_ids[5:10]}")

    grade = {c["cv_id"]: c["relevance_grade"] for c in lab["candidates"]}
    nd = ndcg_at_k(ranked_ids, grade)
    nd5 = ndcg_at_k(ranked_ids, grade, k=5)
    ok_all &= check(f"NDCG@10 >= {A['min_ndcg_at_10']}", nd >= A["min_ndcg_at_10"], f"{nd:.3f}")
    ok_all &= check("NDCG@5 >= 0.95", nd5 >= 0.95, f"{nd5:.3f}")

    # Precision at shortlist (kandidat SHORTLIST yang berlabel Strong)
    id_to_file = {c["cv_id"]: Path(c["file"]).name for c in lab["candidates"]}
    shortlisted_strong = sum(
        1 for cid in ranked_ids
        if res.get(id_to_file.get(cid, ""), {}).get("recommendation") == "SHORTLIST" and grade.get(cid, 0) == 3
    )
    total_shortlisted = sum(
        1 for cid in ranked_ids
        if res.get(id_to_file.get(cid, ""), {}).get("recommendation") == "SHORTLIST"
    ) or 1
    p_shortlist = shortlisted_strong / total_shortlisted
    check("Precision@Shortlist >= 0.90", p_shortlist >= 0.90, f"{p_shortlist:.2f} (info)")

    irr_fail = []
    for c in lab["candidates"]:
        if c["group"] != "irrelevant":
            continue
        r = res.get(Path(c["file"]).name)
        if not r:
            continue
        if r.get("score", 0) > A["irrelevant_max_score"] or pos.get(c["cv_id"], 99) < A["irrelevant_min_rank"]:
            irr_fail.append(f"{c['cv_id']} skor={r.get('score')} rank={pos.get(c['cv_id'])}")
    ok_all &= check("CV tidak relevan: skor < 50 dan peringkat > 10", not irr_fail, "; ".join(irr_fail))

    total = correct = 0
    wrong = []
    in_tol = n_score = 0
    off_score = []
    months_off = []
    for c in lab["candidates"]:
        r = res.get(Path(c["file"]).name)
        if not r or r.get("status") != "SCORED":
            continue
        st = r.get("requirement_states", {})
        for rid, ok_states in c["expected_states"].items():
            total += 1
            if st.get(rid) in ok_states:
                correct += 1
            else:
                wrong.append(f"{c['cv_id']}.{rid}: dapat {st.get(rid)} harusnya {ok_states}")
        n_score += 1
        lo, hi = c["expected_score_min"] - c["score_tolerance"], c["expected_score_max"] + c["score_tolerance"]
        if lo <= r.get("score", -1) <= hi:
            in_tol += 1
        else:
            off_score.append(f"{c['cv_id']} {r.get('score')} (harapan {lo}-{hi})")
        bm = (r.get("metrics") or {}).get("backend_months")
        if bm is not None and abs(bm - c["expected_backend_months"]) > c["backend_months_tolerance"]:
            months_off.append(f"{c['cv_id']} {bm} vs {c['expected_backend_months']}")

    acc = correct / total if total else 0
    ok_all &= check(f"akurasi status per kriteria >= {A['min_state_accuracy']}", acc >= A["min_state_accuracy"], f"{acc:.3f} ({correct}/{total})")
    for w in wrong[:25]:
        log(f"      - {w}")
    ratio = in_tol / n_score if n_score else 0
    ok_all &= check(f"skor dalam toleransi >= {A['min_score_within_tolerance_ratio']}", ratio >= A["min_score_within_tolerance_ratio"],
                    f"{ratio:.2f}; meleset: {off_score}" if off_score else f"{ratio:.2f}")
    check("bulan pengalaman backend (+-3) [informasi, tidak memblokir]", not months_off, "; ".join(months_off))
    log(f"  urutan sistem : {ranked_ids}")
    log(f"  urutan acuan  : {lab['reference_ranking']}")
    return ok_all


# --------------------------------------------------------------------- JD-02
def eval_jd02(run) -> bool:
    lab = load(LABELS / "expected_JD-02.json")
    A = lab["assertions"]
    log("== JD-02 (HR Generalist, uji kontrol) ==")
    scored = sorted([r for r in run["results"] if r.get("status") == "SCORED"], key=lambda r: r["rank"])
    ok = True
    if not scored:
        return check("ada hasil", False)
    first = scored[0]
    ok &= check("I1 (HR) di peringkat 1", Path(first["file"]).name.startswith("I1_"), f"peringkat 1: {first['file']}")
    ok &= check(f"skor I1 >= {A['rank_1_min_score']}", first.get("score", 0) >= A["rank_1_min_score"] if Path(first["file"]).name.startswith("I1_") else False,
                str(first.get("score")))
    others = [f"{Path(r['file']).name}={r['score']}" for r in scored[1:] if r.get("score", 0) > A["others_max_score"]]
    ok &= check(f"CV lain skor <= {A['others_max_score']}", not others, "; ".join(others))
    return ok


# ---------------------------------------------------------------------- edge
def eval_edge(run) -> bool:
    lab = load(LABELS / "expected_edge_cases.json")
    res = by_file(run)
    log("== Edge cases ==")
    ok_all = True
    for case in lab["cases"]:
        e, f = case["expected"], Path(case["file"]).name
        r = res.get(f)
        log(f"- {case['id']} ({f})")
        if r is None:
            ok_all &= check("ada di output", False)
            continue
        if "status" in e:
            ok_all &= check(f"status = {e['status']}", r.get("status") == e["status"], f"dapat {r.get('status')}")
        if "reasons_any" in e:
            ok_all &= check(f"alasan salah satu dari {e['reasons_any']}", bool(set(r.get("reasons", [])) & set(e["reasons_any"])), str(r.get("reasons")))
        if "flags_any" in e:
            ok_all &= check(f"flag salah satu dari {e['flags_any']}", bool(set(r.get("flags", [])) & set(e["flags_any"])), str(r.get("flags")))
        if "flags_nice_to_have" in e:
            check(f"(nice-to-have) flag {e['flags_nice_to_have']}", bool(set(r.get("flags", [])) & set(e["flags_nice_to_have"])), str(r.get("flags")))
        if "max_score" in e:
            ok_all &= check(f"skor <= {e['max_score']}", r.get("score", 0) <= e["max_score"], str(r.get("score")))
        if "band" in e:
            ok_all &= check(f"band = {e['band']}", r.get("band") == e["band"], str(r.get("band")))
        if "band_not" in e:
            ok_all &= check(f"band != {e['band_not']}", r.get("band") != e["band_not"], str(r.get("band")))
        if "states" in e:
            bad = [f"{k}:{r.get('requirement_states', {}).get(k)}" for k, v in e["states"].items() if r.get("requirement_states", {}).get(k) not in v]
            ok_all &= check("status kriteria sesuai", not bad, "; ".join(bad))
        if "parity_with" in e:
            src = next((x for n, x in res.items() if n.startswith(e["parity_with"] + "_")), None)
            if src is None:
                ok_all &= check(f"{e['parity_with']} ikut di run yang sama", False)
            else:
                agree = sum(1 for k, v in src.get("requirement_states", {}).items() if r.get("requirement_states", {}).get(k) == v)
                ok_all &= check(f"status sama dengan {e['parity_with']} >= {e['min_state_agreement']}/10", agree >= e["min_state_agreement"], f"{agree}/10")
                ok_all &= check(f"selisih skor <= {e['score_tolerance']}", abs(r.get("score", 0) - src.get("score", 0)) <= e["score_tolerance"],
                                f"{r.get('score')} vs {src.get('score')}")
        if "pair" in e and case["id"].endswith("a"):
            other = next((x for n, x in res.items() if n.startswith(e["pair"] + "_")), None)
            if other is None:
                ok_all &= check("pasangan counterfactual ada", False)
            else:
                d = abs(r.get("score", 0) - other.get("score", 0))
                ok_all &= check(f"selisih skor pasangan <= {e['max_score_delta']}", d <= e["max_score_delta"], f"{d}")
                ok_all &= check("status kriteria identik", r.get("requirement_states") == other.get("requirement_states"))
        if "duplicate_of" in e:
            ok_all &= check(f"ditandai duplikat dari {e['duplicate_of']}", Path(r.get("duplicate_of") or "").name == e["duplicate_of"], str(r.get("duplicate_of")))
    return ok_all


def _tokens(s):
    import re
    return set(re.findall(r"[a-z0-9]+", re.sub(r"\(.*?\)", "", (s or "").lower())))


def eval_extraction(pred) -> bool:
    """pred = {"files": {"<nama file>": {"experiences":[{title,organization,start,end,employment_type}],
                                        "education":[{level}], "certifications":[str], "skills":[str]}}}"""
    lab = load(LABELS / "expected_extraction.json")["cvs"]
    P = pred.get("files", {})
    log("== Ekstraksi CV (15 CV inti) ==")
    exp_total = exp_date = exp_title = type_ok = 0
    sk_total = sk_hit = ce_total = ce_hit = ed_total = ed_ok = 0
    misses = []
    for f, g in lab.items():
        p = P.get(f)
        if p is None:
            misses.append(f"{g['cv_id']}: tidak ada output")
            exp_total += len(g["experiences"]); sk_total += len(g["skills"]); ce_total += len(g["certifications"]); ed_total += len(g["education"])
            continue
        pe = p.get("experiences", [])
        for e in g["experiences"]:
            exp_total += 1
            m = next((x for x in pe if x.get("start") == e["start"] and x.get("end") == e["end"]), None)
            if m:
                exp_date += 1
                if len(_tokens(m.get("title")) & _tokens(e["title"])) / max(1, len(_tokens(e["title"]))) >= 0.5:
                    exp_title += 1
                if m.get("employment_type") == e["employment_type"]:
                    type_ok += 1
            else:
                misses.append(f"{g['cv_id']}: pengalaman '{e['title']}' {e['start']}..{e['end']} tidak ditemukan")
        ps = {" ".join(sorted(_tokens(s))) for s in p.get("skills", [])}
        for s in g["skills"]:
            sk_total += 1
            sk_hit += " ".join(sorted(_tokens(s))) in ps
        pc = p.get("certifications", [])
        for c in g["certifications"]:
            ce_total += 1
            ce_hit += any(len(_tokens(c) & _tokens(x)) / max(1, len(_tokens(c))) >= 0.6 for x in pc)
        pl = [x.get("level") for x in p.get("education", [])]
        for ed in g["education"]:
            ed_total += 1
            ed_ok += ed["level"] in pl
    r = lambda a, b: a / b if b else 0
    ok = True
    ok &= check("tanggal pengalaman tepat (bulan) >= 0.90", r(exp_date, exp_total) >= 0.90, f"{r(exp_date, exp_total):.2f} ({exp_date}/{exp_total})")
    ok &= check("judul jabatan cocok >= 0.90", r(exp_title, exp_total) >= 0.90, f"{r(exp_title, exp_total):.2f}")
    check("jenis kerja (full_time/internship/freelance) [informasi]", r(type_ok, exp_total) >= 0.90, f"{r(type_ok, exp_total):.2f}")
    ok &= check("recall skill >= 0.85", r(sk_hit, sk_total) >= 0.85, f"{r(sk_hit, sk_total):.2f}")
    ok &= check("recall sertifikasi >= 0.80", r(ce_hit, ce_total) >= 0.80, f"{r(ce_hit, ce_total):.2f}")
    ok &= check("jenjang pendidikan benar >= 0.90", r(ed_ok, ed_total) >= 0.90, f"{r(ed_ok, ed_total):.2f}")
    for m in misses[:20]:
        log(f"      - {m}")
    return ok


def eval_repeat(a, b) -> bool:
    log("== Stabilitas (run ulang dengan konfigurasi sama) ==")
    ra = {Path(r["file"]).name: (r.get("rank"), r.get("score")) for r in a["results"]}
    rb = {Path(r["file"]).name: (r.get("rank"), r.get("score")) for r in b["results"]}
    diff = [f"{k}: {ra[k]} vs {rb.get(k)}" for k in ra if ra[k] != rb.get(k)]
    return check("peringkat dan skor identik", not diff, "; ".join(diff[:10]))


# ----------------------------------------------------------------- self-test
def self_test() -> bool:
    """Bangun output 'sempurna' dari label, lalu pastikan evaluator meluluskannya."""
    from reference_scorer import rank, score

    jd1 = load(HERE / "job_descriptions/JD-01_requirements.approved.json")
    lab = load(LABELS / "expected_JD-01.json")
    items = []
    for c in lab["candidates"]:
        st = {k: v[0] for k, v in c["expected_states"].items()}
        items.append({"candidate_id": c["cv_id"], "result": score(st, jd1), "states": st, "c": c,
                      "strong_count": sum(v == "STRONG" for v in st.values())})
    results = []
    for i, it in enumerate(rank(items), 1):
        r = it["result"]
        results.append({"file": it["c"]["file"], "status": "SCORED", "rank": i, "band": r.band, "score": r.final_score,
                        "raw_score": r.raw_score, "recommendation": r.recommendation, "requirement_states": it["states"],
                        "metrics": {"backend_months": it["c"]["expected_backend_months"]}, "flags": [], "reasons": []})
    run = {"job_id": "JD-01", "run_id": "selftest", "results": results}
    ok = eval_jd01(run)
    # Asersi unit untuk reference_scorer
    log("== Unit test reference_scorer ==")
    m1 = score({"R1": "STRONG", "R2": "STRONG", "R3": "PARTIAL", "R4": "STRONG", "R5": "STRONG", "R6": "NOT_DEMONSTRATED",
                "R7": "STRONG", "R8": "NOT_DEMONSTRATED", "R9": "STRONG", "R10": "NOT_DEMONSTRATED"}, jd1)
    ok &= check("M1: raw 77 -> band B -> cap 74", (m1.raw_score, m1.band, m1.final_score) == (77.0, "B", 74.0), str(m1))
    unk = score({"R1": "UNKNOWN", "R2": "STRONG", "R3": "STRONG", "R4": "STRONG"}, jd1)
    ok &= check("UNKNOWN pada must-have -> band R (cek manual)", unk.band == "R" and unk.recommendation == "MANUAL_CHECK", str(unk))
    part = score({k: "UNKNOWN" for k in ["R1"]} | {k: "STRONG" for k in ["R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]}, jd1)
    ok &= check("UNKNOWN keluar dari penyebut (raw 100)", part.raw_score == 100.0, str(part.raw_score))
    # Ekstraksi sempurna harus lulus
    ext = load(LABELS / "expected_extraction.json")["cvs"]
    perfect = {"files": {f: {"experiences": g["experiences"], "education": [{"level": e["level"]} for e in g["education"]],
                             "certifications": g["certifications"], "skills": g["skills"]} for f, g in ext.items()}}
    ok &= eval_extraction(perfect)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jd01")
    ap.add_argument("--jd02")
    ap.add_argument("--edge")
    ap.add_argument("--repeat", nargs=2)
    ap.add_argument("--extraction")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--report")
    a = ap.parse_args()
    ok = True
    ran = False
    if a.self_test:
        ok &= self_test(); ran = True
    if a.jd01:
        ok &= eval_jd01(load(a.jd01)); ran = True
    if a.jd02:
        ok &= eval_jd02(load(a.jd02)); ran = True
    if a.edge:
        ok &= eval_edge(load(a.edge)); ran = True
    if a.repeat:
        ok &= eval_repeat(load(a.repeat[0]), load(a.repeat[1])); ran = True
    if a.extraction:
        ok &= eval_extraction(load(a.extraction)); ran = True
    if not ran:
        ap.print_help()
        sys.exit(2)
    log("")
    log("HASIL AKHIR: " + ("LULUS" if ok else "GAGAL"))
    if a.report:
        Path(a.report).write_text("```\n" + "\n".join(LINES) + "\n```\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
