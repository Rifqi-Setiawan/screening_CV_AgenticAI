"""Built-in facet templates for common engineering roles integrated with capability ontology (v2.1).

As per Blueprint Section C3, high-level roles are decomposed into atomic testable facets
(e.g. Frontend Developer -> F1..F5) rather than relying on brittle title string matching.
"""

from __future__ import annotations

import re
from typing import Any

from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import get_ontology_graph
from src.domain.requirements.schemas import RequirementFacet

# Canonical built-in facet templates for standard tech domains (C3 Blueprint)
ROLE_FACET_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "frontend": [
        {
            "facet_key": "F1",
            "hypothesis": "membangun komponen UI di framework SPA",
            "core": True,
            "concepts": [
                "skill:react",
                "skill:vue",
                "skill:angular",
                "skill:spa",
                "skill:nextjs",
                "concept:frontend_ui",
            ],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "F2",
            "hypothesis": "mengelola state sisi klien",
            "core": True,
            "concepts": ["skill:redux", "skill:vuex", "skill:zustand", "skill:mobx", "concept:state_management"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "F3",
            "hypothesis": "implementasi layout/slicing dari desain, responsive",
            "core": True,
            "concepts": ["skill:css", "skill:html", "skill:tailwind", "skill:sass", "concept:responsive_design"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "F4",
            "hypothesis": "integrasi API sisi klien",
            "core": False,
            "concepts": [
                "skill:rest_api",
                "skill:graphql",
                "skill:axios",
                "skill:fetch_api",
                "concept:api_integration",
            ],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "F5",
            "hypothesis": "testing/performa frontend",
            "core": False,
            "concepts": [
                "skill:jest",
                "skill:cypress",
                "skill:playwright",
                "concept:frontend_testing",
                "concept:web_performance",
            ],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
    ],
    "backend": [
        {
            "facet_key": "B1",
            "hypothesis": "merancang dan mengimplementasikan REST API / GraphQL / microservices",
            "core": True,
            "concepts": ["skill:rest_api", "skill:graphql", "skill:microservices", "concept:api_design"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "B2",
            "hypothesis": "pengelolaan database dan pemodelan skema data relasional / non-relasional",
            "core": True,
            "concepts": ["skill:postgresql", "skill:mysql", "skill:mongodb", "skill:redis", "concept:database_design"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "B3",
            "hypothesis": "implementasi logika bisnis dan otentikasi / otorisasi backend",
            "core": True,
            "concepts": ["concept:business_logic", "skill:jwt", "skill:oauth", "concept:authentication"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "B4",
            "hypothesis": "integrasi asynchronous messaging dan background job worker",
            "core": False,
            "concepts": ["skill:kafka", "skill:rabbitmq", "skill:celery", "concept:message_queue"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "B5",
            "hypothesis": "unit testing, automated integration testing, dan optimasi performa backend",
            "core": False,
            "concepts": ["skill:pytest", "skill:junit", "concept:backend_testing", "concept:caching"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
    ],
    "fullstack": [
        {
            "facet_key": "FS1",
            "hypothesis": "membangun antarmuka pengguna frontend dan komponen web interaktif",
            "core": True,
            "concepts": ["skill:react", "skill:vue", "skill:javascript", "skill:typescript", "concept:frontend_ui"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "FS2",
            "hypothesis": "merancang dan membangun backend API serta pengolahan server-side",
            "core": True,
            "concepts": ["skill:nodejs", "skill:python", "skill:fastapi", "skill:django", "skill:rest_api"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "FS3",
            "hypothesis": "interaksi database, persistensi data, dan perancangan skema data",
            "core": True,
            "concepts": ["skill:postgresql", "skill:mysql", "skill:mongodb", "concept:database_design"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "FS4",
            "hypothesis": "integrasi end-to-end, middleware, dan manajemen deployment/container",
            "core": False,
            "concepts": ["skill:docker", "concept:end_to_end", "concept:deployment"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "FS5",
            "hypothesis": "pengujian aplikasi menyeluruh (frontend + backend testing)",
            "core": False,
            "concepts": ["skill:jest", "skill:pytest", "concept:integration_testing"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
    ],
    "data": [
        {
            "facet_key": "D1",
            "hypothesis": "membangun dan memelihara pipeline data ETL / ELT batch atau streaming",
            "core": True,
            "concepts": ["skill:etl", "skill:spark", "skill:airflow", "concept:data_pipeline"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "D2",
            "hypothesis": "querying, transformasi, dan pemodelan data warehouse / data lake",
            "core": True,
            "concepts": ["skill:sql", "skill:dbt", "skill:bigquery", "skill:snowflake", "concept:data_modeling"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "D3",
            "hypothesis": "analisis data statistik atau pemodelan machine learning / predictive modeling",
            "core": True,
            "concepts": ["skill:python", "skill:pandas", "skill:scikit_learn", "concept:statistical_analysis"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "D4",
            "hypothesis": "orkestrasi alur kerja data dan otomatisasi data ingestion",
            "core": False,
            "concepts": ["skill:airflow", "skill:prefect", "skill:kafka", "concept:data_orchestration"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "D5",
            "hypothesis": "pembuatan dashboard visualisasi data dan metrik pelaporan analitik",
            "core": False,
            "concepts": ["skill:tableau", "skill:powerbi", "skill:metabase", "concept:data_visualization"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
    ],
    "qa": [
        {
            "facet_key": "QA1",
            "hypothesis": "perancangan test scenario, test case, dan test plan fungsional",
            "core": True,
            "concepts": ["concept:test_planning", "concept:test_cases", "concept:manual_testing"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "QA2",
            "hypothesis": "implementasi test automation untuk end-to-end web/mobile atau API",
            "core": True,
            "concepts": [
                "skill:selenium",
                "skill:cypress",
                "skill:playwright",
                "skill:postman",
                "concept:test_automation",
            ],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "QA3",
            "hypothesis": "pelaporan cacat perangkat lunak (defect tracking) dan verifikasi perbaikan bug",
            "core": True,
            "concepts": ["skill:jira", "concept:bug_tracking", "concept:regression_testing"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "QA4",
            "hypothesis": "pengujian performa, beban, atau keamanan perangkat lunak",
            "core": False,
            "concepts": ["skill:jmeter", "skill:k6", "concept:performance_testing"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "QA5",
            "hypothesis": "integrasi pengujian otomatis ke dalam pipeline CI/CD",
            "core": False,
            "concepts": ["skill:github_actions", "skill:jenkins", "concept:ci_cd_testing"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
    ],
    "devops": [
        {
            "facet_key": "DO1",
            "hypothesis": "mengelola containerization dan orkestrasi aplikasi",
            "core": True,
            "concepts": ["skill:docker", "skill:kubernetes", "concept:containerization"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "DO2",
            "hypothesis": "membangun dan memelihara automated CI/CD pipeline",
            "core": True,
            "concepts": ["skill:github_actions", "skill:gitlab_ci", "skill:jenkins", "concept:cicd_automation"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "DO3",
            "hypothesis": "mengelola cloud infrastructure (AWS / GCP / Azure) menggunakan IaC",
            "core": True,
            "concepts": ["skill:terraform", "skill:aws", "skill:gcp", "skill:azure", "concept:infrastructure_as_code"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "DO4",
            "hypothesis": "implementasi observability, logging, monitoring, dan alerting",
            "core": False,
            "concepts": ["skill:prometheus", "skill:grafana", "skill:elasticsearch", "concept:observability"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
        {
            "facet_key": "DO5",
            "hypothesis": "konfigurasi sistem operasi Linux, jaringan, dan keamanan infrastruktur",
            "core": False,
            "concepts": ["skill:linux", "concept:networking", "concept:infrastructure_security"],
            "depth_floor": "L1",
            "accepted_evidence": ["T1", "T2", "T3", "T4"],
        },
    ],
}

ROLE_REGEX_MAP: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"\b(?:frontend|front-end|front\s+end|ui\s+engineer|ui\s+developer|web\s+designer)\b", re.IGNORECASE
        ),
        "frontend",
    ),
    (
        re.compile(
            r"\b(?:backend|back-end|back\s+end|server-side|api\s+developer|golang\s+developer|python\s+developer)\b",
            re.IGNORECASE,
        ),
        "backend",
    ),
    (re.compile(r"\b(?:fullstack|full-stack|full\s+stack|web\s+developer)\b", re.IGNORECASE), "fullstack"),
    (
        re.compile(
            r"\b(?:data\s+scientist|data\s+engineer|data\s+analyst|bi\s+analyst|analytics\s+engineer|machine\s+learning|ml\s+engineer)\b",
            re.IGNORECASE,
        ),
        "data",
    ),
    (
        re.compile(r"\b(?:qa|quality\s+assurance|tester|test\s+engineer|sdet|automation\s+tester)\b", re.IGNORECASE),
        "qa",
    ),
    (
        re.compile(
            r"\b(?:devops|sre|site\s+reliability|platform\s+engineer|cloud\s+engineer|infrastructure\s+engineer)\b",
            re.IGNORECASE,
        ),
        "devops",
    ),
]


def resolve_role_family(text_or_title: str, ontology: OntologyGraph | None = None) -> str | None:
    """Resolves raw text or job title to a canonical role family.

    Checks capability ontology first (concept alias matching), then regex heuristics.
    """
    clean = text_or_title.strip().lower()

    # 1. Ontology graph lookup if provided or cached
    ont = ontology or get_ontology_graph()
    if ont:
        concept = ont.find_by_alias(clean)
        if concept:
            cid = concept.id.removeprefix("role:").lower()
            if cid in ROLE_FACET_TEMPLATES:
                return cid

    # 2. Direct key match
    if clean in ROLE_FACET_TEMPLATES:
        return clean

    # 3. Regex rule matching
    for pattern, role in ROLE_REGEX_MAP:
        if pattern.search(clean):
            return role

    return None


def get_facet_templates_for_role(
    role_or_title: str,
    ontology: OntologyGraph | None = None,
) -> list[RequirementFacet]:
    """Retrieves 5 atomic facet templates for the specified role.

    If role_or_title is e.g. 'Frontend Developer', resolves to 'frontend' and
    returns 5 RequirementFacet instances (F1..F5).
    """
    role = resolve_role_family(role_or_title, ontology=ontology) or "backend"
    templates = ROLE_FACET_TEMPLATES.get(role, ROLE_FACET_TEMPLATES["backend"])

    ont = ontology or get_ontology_graph()
    facets: list[RequirementFacet] = []

    for t in templates:
        concepts = list(t["concepts"])
        # If ontology available, optionally enrich with verified concepts
        if ont:
            enriched: set[str] = set(concepts)
            for c in concepts:
                # Add implied concepts
                implied = ont.get_implied_concepts(c, max_depth=2)
                enriched.update(implied)
            concepts = sorted(enriched)

        facets.append(
            RequirementFacet(
                facet_key=t["facet_key"],
                hypothesis=t["hypothesis"],
                core=t["core"],
                concepts=concepts,
                depth_floor=t.get("depth_floor", "L1"),
                accepted_evidence=t.get("accepted_evidence", ["T1", "T2", "T3", "T4"]),
            )
        )

    return facets


async def sync_facet_templates_to_database(conn: Any, version: str = "v1") -> int:
    """Synchronizes built-in facet templates into the facet_templates table.

    Returns the number of facet template rows created or updated.
    """
    count = 0
    async with conn.cursor() as cur:
        for role, templates in ROLE_FACET_TEMPLATES.items():
            role_concept = f"role:{role}"
            for t in templates:
                await cur.execute(
                    """
                    INSERT INTO facet_templates (version, role_concept, facet_key, hypothesis, core, concepts)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (version, role_concept, facet_key)
                    DO UPDATE SET
                        hypothesis = EXCLUDED.hypothesis,
                        core = EXCLUDED.core,
                        concepts = EXCLUDED.concepts
                    """,
                    (
                        version,
                        role_concept,
                        t["facet_key"],
                        t["hypothesis"],
                        t["core"],
                        t["concepts"],
                    ),
                )
                count += 1
        await conn.commit()
    return count
