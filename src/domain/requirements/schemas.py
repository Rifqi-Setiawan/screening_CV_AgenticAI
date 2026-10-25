"""Pydantic schemas for RequirementIR, Facet Decomposition, and Duration Policy (v2.1).

Defines the Intermediate Representation (IR) for job requirements, atomic facets,
and duration policies as specified in C3 & C9 of the Blueprint.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.temporal.weighted_union import (
    DEFAULT_ALLOC_WEIGHTS,
    DEFAULT_EMP_WEIGHTS,
    DurationPolicy,
)


class DurationPolicySchema(BaseModel):
    """Configurable duration weighting policy and minimum tenure threshold."""

    model_config = ConfigDict(extra="allow")

    alloc_weights: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_ALLOC_WEIGHTS),
        description="Weights by experience domain allocation level (PRIMARY, SECONDARY, INCIDENTAL)",
    )
    emp_weights: dict[str, float] = Field(
        default_factory=lambda: dict(DEFAULT_EMP_WEIGHTS),
        description="Weights by employment type (full-time, part-time, internship, freelance)",
    )
    recency_window_months: int | None = Field(
        default=None,
        description="Optional recency cutoff window in months prior to as_of date",
    )
    min_months: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum accumulated weighted tenure in months required to satisfy requirement",
    )
    target_domain: str | None = Field(
        default=None,
        description="Specific domain name to accumulate calendar union duration against",
    )

    def to_duration_policy(self) -> DurationPolicy:
        """Converts to the temporal engine's runtime DurationPolicy dataclass."""
        return DurationPolicy(
            alloc_weights=dict(self.alloc_weights),
            emp_weights=dict(self.emp_weights),
            recency_window_months=self.recency_window_months,
        )

    def compute_hash(self) -> str:
        """Computes deterministic SHA256 digest for audit and domain_durations tracking."""
        canonical = {
            "alloc_weights": {k: float(v) for k, v in sorted(self.alloc_weights.items())},
            "emp_weights": {k: float(v) for k, v in sorted(self.emp_weights.items())},
            "min_months": float(self.min_months),
            "recency_window_months": self.recency_window_months,
            "target_domain": self.target_domain,
        }
        raw = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class RequirementFacet(BaseModel):
    """Atomic evaluable facet decomposed from a high-level job requirement."""

    model_config = ConfigDict(extra="allow")

    facet_key: str = Field(description="Unique facet identifier within requirement (e.g. F1, F2)")
    hypothesis: str = Field(description="Testable atomic capability hypothesis in natural language")
    core: bool = Field(
        default=True,
        description="True for core facets mandatory for role equivalence, False for supporting facets",
    )
    concepts: list[str] = Field(
        default_factory=list,
        description="Ontology concept IDs associated with this facet (e.g. skill:react)",
    )
    depth_floor: str | None = Field(
        default=None,
        description="Optional facet-specific depth floor override (e.g. L1, L2)",
    )
    accepted_evidence: list[str] = Field(
        default_factory=lambda: ["T1", "T2", "T3", "T4"],
        description="Accepted evidence tiers for this facet (T0..T4)",
    )

    @field_validator("facet_key")
    @classmethod
    def validate_facet_key(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("facet_key cannot be empty")
        return s

    @field_validator("hypothesis")
    @classmethod
    def validate_hypothesis(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("hypothesis cannot be empty")
        return s


class RequirementIR(BaseModel):
    """Structured Intermediate Representation (IR) for an evaluable job requirement."""

    model_config = ConfigDict(extra="allow")

    requirement_id: str = Field(description="Unique requirement identifier within the JD (e.g. REQ-01)")
    description: str = Field(description="Natural language statement of the qualification")
    category: str = Field(
        default="EXPERIENCE",
        description="Evaluation category: EXPERIENCE, HARD_SKILLS, EDUCATION_CERT, ACHIEVEMENT",
    )
    kind: str = Field(
        default="ROLE_EQUIVALENCE",
        description="Qualification kind: ROLE_EQUIVALENCE, EXPERIENCE_DURATION, SKILL, RESPONSIBILITY, EDUCATION, CERTIFICATION",
    )
    importance: Literal["MUST_HAVE", "STRONG_PREFERENCE", "NICE_TO_HAVE"] = Field(
        default="MUST_HAVE",
        description="Strictness priority level",
    )
    weight: float = Field(
        default=10.0,
        ge=0.0,
        le=100.0,
        description="Normalized scoring weight",
    )
    concepts: list[str] = Field(
        default_factory=list,
        description="Capability ontology concepts targeted by this requirement",
    )
    target_domains: list[str] = Field(
        default_factory=list,
        description="Target capability domains evaluated (e.g. ['frontend'])",
    )
    duration_policy: DurationPolicySchema | None = Field(
        default=None,
        description="Explicit calendar union tenure duration policy",
    )
    accepted_evidence: list[str] = Field(
        default_factory=lambda: ["T1", "T2", "T3", "T4"],
        description="Permissible evidence tiers (T0: mention, T1: project, T2: exp bullet, T3: ownership, T4: quantified impact)",
    )
    depth_floor: str = Field(
        default="L1",
        description="Minimum required competency depth level (L0..L4)",
    )
    facets: list[RequirementFacet] = Field(
        default_factory=list,
        description="Atomic decomposed facets evaluated by directional entailment",
    )
    hard_filter: bool = Field(
        default=False,
        description="Whether failure triggers an eligibility gate violation flag",
    )
    source_text: str = Field(
        default="",
        description="Original raw excerpt or line from the job description",
    )
    lint_flags: list[str] = Field(
        default_factory=list,
        description="Compliance or policy violation flags detected by policy_linter",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional domain-specific operational parameters",
    )
    role_family: str | None = Field(
        default=None,
        description="Associated canonical role family identifier (e.g. frontend, backend)",
    )

    @property
    def core_facets(self) -> list[RequirementFacet]:
        """Returns all mandatory core facets."""
        return [f for f in self.facets if f.core]

    @property
    def supporting_facets(self) -> list[RequirementFacet]:
        """Returns non-core supplementary facets."""
        return [f for f in self.facets if not f.core]

    def get_facet(self, facet_key: str) -> RequirementFacet | None:
        """Look up facet by key."""
        for f in self.facets:
            if f.facet_key == facet_key:
                return f
        return None


class RequirementSetIR(BaseModel):
    """Complete compiled requirement set representing an entire Job Description."""

    model_config = ConfigDict(extra="allow")

    requirement_set_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    job_title: str = ""
    requirements: list[RequirementIR] = Field(default_factory=list)
    category_weights: dict[str, float] = Field(default_factory=dict)
    version: int = 1
