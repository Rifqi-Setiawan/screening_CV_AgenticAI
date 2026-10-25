"""Pydantic schemas for Profiler Agent input and output (v2.1)."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainAllocationLevel(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    INCIDENTAL = "INCIDENTAL"


class EvidenceType(str, Enum):
    USAGE = "USAGE"
    OWNERSHIP = "OWNERSHIP"
    LEADERSHIP = "LEADERSHIP"
    MENTION_ONLY = "MENTION_ONLY"


class DomainAllocation(BaseModel):
    """Domain allocation with allocation level and supporting evidence atoms."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(description="Domain name e.g. frontend, backend, fullstack, data, qa, devops")
    level: DomainAllocationLevel = Field(description="Allocation level: PRIMARY, SECONDARY, or INCIDENTAL")
    support_atom_ids: list[str] = Field(
        default_factory=list,
        description="List of atom_key or UUID strings supporting this domain allocation",
    )
    code_atom_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Ratio of supporting evidence atoms in this domain relative to experience atom total",
    )
    flags: list[str] = Field(default_factory=list, description="Diagnostic flags e.g. INCONSISTENT_ALLOCATION")


class ProfilerExperience(BaseModel):
    """Profile experience entry classified by the Profiler Agent."""

    model_config = ConfigDict(extra="forbid")

    entry_ref: str = Field(description="Reference key of the experience entry e.g. exp_0, exp_1")
    title_raw: str | None = Field(default=None, description="Raw job title extracted from CV")
    employment_type: str | None = Field(
        default="unknown",
        description="Employment type: full-time, part-time, internship, contract, freelance, or unknown",
    )
    date_text_start: str | None = Field(default=None, description="Raw start date text e.g. Jan 2020")
    date_text_end: str | None = Field(default=None, description="Raw end date text e.g. Des 2022, present")
    is_current: bool = Field(default=False, description="True if currently active position")
    domain_allocations: list[DomainAllocation] = Field(
        default_factory=list,
        description="Domain allocations for this position",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_allocations_key(cls, data: Any) -> Any:
        if isinstance(data, dict) and "domain_allocation" in data and "domain_allocations" not in data:
            data["domain_allocations"] = data.pop("domain_allocation")
        return data


class AtomTag(BaseModel):
    """Capability and evidence tagging for a single Evidence Atom."""

    model_config = ConfigDict(extra="forbid")

    atom_id: str = Field(description="Atom key (e.g. exp_0_bullet_0) or UUID string of the evidence atom")
    domains: list[str] = Field(default_factory=list, description="Domains identified in this atom")
    activities: list[str] = Field(default_factory=list, description="Activities or actions performed")
    concepts: list[str] = Field(
        default_factory=list,
        description="Ontology concept IDs (e.g. skill:python, skill:react) or unmapped:<term>",
    )
    evidence_type: EvidenceType = Field(
        default=EvidenceType.USAGE,
        description="Evidence level: USAGE, OWNERSHIP, LEADERSHIP, MENTION_ONLY",
    )
    impact_quantified: bool = Field(default=False, description="True if metric or quantifiable outcome is present")
    impact_kind: str | None = Field(
        default=None,
        description="Impact kind: performance, scale, revenue, cost, reliability, or null",
    )


class ProfilerOutput(BaseModel):
    """Root output schema of the Profiler Agent."""

    model_config = ConfigDict(extra="forbid")

    experiences: list[ProfilerExperience] = Field(
        default_factory=list,
        description="Classified experience entries with domain allocations",
    )
    atom_tags: list[AtomTag] = Field(
        default_factory=list,
        description="Tagged evidence atoms with capability concepts and evidence levels",
    )
    flags: list[str] = Field(default_factory=list, description="Global candidate profile diagnostics")
