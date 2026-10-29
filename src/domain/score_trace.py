"""Score trace: explain a candidate's result down to the sentence of the original CV (v2.2).

Everything shown to a recruiter is derived from what the pipeline stored, in this order:

    final score and band  <-  requirement states and weights  <-  facet verdicts  <-  evidence atoms  <-  CV text

`build_score_trace` assembles that chain. Nothing here calls an LLM and nothing is invented: a sentence in the
trace is either a stored value, a verbatim slice of the (redacted) CV text, or a fixed Indonesian template
filled with stored values. The final numbers are recomputed with the same scorer and compared with the stored
ones; when they differ (for example a run made with older scoring rules) the trace says so instead of hiding it.
"""

from __future__ import annotations

import re
from typing import Any

from src.agents.schemas.matcher import FacetEvaluationResult
from src.domain.atoms import span_matches_text
from src.domain.matching.ontology_shortcut import determine_atom_tier
from src.domain.scoring.scorer_v2 import SHORTLIST_CUTOFF, STATE_VALUE, score_v2
from src.infrastructure.config import settings

CONTEXT_CHARS = 160

TIER_LABELS = {
    "T0": "Klaim atau daftar keahlian (bukan bukti kerja)",
    "T1": "Proyek",
    "T2": "Pengalaman kerja",
    "T3": "Pengalaman kerja dengan kepemilikan/kepemimpinan",
    "T4": "Pengalaman kerja dengan dampak terukur",
}

STATE_LABELS = {
    "STRONG": "Terbukti kuat",
    "PARTIAL": "Terbukti sebagian",
    "NOT_DEMONSTRATED": "Belum terbukti",
    "UNKNOWN": "Belum bisa dinilai",
}

VERDICT_LABELS = {
    "ENTAILED": "Didukung bukti",
    "PARTIAL": "Didukung sebagian",
    "NOT_ENTAILED": "Tidak didukung bukti",
    "CONTRADICTED": "Bertentangan dengan bukti",
    "UNKNOWN": "Tidak bisa dinilai",
    "SATISFIED": "Terpenuhi (aturan ontologi)",
}

# Exact flag -> meaning, then prefix flag -> meaning (flags often carry a suffix such as ":R4").
FLAG_MEANINGS = {
    "HIDDEN_TEXT": "Ada teks tersembunyi di berkas (font sangat kecil, warna sama dengan latar, atau tertutup). Teks itu tidak dipakai sebagai bukti.",
    "PROMPT_INJECTION": "Berkas memuat kalimat yang tampak mengarahkan penilaian otomatis. Kalimat itu diperlakukan sebagai data, bukan instruksi.",
    "INJECTION_SUSPECT": "Model menandai teks dalam berkas yang mencoba mengarahkan penilaian.",
    "KEYWORD_STUFFING": "Daftar kata kunci yang tidak disertai riwayat kerja.",
    "HIGH_T0_EVIDENCE_RATIO": "Sebagian besar bukti hanya berupa klaim atau daftar keahlian, bukan pengalaman kerja.",
    "AGENT_DISAGREEMENT": "Penilai kedua (Critic) tidak sepakat dengan penilai pertama pada setidaknya satu facet.",
    "AGENT_DISAGREEMENT_REVIEW": "Ada ketidaksepakatan antar penilai; rekomendasi shortlist diturunkan menjadi review manusia.",
    "DATE_UNCERTAIN": "Tanggal kerja tidak pasti sehingga durasi punya rentang (terendah-tertinggi).",
    "DATE_ANOMALY": "Ada tanggal yang janggal (terbalik, terlalu panjang, atau di masa depan).",
    "LOW_COVERAGE": "Kurang dari 60% bobot kriteria yang bisa dinilai.",
    "SCORE_INTERVAL_STRADDLES_SHORTLIST": "Kriteria yang belum bisa dinilai bisa menggeser kandidat melewati batas shortlist.",
    "NON_SCORABLE_REQUIREMENT_SKIPPED": "Ada kriteria yang dilewati karena melanggar kebijakan (atribut terlarang).",
    "SPAN_VERIFICATION_UNAVAILABLE": "Lokasi kutipan di berkas tidak bisa diverifikasi; semua kutipan dipakai apa adanya.",
    "INVISIBLE_CHARS": "Ada karakter tak terlihat di teks berkas.",
    "BIDI_CONTROL": "Ada karakter pengatur arah tulisan yang tersembunyi di teks berkas.",
    "HOMOGLYPH_MIX": "Ada kata yang mencampur huruf Latin dengan huruf mirip dari alfabet lain.",
    "INTERVIEW_ADJUSTED": "Skor ini sudah memasukkan penilaian jawaban wawancara.",
}
FLAG_PREFIX_MEANINGS = {
    "T0_CAPPED_AT_PARTIAL": "Kriteria ini hanya didukung klaim/daftar keahlian sehingga dibatasi maksimal PARTIAL.",
    "T0_DEPTH_FLOOR_ENFORCED": "Bukti hanya klaim sehingga kedalamannya dikunci rendah.",
    "SUPPORTING_ATOMS_CAPPED": "Jumlah bukti per facet dibatasi agar CV yang panjang tidak diuntungkan.",
    "DOMAIN_INFERENCE": "Facet ini dinaikkan ke PARTIAL dari konteks sistem transaksi yang dikerjakan, tanpa menyebut teknologinya secara eksplisit.",
    "UNVERIFIED_SPAN_ATOMS": "Beberapa kutipan tidak ditemukan di berkas dan tidak dipakai sebagai bukti.",
    "UNKNOWN_CONCEPT": "Istilah dalam CV belum ada di ontologi sehingga tidak ikut pencocokan otomatis.",
    "ATOM_OVERUSED": "Satu kutipan dipakai sebagai bukti untuk terlalu banyak facet.",
}


def explain_flag(flag: str) -> str:
    if flag in FLAG_MEANINGS:
        return FLAG_MEANINGS[flag]
    prefix = flag.split(":", 1)[0]
    return FLAG_PREFIX_MEANINGS.get(prefix, "")


def _verdict(raw: Any) -> str:
    return str(getattr(raw, "value", raw) or "UNKNOWN").split(".")[-1].upper()


# ----------------------------------------------------------------------------------------------- source
def _occurrences(text: str, needle: str, limit: int = 25) -> list[tuple[int, int]]:
    needle = needle.strip()
    if not needle:
        return []
    out: list[tuple[int, int]] = []
    pos = text.find(needle)
    while pos >= 0 and len(out) < limit:
        out.append((pos, pos + len(needle)))
        pos = text.find(needle, pos + 1)
    if out:
        return out
    tokens = needle.split()
    if len(tokens) < 2 or len(needle) > 600:
        return []
    pattern = re.compile(r"\s+".join(re.escape(t) for t in tokens), re.IGNORECASE)
    return [(m.start(), m.end()) for m in pattern.finditer(text)][:limit]


def locate_in_text(text: str, atom_text: str, hint: int | None = None) -> tuple[int, int] | None:
    """Where an atom sits in the stored CV text; of several matches the one closest to `hint` wins."""
    found = _occurrences(text, atom_text)
    if not found:
        return None
    if hint is None:
        return found[0]
    return min(found, key=lambda se: abs(se[0] - hint))


def source_ref(atom: dict[str, Any], full_text: str | None) -> dict[str, Any]:
    """The verbatim CV sentence behind an atom, with surrounding text and a verification flag."""
    atom_text = str(atom.get("text_redacted") or "").strip()
    start = end = None
    if full_text and atom_text:
        rs, re_ = atom.get("red_start"), atom.get("red_end")
        if isinstance(rs, int) and isinstance(re_, int) and span_matches_text(full_text, rs, re_, atom_text):
            start, end = rs, re_
        else:
            located = locate_in_text(full_text, atom_text, hint=rs if isinstance(rs, int) else None)
            if located:
                start, end = located
    tier = determine_atom_tier(
        {"kind": atom.get("kind", ""), "visibility": atom.get("visibility", "VISIBLE"), "rating": atom.get("rating")}
    )
    ref: dict[str, Any] = {
        "atom_key": atom.get("atom_key"),
        "kind": atom.get("kind"),
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, tier),
        "is_evidence": tier != "T0",
        "page": atom.get("page"),
        "quote": atom_text,
        "source_found": start is not None,
        "span": None,
        "context_before": "",
        "context_after": "",
    }
    if start is not None and full_text is not None and end is not None:
        ref["quote"] = full_text[start:end].strip()
        ref["span"] = [start, end]
        lo = max(0, start - CONTEXT_CHARS)
        before = full_text[lo:start]
        if lo > 0 and " " in before:  # do not start the window in the middle of a word
            before = before.split(" ", 1)[1]
        after = full_text[end : end + CONTEXT_CHARS]
        if end + CONTEXT_CHARS < len(full_text) and " " in after:  # nor end it in the middle of one
            after = after.rsplit(" ", 1)[0]
        ref["context_before"] = before.lstrip()
        ref["context_after"] = after.rstrip()
    return ref


# ----------------------------------------------------------------------------------------------- reasons
def _why_state(
    state: str,
    facets: list[dict[str, Any]],
    duration: dict[str, Any] | None,
    flags: list[str],
    req_id: str,
) -> str:
    core = [f for f in facets if f["core"]]
    parts: list[str] = []
    if core:
        entailed = [f for f in core if f["verdict"] in ("ENTAILED", "SATISFIED")]
        deep = [f for f in entailed if f["depth"] in ("L2", "L3", "L4")]
        open_ = [f for f in core if f not in entailed]
        if state == "STRONG":
            parts.append(
                f"Semua {len(core)} facet inti didukung bukti dan {len(deep)} di antaranya berkedalaman L2 atau lebih."
            )
        elif state == "PARTIAL":
            if open_:
                names = ", ".join(
                    f"{f['facet_key']} ({VERDICT_LABELS.get(f['verdict'], f['verdict']).lower()})" for f in open_
                )
                parts.append(f"Sebagian terbukti. Facet inti yang belum penuh: {names}.")
            else:
                parts.append("Facet inti didukung bukti, tetapi kedalaman atau durasi belum memenuhi syarat STRONG.")
        elif state == "NOT_DEMONSTRATED":
            parts.append(
                "Bukti pada CV tidak cukup untuk facet inti: " + ", ".join(f["facet_key"] for f in open_) + "."
            )
        else:
            parts.append("Belum bisa dinilai karena tidak ada facet inti yang bisa diuji.")
    if duration and duration.get("min_months"):
        lo, hi, need = duration["months_lo"], duration["months_hi"], duration["min_months"]
        rng = f"{lo:g}" if lo == hi else f"{lo:g}-{hi:g}"
        verdict = "memenuhi" if lo >= need else ("belum memenuhi" if hi < need else "belum pasti memenuhi")
        parts.append(f"Durasi relevan {rng} bulan, {verdict} minimum {need:g} bulan.")
    if any(f.split(":", 1)[0] == "T0_CAPPED_AT_PARTIAL" and f.endswith(f":{req_id}") for f in flags):
        parts.append("Dibatasi PARTIAL karena hanya didukung klaim atau daftar keahlian.")
    return " ".join(parts)


def _band_reason(
    band: str, must_not_strong: list[str], flags: list[str], cap: float | None, raw: float, final: float
) -> str:
    if cap is not None and final < raw:
        cap_txt = f" Skor dibatasi maksimal {cap:g} (hitungan sebelum batas: {raw:g})."
    elif cap is not None:
        cap_txt = f" Batas skor band ini {cap:g}, belum terlampaui."
    else:
        cap_txt = ""
    if band == "A":
        return "Semua syarat wajib (MUST_HAVE) terbukti kuat."
    if band == "B":
        return f"Satu syarat wajib belum terbukti kuat ({', '.join(must_not_strong)}).{cap_txt}"
    if band == "C":
        return f"Dua atau lebih syarat wajib belum terbukti kuat ({', '.join(must_not_strong)}).{cap_txt}"
    reasons = []
    if "AGENT_DISAGREEMENT" in flags and settings.AGENT_DISAGREEMENT_FORCES_BAND_R:
        reasons.append("ada ketidaksepakatan antar penilai (aturan lama)")
    reasons.append("ada syarat wajib yang belum bisa dinilai")
    return "Perlu pemeriksaan manual: " + " dan ".join(reasons) + "."


def _recommendation_reason(rec: str, band: str, final: float, coverage: float | None, flags: list[str]) -> str:
    if rec == "SHORTLIST":
        return f"Band A dan skor {final:g} mencapai batas shortlist ({SHORTLIST_CUTOFF:g})."
    if rec == "REVIEW":
        if "AGENT_DISAGREEMENT_REVIEW" in flags:
            return "Layak masuk shortlist menurut skor, tetapi penilai tidak sepakat sehingga perlu review manusia."
        return f"Band {band} (skor {final:g}): layak ditinjau recruiter, belum otomatis shortlist."
    if rec == "LOW_PRIORITY":
        return f"Band {band}: terlalu banyak syarat wajib yang belum terbukti."
    if rec == "MANUAL_CHECK":
        if coverage is not None and coverage < 0.6:
            return "Hanya sebagian kecil kriteria yang bisa dinilai; perlu pemeriksaan manual."
        return "Ada hal yang tidak bisa diputuskan otomatis; perlu pemeriksaan manual."
    return ""


# ----------------------------------------------------------------------------------------------- timeline
def _timeline(duration_row: dict[str, Any]) -> list[dict[str, Any]]:
    ledger = sorted(duration_row.get("month_ledger") or [], key=lambda m: m["month"])
    periods: list[dict[str, Any]] = []
    cur: dict[str, Any] | None = None
    for m in ledger:
        ym, entry, weight = m["month"], m.get("contributing_entry"), m.get("weight", 1.0)
        if cur and cur["entry"] == entry and cur["weight"] == weight and _next(cur["end"]) == ym:
            cur["end"] = ym
            cur["months"] += 1
        else:
            if cur:
                periods.append(cur)
            cur = {"entry": entry, "weight": weight, "start": ym, "end": ym, "months": 1}
    if cur:
        periods.append(cur)
    return periods


def _next(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}"


# ----------------------------------------------------------------------------------------------- main
def build_score_trace(
    *,
    stored: dict[str, Any],
    requirements: list[dict[str, Any]],
    requirement_states: dict[str, str],
    category_weights: dict[str, float] | None,
    facet_judgments: list[dict[str, Any]],
    critic_reviews: list[dict[str, Any]],
    domain_durations: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
    full_text: str | None,
) -> dict[str, Any]:
    """Assembles the full explanation. `stored` = {final_score, raw_score, band, recommendation, flags, coverage}."""
    flags = sorted({str(f) for f in (stored.get("flags") or [])})
    atom_index: dict[str, dict[str, Any]] = {}
    for a in atoms:
        if a.get("atom_key"):
            atom_index[str(a["atom_key"])] = a
        if a.get("id"):
            atom_index[str(a["id"])] = a

    judged: dict[str, dict[str, Any]] = {}
    for j in facet_judgments:
        judged.setdefault(j["facet_key"], j)
    reviewed = {c["facet_key"]: c for c in critic_reviews}
    durations = {d["domain"]: d for d in domain_durations}

    refs_cache: dict[str, dict[str, Any]] = {}

    def ref_for(key: str) -> dict[str, Any] | None:
        atom = atom_index.get(key)
        if atom is None:
            return None
        k = str(atom.get("atom_key") or key)
        if k not in refs_cache:
            refs_cache[k] = source_ref(atom, full_text)
        return refs_cache[k]

    req_view: list[dict[str, Any]] = []
    counted_weight = sum(
        float(r["weight"]) for r in requirements if requirement_states.get(r["requirement_id"]) not in (None, "UNKNOWN")
    )
    sum_all = sum(float(r["weight"]) for r in requirements) or 1.0
    cited: dict[str, dict[str, Any]] = {}
    for r in requirements:
        rid = r["requirement_id"]
        state = requirement_states.get(rid, "UNKNOWN")
        facets_out = []
        for f in r.get("facets") or []:
            j = judged.get(f["facet_key"], {})
            c = reviewed.get(f["facet_key"])
            keys = list(
                dict.fromkeys(
                    [
                        *(j.get("support_atom_keys") or []),
                        *(j.get("support_atom_ids") or []),
                        *((c or {}).get("support_atoms") or []),
                    ]
                )
            )
            evidence = []
            for k in keys:
                ref = ref_for(str(k))
                if ref:
                    evidence.append(ref)
                    cited[ref["atom_key"]] = ref
            facets_out.append(
                {
                    "facet_key": f["facet_key"],
                    "hypothesis": f.get("hypothesis", ""),
                    "core": bool(f.get("core", True)),
                    "verdict": _verdict(j.get("verdict")) if j else "UNKNOWN",
                    "verdict_label": VERDICT_LABELS.get(_verdict(j.get("verdict")) if j else "UNKNOWN", ""),
                    "depth": str(getattr(j.get("depth_level"), "value", j.get("depth_level")) or "L0") if j else "L0",
                    "analysis": j.get("analysis", "") if j else "",
                    "rationale_code": j.get("rationale_code") if j else None,
                    "method": j.get("method") if j else None,
                    "evidence": evidence,
                    "evidence_tracked": bool(keys),
                    "critic": (
                        {
                            "action": c.get("verdict_action"),
                            "final_verdict": _verdict(c.get("final_verdict")),
                            "original_verdict": _verdict(c.get("original_verdict"))
                            if c.get("original_verdict")
                            else None,
                            "reasoning": c.get("reasoning") or c.get("analysis") or "",
                            "disagreement": bool(c.get("is_disagreement")),
                        }
                        if c
                        else None
                    ),
                }
            )
        policy = r.get("duration_policy") or {}
        domain = (r.get("target_domains") or ["general"])[0]
        dur_row = durations.get(domain)
        duration = None
        if dur_row is not None or policy.get("min_months"):
            duration = {
                "domain": domain,
                "months_lo": float(dur_row["months_lo"]) if dur_row else 0.0,
                "months_hi": float(dur_row["months_hi"]) if dur_row else 0.0,
                "min_months": float(policy.get("min_months", 0.0) or 0.0),
                "periods": _timeline(dur_row) if dur_row else [],
            }
            if not duration["min_months"]:
                duration = None if not duration["periods"] else duration
        weight = float(r["weight"])
        value = STATE_VALUE.get(state)
        counted = state != "UNKNOWN"
        req_view.append(
            {
                "requirement_id": rid,
                "description": r.get("description", ""),
                "kind": r.get("kind"),
                "category": r.get("category"),
                "importance": r.get("importance"),
                "weight": weight,
                "weight_share": round(100.0 * weight / sum_all, 1),
                "state": state,
                "state_label": STATE_LABELS.get(state, state),
                "state_value": value,
                "counted": counted,
                "points": round(weight * value, 2) if (counted and value is not None) else None,
                "max_points": weight,
                "why": _why_state(state, facets_out, duration, flags, rid),
                "facets": facets_out,
                "duration": duration,
            }
        )

    # Recompute with the scorer and compare with the stored result.
    req_set = {
        "category_weights": category_weights or {},
        "requirements": [
            {
                "requirement_id": r["requirement_id"],
                "category": r.get("category", "HARD_SKILLS"),
                "importance": r.get("importance", "MUST_HAVE"),
                "weight": float(r["weight"]),
                "lint_flags": r.get("lint_flags") or [],
                "facets": r.get("facets") or [],
            }
            for r in requirements
        ],
    }
    judg_for_scorer: list[FacetEvaluationResult | dict[str, Any]] = [
        {
            "facet_key": j["facet_key"],
            "verdict": _verdict(j.get("verdict")),
            "depth_level": j.get("depth_level") or "L0",
            "support_atoms": list(j.get("support_atom_keys") or j.get("support_atom_ids") or []),
        }
        for j in judged.values()
    ]
    recomputed = score_v2(
        states=requirement_states,
        requirement_set=req_set,
        facet_judgments=judg_for_scorer,
        atoms=[a for a in atoms if a.get("atom_key")],
        flags=[f for f in flags if f == "AGENT_DISAGREEMENT"],
        apply_depth=settings.SCORER_DEPTH_FACTORS_ENABLED,
    )
    final = float(stored.get("final_score") or 0.0)
    consistent = abs(recomputed.final_score - final) <= 0.11 and recomputed.band == stored.get("band")

    must_not_strong = list(recomputed.must_have_not_strong)
    cap = {"B": 74.0, "C": 49.0}.get(str(stored.get("band")))
    category = [
        {"category": c, "score": s, "weight": (category_weights or {}).get(c)}
        for c, s in sorted(recomputed.category_scores.items())
    ]

    return {
        "summary": {
            "final_score": final,
            "raw_score": float(stored.get("raw_score") or 0.0),
            "band": stored.get("band"),
            "recommendation": stored.get("recommendation"),
            "coverage": stored.get("coverage"),
            "score_interval": [recomputed.score_lo, recomputed.score_hi],
            "capped": bool(final < float(stored.get("raw_score") or 0.0)),
            "band_reason": _band_reason(
                str(stored.get("band")), must_not_strong, flags, cap, float(stored.get("raw_score") or 0.0), final
            ),
            "recommendation_reason": _recommendation_reason(
                str(stored.get("recommendation")), str(stored.get("band")), final, stored.get("coverage"), flags
            ),
            "counted_weight": counted_weight,
            "total_weight": sum_all,
        },
        "formula": (
            "Skor = jumlah (bobot kriteria x nilai state) / jumlah bobot kriteria yang bisa dinilai x 100. "
            "Nilai state: STRONG 1,0; PARTIAL 0,5; NOT_DEMONSTRATED 0. Kriteria yang belum bisa dinilai (UNKNOWN) tidak "
            "dihitung, tetapi menjadi rentang skor terendah-tertinggi."
            + (" Kedalaman bukti (L0-L4) ikut mengalikan nilai." if settings.SCORER_DEPTH_FACTORS_ENABLED else "")
            + " Band dan batas skor ditentukan oleh syarat wajib: Band A bila semuanya STRONG, B bila satu belum (maks 74), "
            "C bila dua atau lebih (maks 49)."
        ),
        "categories": category,
        "requirements": req_view,
        "flags": [{"flag": f, "meaning": explain_flag(f)} for f in flags],
        "consistency": {
            "consistent": consistent,
            "stored_final": final,
            "recomputed_final": recomputed.final_score,
            "stored_band": stored.get("band"),
            "recomputed_band": recomputed.band,
            "note": (
                ""
                if consistent
                else "Angka rekonstruksi berbeda dari angka tersimpan: run ini kemungkinan dibuat dengan aturan skor versi sebelumnya. "
                "Angka tersimpan tetap yang berlaku."
            ),
        },
        "cited_atoms": sorted(cited),
        "source_available": full_text is not None,
    }
