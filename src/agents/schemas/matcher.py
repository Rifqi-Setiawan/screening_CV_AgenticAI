"""Pydantic schemas for Matcher Agent input and output (v2.1).

Implements Directional Entailment schemas as specified in Blueprint Section C2, C3, and R1:
- R1 Rule: Field `analysis` (<= 60 tokens) MUST be positioned BEFORE `verdict`
  to enforce intermediate reasoning grounding before discrete classification.
- Evaluates whether literal evidence in atoms entails qualification facets.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FacetVerdict(str, Enum):
    ENTAILED = "ENTAILED"
    PARTIAL = "PARTIAL"
    NOT_ENTAILED = "NOT_ENTAILED"
    CONTRADICTED = "CONTRADICTED"
    UNKNOWN = "UNKNOWN"


class DepthLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class FacetEvaluationInput(BaseModel):
    """Input payload representing an atomic qualification facet to be evaluated by Matcher."""

    model_config = ConfigDict(extra="forbid")

    facet_key: str = Field(description="Unique facet identifier (e.g. F1, F2)")
    hypothesis: str = Field(description="Atomic capability statement to test against evidence atoms")
    core: bool = Field(default=True, description="True for core facets mandatory for role equivalence")
    concepts: list[str] = Field(
        default_factory=list,
        description="Ontology concept IDs associated with this facet (e.g. skill:react)",
    )
    candidate_atoms: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top-K evidence atoms retrieved for this facet",
    )
    raw_title: str | None = Field(
        default=None,
        description="Candidate's raw job title provided strictly as context_only (weak prior)",
    )
    depth_floor: str = Field(
        default="L1",
        description="Minimum competency depth level expected for this facet (L0..L4)",
    )


class FacetEvaluationResult(BaseModel):
    """Evaluation result for an atomic requirement facet.

    CRITICAL (R1 Blueprint v2.1): The `analysis` field MUST be defined and serialized
    BEFORE `verdict` to enforce reasoning tokens before discrete classification tokens.
    """

    model_config = ConfigDict(extra="forbid")

    facet_key: str = Field(description="Unique facet identifier (e.g. F1, F2)")
    # analysis field MUST precede verdict (R1)
    analysis: str = Field(
        description="Concise literal evaluation of evidence vs hypothesis (<= 60 tokens). First field for R1 reasoning."
    )
    verdict: FacetVerdict = Field(
        description="Entailment verdict: ENTAILED, PARTIAL, NOT_ENTAILED, CONTRADICTED, UNKNOWN"
    )
    support_atoms: list[str] = Field(
        default_factory=list,
        description="List of atom_key identifiers that literally support this verdict",
    )
    depth_level: DepthLevel = Field(
        default=DepthLevel.L0,
        description="Demonstrated competency depth level: L0 (none/mention), L1 (basic), L2 (practitioner), L3 (expert), L4 (principal)",
    )
    rationale_code: str = Field(
        default="DIRECT_EVIDENCE",
        description="Standardized rationale classification code e.g. DIRECT_EVIDENCE, PARTIAL_EVIDENCE, NO_EVIDENCE, TITLE_CONTEXT_MISMATCH",
    )
    needs_more_context: bool = Field(
        default=False,
        description="True if neighboring atoms in the same experience entry are needed to evaluate this facet",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)
        # Support aliases
        if "support_atoms" not in d and "support_atom_ids" in d:
            d["support_atoms"] = d.pop("support_atom_ids")
        elif "support_atoms" not in d and "atoms" in d:
            d["support_atoms"] = d.pop("atoms")

        # Normalize verdict case
        if "verdict" in d and isinstance(d["verdict"], str):
            d["verdict"] = d["verdict"].strip().upper()

        # Normalize depth_level case
        if "depth_level" in d and isinstance(d["depth_level"], str):
            d["depth_level"] = d["depth_level"].strip().upper()

        return d


class MatcherBatchOutput(BaseModel):
    """Output container for a batch of evaluated facets."""

    model_config = ConfigDict(extra="forbid")

    evaluations: list[FacetEvaluationResult] = Field(
        default_factory=list,
        description="List of facet evaluation results",
    )
    flags: list[str] = Field(
        default_factory=list,
        description="Diagnostic flags e.g. TITLE_CONTEXT_MISMATCH, NEEDS_MORE_CONTEXT_TRIGGERED",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_batch(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        d = dict(data)
        if "evaluations" not in d:
            if "results" in d:
                d["evaluations"] = d.pop("results")
            elif "judgments" in d:
                d["evaluations"] = d.pop("judgments")
            elif "facet_evaluations" in d:
                d["evaluations"] = d.pop("facet_evaluations")

        return d

    def get_evaluation(self, facet_key: str) -> FacetEvaluationResult | None:
        """Finds evaluation result for a specific facet key."""
        for ev in self.evaluations:
            if ev.facet_key == facet_key:
                return ev
        return None
