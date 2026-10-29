"""Facets per requirement: judge only what each requirement is actually about (v2.2).

v2.1 gave every requirement, whatever its kind, the full facet template of the job's role. In the 19-CV
run all six criteria (years of experience, language, REST API, SQL database, clean code, payment gateway)
therefore depended on the same five facets: one weak facet pulled every criterion to PARTIAL (eight
candidates at exactly 50.0) and the Matcher re-judged identical facets once per criterion.

Rules (deterministic, conservative):
- ROLE_EQUIVALENCE / EXPERIENCE_DURATION statements of general role experience ("minimal N tahun sebagai
  <role>") keep the full role template: they really are about the whole role;
- other ROLE_EQUIVALENCE statements keep the template facets that share vocabulary with their text
  (nothing matching keeps the full template);
- every other kind (SKILL, RESPONSIBILITY, ACHIEVEMENT, EDUCATION, ...) gets one facet carrying the
  requirement's own text and concepts, so it is judged directly;
- kept facets become `core` for that requirement, because the requirement is specifically about them
  (a requirement narrowed to a non-core facet could never be evaluated);
- only facets that look auto-filled from a role template are replaced; facets written by a recruiter or by
  the JD compiler are left alone.
"""

from __future__ import annotations

import re
from typing import Any

from src.domain.requirements.facet_templates import ROLE_FACET_TEMPLATES
from src.domain.requirements.schemas import RequirementFacet, RequirementIR, RequirementSetIR

NARROWED_FLAG = "facets_narrowed_from"

_SYNONYMS = (
    ("basis data", "database"),
    ("kueri", "query"),
    ("pengujian", "testing"),
    ("otentikasi", "authentication"),
    ("otorisasi", "authorization"),
    ("keamanan", "security"),
    ("antrian", "queue"),
    ("performa", "performance"),
)

_STOP = {
    "dan",
    "atau",
    "yang",
    "dengan",
    "dalam",
    "untuk",
    "pada",
    "dari",
    "serta",
    "minimal",
    "mahir",
    "menguasai",
    "memahami",
    "pengalaman",
    "kemampuan",
    "berpengalaman",
    "salah",
    "satu",
    "bahasa",
    "implementasi",
    "integrasi",
    "merancang",
    "membangun",
    "mengimplementasikan",
    "pengelolaan",
    "pemodelan",
    "prinsip",
    "pihak",
    "ketiga",
    "contoh",
    "misalnya",
    "the",
    "and",
    "with",
    "for",
    "skill",
    "concept",
    "developer",
    "engineer",
    "backend",
    "frontend",
}

_YEARS = re.compile(r"\b\d+\s*(?:\+\s*)?(?:tahun|thn|years?|yrs?|bulan|months?)\b", re.IGNORECASE)


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    for src, dst in _SYNONYMS:
        lowered = lowered.replace(src, dst)
    return {t for t in re.findall(r"[a-z0-9+#]{3,}", lowered) if t not in _STOP}


def _facet_vocabulary(facet: RequirementFacet) -> set[str]:
    words = _tokens(facet.hypothesis)
    for concept in facet.concepts:
        words |= _tokens(concept.split(":", 1)[-1].replace("_", " "))
    return words


def is_general_role_statement(req: RequirementIR) -> bool:
    """True for 'minimum N years as <role>' statements that must see the whole role template."""
    if req.duration_policy is not None and req.duration_policy.min_months > 0:
        return True
    return bool(_YEARS.search(req.description or ""))


ROLE_KINDS = ("ROLE_EQUIVALENCE", "EXPERIENCE_DURATION")


def _norm_hypothesis(text: str) -> str:
    return " ".join(str(text).lower().split())


_TEMPLATE_SETS: list[frozenset[tuple[str, str]]] = [
    frozenset((t["facet_key"], _norm_hypothesis(t["hypothesis"])) for t in templates)
    for templates in ROLE_FACET_TEMPLATES.values()
]


def looks_like_template(facets: list[RequirementFacet]) -> bool:
    """True when `facets` are exactly one of the role templates (i.e. auto-filled, not authored)."""
    if not facets:
        return False
    return frozenset((f.facet_key, _norm_hypothesis(f.hypothesis)) for f in facets) in _TEMPLATE_SETS


def own_facet(req: RequirementIR) -> RequirementFacet:
    """A single core facet that carries the requirement's own text, for requirements judged directly."""
    concepts = [c for c in req.concepts if ":" in c][:8]
    return RequirementFacet(
        facet_key=f"{req.requirement_id}.F1",
        hypothesis=(req.description or req.source_text or req.requirement_id).strip(),
        core=True,
        concepts=concepts,
        depth_floor=req.depth_floor or "L1",
        accepted_evidence=list(req.accepted_evidence) or ["T1", "T2", "T3", "T4"],
    )


def default_facets(req: RequirementIR) -> list[RequirementFacet]:
    """Facets a requirement should be judged on, given its kind and text."""
    if (req.kind or "").upper() in ROLE_KINDS:
        return narrow_facets(req)
    return [own_facet(req)]


def narrow_facets(req: RequirementIR) -> list[RequirementFacet]:
    """Returns the template facets a role requirement should be judged on (possibly all of them)."""
    facets = list(req.facets or [])
    if len(facets) < 2 or is_general_role_statement(req):
        return facets

    req_words = _tokens(" ".join([req.description or "", req.source_text or ""]))
    scored = [(len(req_words & _facet_vocabulary(f)), f) for f in facets]
    best = max(score for score, _ in scored)
    if best == 0:
        return facets

    keep = [f for score, f in scored if score >= max(1, best * 0.5)]
    if len(keep) == len(facets):
        return facets
    return [f.model_copy(update={"core": True}) for f in keep]


def apply_facet_narrowing(req_set: RequirementSetIR) -> int:
    """Narrows facets in place (idempotent). Returns the number of requirements that changed."""
    changed = 0
    for req in req_set.requirements:
        if NARROWED_FLAG in req.params or not looks_like_template(req.facets):
            continue
        replacement = default_facets(req)
        if [f.facet_key for f in replacement] != [f.facet_key for f in req.facets]:
            req.params[NARROWED_FLAG] = len(req.facets)
            req.facets = replacement
            changed += 1
    return changed


def facet_signature(facet: RequirementFacet | dict[str, Any]) -> tuple[str, str, tuple[str, ...]]:
    """Identity of a facet for judgment reuse: same key, hypothesis and concepts => same judgment."""
    if isinstance(facet, dict):
        key, hyp, concepts = facet.get("facet_key", ""), facet.get("hypothesis", ""), facet.get("concepts", [])
    else:
        key, hyp, concepts = facet.facet_key, facet.hypothesis, facet.concepts
    return (str(key), " ".join(str(hyp).lower().split()), tuple(sorted(str(c) for c in concepts)))
