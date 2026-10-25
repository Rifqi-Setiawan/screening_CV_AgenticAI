"""RequirementIR, Facet Decomposition, and Duration Policy module (v2.1)."""

from src.domain.requirements.compiler import (
    compile_job_requirements_ir,
    decompose_role_to_facets,
    extract_duration_policy,
    load_requirement_ir_from_db,
    save_domain_duration_to_db,
    save_facet_judgment_to_db,
    save_requirement_ir_to_db,
)
from src.domain.requirements.facet_templates import (
    ROLE_FACET_TEMPLATES,
    get_facet_templates_for_role,
    resolve_role_family,
    sync_facet_templates_to_database,
)
from src.domain.requirements.schemas import (
    DurationPolicySchema,
    RequirementFacet,
    RequirementIR,
    RequirementSetIR,
)

__all__ = [
    "DurationPolicySchema",
    "RequirementFacet",
    "RequirementIR",
    "RequirementSetIR",
    "ROLE_FACET_TEMPLATES",
    "compile_job_requirements_ir",
    "decompose_role_to_facets",
    "extract_duration_policy",
    "get_facet_templates_for_role",
    "load_requirement_ir_from_db",
    "resolve_role_family",
    "save_domain_duration_to_db",
    "save_facet_judgment_to_db",
    "save_requirement_ir_to_db",
    "sync_facet_templates_to_database",
]
