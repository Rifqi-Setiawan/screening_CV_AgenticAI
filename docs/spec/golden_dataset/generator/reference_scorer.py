"""
Implementasi ACUAN rumus skor (lihat 02_SCORING_RUBRIC_SPEC.md bagian 5-7).

Input : status per kriteria + requirement set yang sudah disetujui.
Output: raw_score, band, final_score (setelah cap), rekomendasi, warna.

Modul ini TIDAK melakukan ekstraksi atau penentuan status; itu tugas pipeline.
Agent boleh menyalin logika ini apa adanya ke scoring engine produksi, dan
WAJIB menjaga hasilnya identik (ada unit test di evaluate.py --self-test).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

STATE_VALUE = {"STRONG": 1.0, "PARTIAL": 0.5, "NOT_DEMONSTRATED": 0.0}
# UNKNOWN tidak punya nilai: dikeluarkan dari pembilang DAN penyebut.

BAND_CAP = {"A": 100.0, "B": 74.0, "C": 49.0}
BAND_ORDER = {"A": 0, "B": 1, "C": 2, "R": 3}  # R = perlu cek manual


@dataclass
class ScoreResult:
    raw_score: float
    final_score: float
    band: str
    capped: bool
    recommendation: str
    color: str
    category_scores: dict = field(default_factory=dict)
    must_have_not_strong: list = field(default_factory=list)


def score(states: dict[str, str], requirement_set: dict) -> ScoreResult:
    reqs = requirement_set["requirements"]
    num = den = 0.0
    cat_num: dict[str, float] = {}
    cat_den: dict[str, float] = {}
    must_not_strong, must_unknown = [], []

    for r in reqs:
        rid, w, st = r["requirement_id"], float(r["weight"]), states.get(r["requirement_id"], "UNKNOWN")
        if r["importance"] == "MUST_HAVE":
            if st == "UNKNOWN":
                must_unknown.append(rid)
            elif st != "STRONG":
                must_not_strong.append(rid)
        if st == "UNKNOWN":
            continue
        v = STATE_VALUE[st]
        num += w * v
        den += w
        cat_num[r["category"]] = cat_num.get(r["category"], 0.0) + w * v
        cat_den[r["category"]] = cat_den.get(r["category"], 0.0) + w

    raw = round(100.0 * num / den, 1) if den else 0.0
    cats = {c: round(100.0 * cat_num[c] / cat_den[c], 1) for c in cat_den}

    if must_unknown:
        band = "R"
    elif not must_not_strong:
        band = "A"
    elif len(must_not_strong) == 1:
        band = "B"
    else:
        band = "C"

    cap = BAND_CAP.get(band, 100.0)
    final = min(raw, cap)
    capped = final < raw

    if band == "R":
        rec = "MANUAL_CHECK"
    elif band == "A" and final >= 70:
        rec = "SHORTLIST"
    elif band in ("A", "B"):
        rec = "REVIEW"
    else:
        rec = "LOW_PRIORITY"

    color = "green" if final >= 75 else ("yellow" if final >= 50 else "red")
    return ScoreResult(raw, final, band, capped, rec, color, cats, must_not_strong)


def tie_break_key(candidate_id: str, run_id: str) -> str:
    """Pemecah seri yang stabil dan tidak berkaitan dengan nama/tanggal upload."""
    return hashlib.sha256(f"{run_id}:{candidate_id}".encode()).hexdigest()


def rank(items: list[dict], run_id: str = "eval") -> list[dict]:
    """items: [{'candidate_id':..., 'result': ScoreResult, 'strong_count': int}]"""
    return sorted(
        items,
        key=lambda x: (
            BAND_ORDER[x["result"].band],
            -x["result"].final_score,
            -x.get("strong_count", 0),
            tie_break_key(x["candidate_id"], run_id),
        ),
    )
