"""Copilot HR: structured tools over screening results with citation enforcement (v2.2).

This is deliberately not RAG over raw CV text. The recruiter-facing assistant answers from four tools that read
the results the pipeline already produced (facet judgments, evidence atoms, month ledgers, critic reviews):

    get_atoms(candidate, facet)      evidence atoms and their verbatim redacted text
    compare(candidates, requirement) side-by-side states, depth and supporting atoms
    timeline(candidate, domain)      contiguous work periods contributing to a domain duration
    explain_score(candidate)         why a candidate got this band and score

Rules enforced in code, whatever model (if any) writes the prose around the tools:
- every sentence of an answer must cite an existing atom id as `[atom_key]`, or state explicitly that no
  evidence exists; anything else is stripped (`enforce_citations`);
- queries that ask to infer a protected attribute are refused (`check_query`);
- atoms are untrusted data: tool output is cleaned of control characters and never executed or interpreted;
- candidates are shown by short id, never by file name (file names often contain the applicant's name).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from src.domain.protected_attributes import scrub_protected_attributes
from src.domain.text_hygiene import neutralize_control_chars

CITATION = re.compile(r"\[([A-Za-z0-9_.\-]+)\]")
ABSTAIN = re.compile(
    r"\b(?:tidak\s+ada\s+bukti|bukti\s+tidak\s+(?:ditemukan|cukup)|no\s+evidence|not\s+enough\s+evidence)\b",
    re.IGNORECASE,
)
REMOVED = "[kalimat dihapus: tanpa sitasi atom yang valid]"
REFUSAL = (
    "Pertanyaan ini meminta kesimpulan tentang atribut terlindungi ({cats}). Sistem tidak menyimpulkan atribut "
    "tersebut dan tidak menggunakannya dalam penilaian. Ajukan pertanyaan tentang kemampuan, pengalaman, atau bukti kerja."
)
PROTECTED_CATEGORIES = {"RELIGION", "GENDER", "AGE", "BIRTH", "MARITAL", "ETHNICITY", "PHYSICAL"}


def short_id(candidate_id: str) -> str:
    return str(candidate_id).replace("-", "")[:8]


def _clean(text: Any) -> str:
    return neutralize_control_chars(str(text or ""))


@dataclass
class CopilotStore:
    """In-memory view of one screening run, built from the rankings payload (or the pipeline result)."""

    candidates: dict[str, dict[str, Any]] = field(default_factory=dict)
    requirements: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_rankings_payload(
        cls, payload: dict[str, Any], requirements: list[dict[str, Any]] | None = None
    ) -> CopilotStore:
        store = cls(requirements={r["requirement_id"]: r for r in (requirements or [])})
        for row in payload.get("rankings", []):
            cid = str(row.get("candidate_id") or row.get("cv_id"))
            store.candidates[cid] = row
        return store

    # ------------------------------------------------------------------ lookups
    def candidate(self, candidate_id: str) -> dict[str, Any]:
        key = self._resolve(candidate_id)
        return self.candidates[key]

    def _resolve(self, candidate_id: str) -> str:
        if candidate_id in self.candidates:
            return candidate_id
        matches = [c for c in self.candidates if short_id(c) == candidate_id or c.startswith(candidate_id)]
        if len(matches) != 1:
            raise KeyError(f"unknown candidate {candidate_id!r}")
        return matches[0]

    def atoms_of(self, candidate_id: str) -> dict[str, dict[str, Any]]:
        row = self.candidate(candidate_id)
        return {a["atom_key"]: a for a in row.get("grounding_atoms", []) if a.get("atom_key")}

    def all_atom_keys(self, candidate_ids: list[str] | None = None) -> set[str]:
        ids = candidate_ids if candidate_ids else list(self.candidates)
        keys: set[str] = set()
        for cid in ids:
            keys |= set(self.atoms_of(cid))
        return keys


def _judgment_view(j: dict[str, Any]) -> dict[str, Any]:
    verdict = str(j.get("verdict", "UNKNOWN")).split(".")[-1]
    return {
        "facet": j.get("facet_key"),
        "requirement": j.get("requirement_id"),
        "verdict": verdict,
        "depth": j.get("depth_level") or "L0",
        "atoms": list(j.get("support_atom_ids") or j.get("support_atoms") or []),
        "method": j.get("method"),
        "superseded_by_critic": bool(j.get("superseded_by_critic")),
    }


# ---------------------------------------------------------------------------------------------- tools
def get_atoms(
    store: CopilotStore, candidate_id: str, facet: str | None = None, kinds: list[str] | None = None, limit: int = 20
) -> dict[str, Any]:
    row = store.candidate(candidate_id)
    atoms = store.atoms_of(candidate_id)
    wanted: set[str] | None = None
    if facet:
        wanted = set()
        for j in row.get("facet_judgments", []):
            if j.get("facet_key") == facet:
                wanted |= set(j.get("support_atom_ids") or j.get("support_atoms") or [])
    out = []
    for key, a in atoms.items():
        if wanted is not None and key not in wanted:
            continue
        if kinds and a.get("kind") not in kinds:
            continue
        out.append(
            {
                "atom": key,
                "kind": a.get("kind"),
                "page": a.get("page"),
                "span": [a.get("char_start"), a.get("char_end")],
                "text": _clean(a.get("text_redacted")),
            }
        )
    return {
        "candidate": short_id(row.get("candidate_id") or candidate_id),
        "facet": facet,
        "atoms": out[: max(0, limit)],
        "truncated": len(out) > limit,
    }


def compare(store: CopilotStore, candidate_ids: list[str], requirement_id: str | None = None) -> dict[str, Any]:
    rows = []
    for cid in candidate_ids:
        row = store.candidate(cid)
        judgments = [
            _judgment_view(j)
            for j in row.get("facet_judgments", [])
            if requirement_id is None or j.get("requirement_id") == requirement_id
        ]
        states = row.get("requirement_states") or {}
        rows.append(
            {
                "candidate": short_id(row.get("candidate_id") or cid),
                "rank": row.get("rank"),
                "band": row.get("band"),
                "score": row.get("final_score"),
                "recommendation": row.get("recommendation"),
                "requirement_state": states.get(requirement_id) if requirement_id else states,
                "facets": judgments,
                "flags": sorted(row.get("flags") or []),
            }
        )
    return {"requirement": requirement_id, "rows": rows}


def timeline(store: CopilotStore, candidate_id: str, domain: str | None = None) -> dict[str, Any]:
    row = store.candidate(candidate_id)
    periods: list[dict[str, Any]] = []
    for dd in row.get("domain_durations", []):
        if domain and dd.get("domain") != domain:
            continue
        ledger = sorted(dd.get("month_ledger") or [], key=lambda m: m["month"])
        current: dict[str, Any] | None = None
        for m in ledger:
            ym, entry, weight = m["month"], m.get("contributing_entry"), m.get("weight", 1.0)
            if (
                current
                and current["entry"] == entry
                and current["weight"] == weight
                and _next_month(current["end"]) == ym
            ):
                current["end"] = ym
                current["months"] += 1
            else:
                if current:
                    periods.append(current)
                current = {
                    "domain": dd.get("domain"),
                    "entry": entry,
                    "weight": weight,
                    "start": ym,
                    "end": ym,
                    "months": 1,
                }
        if current:
            periods.append(current)
    return {
        "candidate": short_id(row.get("candidate_id") or candidate_id),
        "domain": domain,
        "periods": periods,
        "months_lo_hi": {
            dd["domain"]: [dd.get("months_lo"), dd.get("months_hi")]
            for dd in row.get("domain_durations", [])
            if not domain or dd.get("domain") == domain
        },
    }


def _next_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:7])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}"


def explain_score(store: CopilotStore, candidate_id: str) -> dict[str, Any]:
    row = store.candidate(candidate_id)
    atoms = store.atoms_of(candidate_id)
    facets = []
    for j in row.get("facet_judgments", []):
        view = _judgment_view(j)
        view["evidence"] = [
            {"atom": a, "text": _clean(atoms[a].get("text_redacted"))[:240]} for a in view["atoms"] if a in atoms
        ]
        facets.append(view)
    return {
        "candidate": short_id(row.get("candidate_id") or candidate_id),
        "band": row.get("band"),
        "score": row.get("final_score"),
        "recommendation": row.get("recommendation"),
        "requirement_states": row.get("requirement_states") or {},
        "facets": facets,
        "critic": [
            {
                "facet": c.get("facet_key"),
                "action": c.get("verdict_action"),
                "final": c.get("final_verdict"),
                "disagreement": c.get("is_disagreement"),
            }
            for c in row.get("critic_reviews", [])
        ],
        "flags": sorted(row.get("flags") or []),
    }


TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_atoms": get_atoms,
    "compare": compare,
    "timeline": timeline,
    "explain_score": explain_score,
}


# ---------------------------------------------------------------------------------------------- guardrails
def check_query(query: str) -> tuple[bool, str]:
    """(allowed, message). Refuses queries that ask to infer a protected attribute."""
    _, cats = scrub_protected_attributes(query or "")
    blocked = sorted(set(cats) & PROTECTED_CATEGORIES)
    if blocked:
        return False, REFUSAL.format(cats=", ".join(c.lower() for c in blocked))
    return True, ""


@dataclass
class CitationReport:
    ok: bool
    cleaned: str
    violations: list[dict[str, str]]


def enforce_citations(answer: str, store: CopilotStore, candidate_ids: list[str] | None = None) -> CitationReport:
    """Keeps only sentences that cite existing atoms (or abstain explicitly); strips the rest."""
    valid = store.all_atom_keys(candidate_ids)
    kept: list[str] = []
    violations: list[dict[str, str]] = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", _clean(answer).strip()):
        s = sentence.strip()
        if not s:
            continue
        cites = CITATION.findall(s)
        unknown = [c for c in cites if c not in valid]
        if ABSTAIN.search(s) and not unknown or cites and not unknown:
            kept.append(s)
        else:
            reason = "unknown_citation" if unknown else "no_citation"
            violations.append({"sentence": s, "reason": reason, "unknown": ", ".join(unknown)})
            kept.append(REMOVED)
    return CitationReport(ok=not violations, cleaned="\n".join(kept), violations=violations)
