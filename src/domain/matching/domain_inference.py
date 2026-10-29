"""Domain-context implication: credit unstated-but-implied capabilities, conservatively (v2.2).

The Matcher entails a facet only from literal evidence. In the 19-CV run a backend engineer on a crypto
exchange and on a branchless-banking platform was scored as if database skills were unproven because no bullet
spelled out "PostgreSQL" or "MySQL", although transaction systems of that kind cannot run without a transactional
database. This module encodes a small, reviewable table of such implications.

Rules are deliberately weak: an implication can lift NOT_ENTAILED / UNKNOWN to PARTIAL at depth L1 only (never
ENTAILED), is grounded on real evidence atoms (experience/project bullets, never skill lists or summaries), and is
marked `rationale_code="DOMAIN_INFERENCE"` plus a candidate flag so reviewers can see and discount it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.agents.schemas.matcher import DepthLevel, FacetEvaluationResult, FacetVerdict

EVIDENCE_KINDS = ("exp_bullet", "project_bullet")
UPGRADABLE = (FacetVerdict.NOT_ENTAILED, FacetVerdict.UNKNOWN)


@dataclass(frozen=True)
class Implication:
    rule_id: str
    facet_terms: tuple[str, ...]  # the facet is about one of these
    evidence_terms: tuple[str, ...]  # the candidate worked on systems of this kind
    min_atoms: int = 1


IMPLICATIONS: tuple[Implication, ...] = (
    Implication(
        rule_id="transactional_db_from_transaction_systems",
        facet_terms=("database", "basis data", "sql", "postgresql", "mysql", "relasional", "relational"),
        evidence_terms=(
            "payment",
            "pembayaran",
            "fintech",
            "trading",
            "perdagangan aset",
            "bank",
            "banking",
            "perbankan",
            "transaksi",
            "transaction",
            "deposit",
            "withdraw",
            "penarikan",
            "order matching",
            "ledger",
            "billing",
            "checkout",
            "saldo",
            "wallet",
            "dompet digital",
            "settlement",
        ),
    ),
)


def _text(atom: Any) -> str:
    return str(
        getattr(atom, "text_redacted", None) or (atom.get("text_redacted") if isinstance(atom, dict) else "") or ""
    ).lower()


def _kind(atom: Any) -> str:
    return str(getattr(atom, "kind", None) or (atom.get("kind") if isinstance(atom, dict) else "") or "")


def _key(atom: Any) -> str:
    return str(getattr(atom, "atom_key", None) or (atom.get("atom_key") if isinstance(atom, dict) else "") or "")


def apply_domain_inference(
    judgments: list[FacetEvaluationResult],
    facets_by_key: dict[str, str],
    atoms: list[Any],
    max_support: int = 3,
) -> tuple[list[FacetEvaluationResult], list[str]]:
    """Returns (judgments with implications applied, flags). `facets_by_key` maps facet_key -> hypothesis text."""
    evidence_atoms = [a for a in atoms if _kind(a) in EVIDENCE_KINDS]
    out: list[FacetEvaluationResult] = []
    flags: list[str] = []
    for j in judgments:
        hypothesis = facets_by_key.get(j.facet_key, "").lower()
        upgraded = None
        if j.verdict in UPGRADABLE and hypothesis:
            for rule in IMPLICATIONS:
                if not any(t in hypothesis for t in rule.facet_terms):
                    continue
                support = [a for a in evidence_atoms if any(t in _text(a) for t in rule.evidence_terms)]
                if len(support) >= rule.min_atoms:
                    keys = [_key(a) for a in support[:max_support]]
                    upgraded = j.model_copy(
                        update={
                            "verdict": FacetVerdict.PARTIAL,
                            "depth_level": DepthLevel.L1,
                            "support_atoms": keys,
                            "rationale_code": "DOMAIN_INFERENCE",
                            "analysis": (
                                f"Disimpulkan dari konteks sistem ({rule.rule_id}): bukti kerja pada sistem "
                                f"transaksional tanpa menyebut teknologi basis data; hanya PARTIAL. {j.analysis}"
                            )[:600],
                        }
                    )
                    flags.append(f"DOMAIN_INFERENCE:{j.facet_key}")
                    break
        out.append(upgraded or j)
    return out, flags
