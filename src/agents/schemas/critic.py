"""Pydantic schemas for Critic Agent input and output (v2.1).

Implements Section C2 S8 and C5 of the Blueprint:
- S8 Critic Agent: Adversarial Multi-Model verification.
- Two-step reasoning: Field `analysis` (freeform reasoning) MUST appear BEFORE
  `verdict_action` and `final_verdict` to enforce skeptical evidence scrutiny.
- VerdictAction: CONFIRM, DOWNGRADE, UPGRADE.
- Identifies disputes and marks AGENT_DISAGREEMENT for manual review fallback.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.agents.schemas.matcher import DepthLevel, FacetEvaluationResult, FacetVerdict
from src.domain.atoms import EvidenceAtom


class VerdictAction(str, Enum):
    CONFIRM = "CONFIRM"
    DOWNGRADE = "DOWNGRADE"
    UPGRADE = "UPGRADE"


class CriticFacetReview(BaseModel):
    """Adversarial critique and verdict for an individual requirement facet.

    CRITICAL (Blueprint v2.1 Section C2 S8 & R1):
    Field `analysis` MUST precede `verdict_action` and `final_verdict` to ensure
    adversarial evidence deconstruction before classification.
    """

    model_config = ConfigDict(extra="forbid")

    facet_key: str = Field(description="Unique facet identifier (e.g. F1, F2)")
    # analysis field MUST precede verdict_action and final_verdict
    analysis: str = Field(
        description="Freeform adversarial analysis testing literal evidence atoms against claims before verdict."
    )
    verdict_action: VerdictAction = Field(
        description="Adversarial action: CONFIRM (uphold Matcher), DOWNGRADE (weaken), UPGRADE (strengthen with verified atom)"
    )
    final_verdict: FacetVerdict = Field(
        description="Final entailment verdict after adversarial review: ENTAILED, PARTIAL, NOT_ENTAILED, CONTRADICTED, UNKNOWN"
    )
    reasoning: str = Field(
        default="",
        description="Structured rationale explaining why the verdict action was chosen",
    )
    original_verdict: FacetVerdict | None = Field(
        default=None,
        description="Original verdict from Matcher Agent prior to review",
    )
    depth_level: DepthLevel = Field(
        default=DepthLevel.L0,
        description="Assessed competency depth level L0..L4",
    )
    support_atoms: list[str] = Field(
        default_factory=list,
        description="Atom keys literally supporting the final verdict",
    )
    is_disagreement: bool = Field(
        default=False,
        description="True if Critic disagreed with Matcher (e.g. DOWNGRADE, UPGRADE, or verdict change)",
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Diagnostic flags e.g. KEYWORD_STUFFING_SUSPECT, T0_CEILING_ENFORCED, WEAK_CLAIM_DOWNGRADED",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_review(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)
        # Normalize support_atoms aliases
        if "support_atoms" not in d:
            if "support_atom_ids" in d:
                d["support_atoms"] = d.pop("support_atom_ids")
            elif "atoms" in d:
                d["support_atoms"] = d.pop("atoms")

        # Normalize verdict_action
        if "verdict_action" in d and isinstance(d["verdict_action"], str):
            d["verdict_action"] = d["verdict_action"].strip().upper()

        # Normalize final_verdict
        if "final_verdict" in d and isinstance(d["final_verdict"], str):
            d["final_verdict"] = d["final_verdict"].strip().upper()

        # Normalize original_verdict
        if "original_verdict" in d and isinstance(d["original_verdict"], str):
            d["original_verdict"] = d["original_verdict"].strip().upper()

        # Normalize depth_level
        if "depth_level" in d and isinstance(d["depth_level"], str):
            d["depth_level"] = d["depth_level"].strip().upper()

        # Fill default reasoning from analysis if omitted
        if not d.get("reasoning") and d.get("analysis"):
            d["reasoning"] = str(d["analysis"])[:200]

        return d


class CriticInput(BaseModel):
    """Input payload provided to the Critic Agent for adversarial verification."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(description="Unique candidate identifier")
    judgments: list[FacetEvaluationResult | dict[str, Any]] = Field(
        default_factory=list,
        description="Initial facet judgments produced by Matcher Agent",
    )
    escalation_triggers: list[str] = Field(
        default_factory=list,
        description="Active escalation triggers e.g. ['E1', 'E2', 'E4']",
    )
    atoms: list[EvidenceAtom | dict[str, Any]] = Field(
        default_factory=list,
        description="Evidence atoms extracted for this candidate",
    )
    requirement_scores: dict[str, Any] = Field(
        default_factory=dict,
        description="Aggregated requirement results or score summary",
    )
    raw_title: str | None = Field(
        default=None,
        description="Candidate's raw job title (context_only, weak prior)",
    )
    facets_to_review: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Target qualification facets undergoing adversarial review",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context such as NLI results or PII flags",
    )


class CriticOutput(BaseModel):
    """Output container produced by the Critic Agent."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(description="Unique candidate identifier")
    facet_reviews: list[CriticFacetReview] = Field(
        default_factory=list,
        description="List of adversarial facet reviews",
    )
    overall_reasoning: str | None = Field(
        default=None,
        description="Overall synthesis of candidate qualifications and adversarial findings",
    )
    escalation_triggers: list[str] = Field(
        default_factory=list,
        description="Escalation triggers that prompted or were confirmed by this review",
    )
    has_disagreement: bool = Field(
        default=False,
        description="True if one or more facet judgments resulted in dispute with Matcher",
    )
    disagreement_flags: list[str] = Field(
        default_factory=list,
        description="Flags identifying specific disagreements e.g. AGENT_DISAGREEMENT, DOWNGRADE:F1",
    )
    final_recommendation: str | None = Field(
        default=None,
        description="Recommended routing e.g. MANUAL_CHECK when AGENT_DISAGREEMENT is present",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_critic_output(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)
        if "facet_reviews" not in d:
            if "reviews" in d:
                d["facet_reviews"] = d.pop("reviews")
            elif "evaluations" in d:
                d["facet_reviews"] = d.pop("evaluations")
            elif "results" in d:
                d["facet_reviews"] = d.pop("results")

        return d

    def get_review(self, facet_key: str) -> CriticFacetReview | None:
        """Finds review for a given facet key."""
        for rev in self.facet_reviews:
            if rev.facet_key == facet_key:
                return rev
        return None
