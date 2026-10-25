"""Agents module (v2.1)."""

from src.agents.critic import (
    build_critic_user_prompt,
    evaluate_escalation_triggers,
    load_critic_system_prompt,
    resolve_disagreements,
    resolve_facet_dispute,
    run_critic_agent,
)
from src.agents.matcher import (
    build_matcher_user_prompt,
    load_matcher_system_prompt,
    run_matcher_agent,
    save_matcher_results,
)
from src.agents.profiler import run_profiler_agent, save_profiler_results
from src.agents.schemas.critic import (
    CriticFacetReview,
    CriticInput,
    CriticOutput,
    VerdictAction,
)
from src.agents.schemas.matcher import (
    DepthLevel,
    FacetEvaluationInput,
    FacetEvaluationResult,
    FacetVerdict,
    MatcherBatchOutput,
)
from src.agents.schemas.profiler import (
    AtomTag,
    DomainAllocation,
    DomainAllocationLevel,
    EvidenceType,
    ProfilerExperience,
    ProfilerOutput,
)
from src.agents.validators import validate_profiler_output

__all__ = [
    "AtomTag",
    "CriticFacetReview",
    "CriticInput",
    "CriticOutput",
    "DepthLevel",
    "DomainAllocation",
    "DomainAllocationLevel",
    "EvidenceType",
    "FacetEvaluationInput",
    "FacetEvaluationResult",
    "FacetVerdict",
    "MatcherBatchOutput",
    "ProfilerExperience",
    "ProfilerOutput",
    "VerdictAction",
    "build_critic_user_prompt",
    "build_matcher_user_prompt",
    "evaluate_escalation_triggers",
    "load_critic_system_prompt",
    "load_matcher_system_prompt",
    "resolve_disagreements",
    "resolve_facet_dispute",
    "run_critic_agent",
    "run_matcher_agent",
    "run_profiler_agent",
    "save_matcher_results",
    "save_profiler_results",
    "validate_profiler_output",
]
