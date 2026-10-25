"""
Membangun file label (kunci jawaban) dari cv_data.py + reference_scorer.py.

    python build_labels.py --out ../labels
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from cv_data import AS_OF, CVS, EDGE_CASES
from reference_scorer import score

ROOT = Path(__file__).resolve().parent.parent
GRADE = {"S1": 3, "S2": 3, "S3": 3, "S4": 3, "S5": 3,
         "M1": 2, "M3": 2, "M2": 1, "M4": 1, "M5": 1}  # irrelevant = 0


MONTHS = {
    "jan": 1, "januari": 1, "january": 1, "feb": 2, "februari": 2, "february": 2, "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4, "mei": 5, "may": 5, "jun": 6, "juni": 6, "june": 6, "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "agustus": 8, "aug": 8, "august": 8, "sep": 9, "september": 9, "okt": 10, "oktober": 10, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "des": 12, "desember": 12, "dec": 12, "december": 12,
}
PRESENT = {"sekarang", "present", "now", "saat ini", "current"}


def norm_point(s: str, is_start: bool):
    s = s.strip().lower()
    if s in PRESENT:
        return "present"
    if "/" in s:
        m, y = s.split("/")
        return f"{int(y):04d}-{int(m):02d}"
    parts = s.split()
    if len(parts) == 1:
        return f"{int(parts[0]):04d}-{7 if is_start else 6:02d}"  # aturan year-only
    return f"{int(parts[1]):04d}-{MONTHS[parts[0]]:02d}"


def norm_range(dates: str):
    a, b = [x.strip() for x in dates.replace("–", "-").split(" - ")] if " - " in dates.replace("–", "-") else (dates, dates)
    return norm_point(a, True), norm_point(b, False)


def degree_level(deg: str):
    d = deg.lower()
    return "S1" if d.startswith("s1") or "bachelor" in d else ("D3" if d.startswith("d3") else "OTHER")


def extraction_labels():
    out = {}
    for cv in CVS:
        exps = []
        for e in cv["experience"]:
            st, en = norm_range(e["dates"])
            exps.append({"title": e["title"], "organization": e["org"], "start": st, "end": en, "employment_type": e["type"]})
        out[cv["file"]] = {
            "cv_id": cv["id"],
            "experiences": exps,
            "projects_count": len(cv.get("projects", [])),
            "organizations_count": len(cv.get("organizations", [])),
            "education": [{"level": degree_level(ed["degree"]), "degree_raw": ed["degree"], "institution": ed["institution"]} for ed in cv["education"]],
            "certifications": [c["name"] for c in cv.get("certifications", [])],
            "skills": cv["skills"],
            "identity_fields_present": [k for k, v in cv["identity"].items() if v],
        }
    return out


def score_range(states_ok: dict, req_set: dict):
    keys = list(states_ok)
    results = []
    for combo in itertools.product(*[states_ok[k] for k in keys]):
        results.append(score(dict(zip(keys, combo)), req_set))
    return results


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    jd1 = json.loads((ROOT / "job_descriptions/JD-01_requirements.approved.json").read_text())

    cands = []
    for cv in CVS:
        rs = score_range(cv["expected"]["states"], jd1)
        ref = rs[0]
        cands.append({
            "cv_id": cv["id"],
            "file": f"cvs/core/{cv['file']}",
            "group": cv["group"],
            "format": cv["format"],
            "language": cv["lang"],
            "relevance_grade": GRADE.get(cv["id"], 0),
            "expected_states": cv["expected"]["states"],
            "expected_backend_months": cv["expected"]["backend_months"],
            "backend_months_tolerance": 3,
            "expected_band": sorted({r.band for r in rs}),
            "expected_score_reference": ref.final_score,
            "expected_raw_score_reference": ref.raw_score,
            "expected_score_min": min(r.final_score for r in rs),
            "expected_score_max": max(r.final_score for r in rs),
            "score_tolerance": 5,
            "expected_recommendation": sorted({r.recommendation for r in rs}),
            "note": cv["expected"].get("note", ""),
        })

    ranked = sorted(cands, key=lambda c: ({"A": 0, "B": 1, "C": 2}[c["expected_band"][0]], -c["expected_score_reference"]))
    jd01 = {
        "job_id": "JD-01",
        "as_of": AS_OF,
        "requirement_set": "job_descriptions/JD-01_requirements.approved.json",
        "reference_ranking": [c["cv_id"] for c in ranked],
        "assertions": {
            "top5_exact_set": ["S1", "S2", "S3", "S4", "S5"],
            "ranks_6_to_10_min_overlap": {"set": ["M1", "M2", "M3", "M4", "M5"], "min": 4},
            "irrelevant_max_score": 49.9,
            "irrelevant_min_rank": 11,
            "min_ndcg_at_10": 0.95,
            "min_state_accuracy": 0.90,
            "min_score_within_tolerance_ratio": 0.90,
            "max_runs_rank_change": 0,
        },
        "candidates": cands,
    }
    (out / "expected_JD-01.json").write_text(json.dumps(jd01, indent=2, ensure_ascii=False))

    i1 = next(c for c in CVS if c["id"] == "I1")
    jd02 = {
        "job_id": "JD-02",
        "as_of": AS_OF,
        "requirement_set": "job_descriptions/JD-02_requirements.approved.json",
        "assertions": {"rank_1": "I1", "rank_1_min_score": 80, "others_max_score": 30},
        "candidates": [{"cv_id": "I1", "expected_states": i1["expected"]["jd02"]["states"]}],
        "note": "Uji kontrol: semua 15 CV inti di-screening untuk JD-02. CV HR (I1) wajib peringkat 1.",
    }
    (out / "expected_JD-02.json").write_text(json.dumps(jd02, indent=2, ensure_ascii=False))

    edge = {
        "job_id": "JD-01",
        "as_of": AS_OF,
        "how_to_run": "Setiap file edge di-screening untuk JD-01 BERSAMA 15 CV inti (satu run per file edge, atau satu run berisi semua file edge). Asersi edge tidak boleh mengubah asersi top-5 inti, kecuali E2 (scan dari S2) dan E8 (duplikat S1) yang memang menyerupai kandidat kuat: keduanya tidak dihitung dalam asersi top-5.",
        "cases": [{**{k: v for k, v in e.items() if k not in ("identity", "personal")}, "file": f"cvs/edge/{e['file']}"} for e in EDGE_CASES],
    }
    (out / "expected_edge_cases.json").write_text(json.dumps(edge, indent=2, ensure_ascii=False))

    ext = {"as_of": AS_OF, "date_format": "YYYY-MM atau 'present'", "year_only_rule": "awal=YYYY-07, akhir=YYYY-06",
           "cvs": extraction_labels()}
    (out / "expected_extraction.json").write_text(json.dumps(ext, indent=2, ensure_ascii=False))

    print("reference ranking JD-01:")
    for i, c in enumerate(ranked, 1):
        print(f"{i:>2} {c['cv_id']:<3} band={c['expected_band']} score={c['expected_score_reference']} "
              f"[{c['expected_score_min']}-{c['expected_score_max']}] raw={c['expected_raw_score_reference']} rec={c['expected_recommendation']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "labels"))
    main(Path(ap.parse_args().out))
