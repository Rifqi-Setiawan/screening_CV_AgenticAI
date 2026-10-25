"""Job Description Compiler into RequirementIR with Facet Decomposition and Duration Policy (v2.1).

Implements Section C3 and S0 Graph B from Blueprint v2.1:
- Decomposes role requirements into atomic, testable facets (e.g. Frontend Developer -> F1..F5)
- Attaches explicit calendar union duration policies per domain
- Rule-based deterministic fallback + 9Router LLM adapter (ag/gemini-3.8-flash-high)
- Database persistence for requirements, requirement_facets, facet_judgments, and domain_durations
"""

from __future__ import annotations

import contextlib
import json
import re
import uuid
from typing import Any, Literal

from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import get_ontology_graph
from src.domain.pii import sanitize_contact_pii
from src.domain.policy_linter import lint_text
from src.domain.requirements.facet_templates import (
    get_facet_templates_for_role,
    resolve_role_family,
)
from src.domain.requirements.schemas import (
    DurationPolicySchema,
    RequirementFacet,
    RequirementIR,
    RequirementSetIR,
)
from src.infrastructure.config import settings
from src.infrastructure.gateway import ModelGateway, parse_llm_json
from src.infrastructure.logging import logger

DEFAULT_CATEGORY_WEIGHTS: dict[str, float] = {
    "EXPERIENCE": 40.0,
    "HARD_SKILLS": 30.0,
    "EDUCATION_CERT": 15.0,
    "ACHIEVEMENT": 15.0,
}

YEARS_REGEX = re.compile(
    r"\b(?:(?:minimal|min|at\s+least|pengalaman\s+minimal|pengalaman\s+min)\s+)?(\d+(?:[.,]\d+)?)\s*(?:-|s/?d|sampai|hingga)?\s*(\d+(?:[.,]\d+)?)?\s*(?:tahun|thn|th|years?|yrs?)\b",
    re.IGNORECASE,
)
MONTHS_REGEX = re.compile(
    r"\b(?:(?:minimal|min|at\s+least|pengalaman\s+minimal)\s+)?(\d+)\s*(?:bulan|bln|months?)\b",
    re.IGNORECASE,
)

MUST_HAVE_REGEX = re.compile(
    r"\b(?:wajib|harus|must|required|minimum|minimal|essential)\b",
    re.IGNORECASE,
)
NICE_TO_HAVE_REGEX = re.compile(
    r"\b(?:nilai\s+tambah|nice\s+to\s+have|plus|diutamakan|preferred|keuntungan)\b",
    re.IGNORECASE,
)


def determine_importance(
    line: str, default: str = "STRONG_PREFERENCE"
) -> Literal["MUST_HAVE", "STRONG_PREFERENCE", "NICE_TO_HAVE"]:
    """Determines requirement strictness from wording."""
    if MUST_HAVE_REGEX.search(line):
        return "MUST_HAVE"
    if NICE_TO_HAVE_REGEX.search(line):
        return "NICE_TO_HAVE"
    return "STRONG_PREFERENCE" if default == "STRONG_PREFERENCE" else "MUST_HAVE"


def extract_duration_policy(
    text: str,
    target_domain: str | None = None,
) -> DurationPolicySchema | None:
    """Extracts minimum tenure and builds DurationPolicySchema from text line."""
    # Check years first
    m_yr = YEARS_REGEX.search(text)
    if m_yr:
        num_str = m_yr.group(1).replace(",", ".")
        try:
            years = float(num_str)
            min_months = round(years * 12.0, 1)
            return DurationPolicySchema(min_months=min_months, target_domain=target_domain)
        except ValueError:
            pass

    # Check months
    m_mo = MONTHS_REGEX.search(text)
    if m_mo:
        try:
            months = float(m_mo.group(1))
            return DurationPolicySchema(min_months=months, target_domain=target_domain)
        except ValueError:
            pass

    return None


def decompose_role_to_facets(
    role_or_title: str,
    ontology: OntologyGraph | None = None,
) -> list[RequirementFacet]:
    """Decomposes a role qualification into atomic testable facets (C3 Blueprint).

    For example, 'Frontend Developer' decomposes into 5 facets:
      F1 [core] membangun komponen UI di framework SPA
      F2 [core] mengelola state sisi klien
      F3 [core] implementasi layout/slicing dari desain, responsive
      F4 [supp] integrasi API sisi klien
      F5 [supp] testing/performa frontend
    """
    return get_facet_templates_for_role(role_or_title, ontology=ontology)


# Fallback concept mappings for skill extraction
KNOWN_SKILL_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"\b(?:react|reactjs|react\.js)\b", re.IGNORECASE), "skill:react", "frontend"),
    (re.compile(r"\b(?:vue|vuejs|vue\.js)\b", re.IGNORECASE), "skill:vue", "frontend"),
    (re.compile(r"\b(?:angular)\b", re.IGNORECASE), "skill:angular", "frontend"),
    (re.compile(r"\b(?:next\.?js)\b", re.IGNORECASE), "skill:nextjs", "frontend"),
    (re.compile(r"\b(?:typescript|ts)\b", re.IGNORECASE), "skill:typescript", "frontend"),
    (re.compile(r"\b(?:javascript|js)\b", re.IGNORECASE), "skill:javascript", "frontend"),
    (re.compile(r"\b(?:css|css3|tailwind|sass|scss)\b", re.IGNORECASE), "skill:css", "frontend"),
    (re.compile(r"\b(?:python|fastapi|django|flask)\b", re.IGNORECASE), "skill:python", "backend"),
    (re.compile(r"\b(?:golang|go)\b", re.IGNORECASE), "skill:golang", "backend"),
    (re.compile(r"\b(?:postgresql|postgres)\b", re.IGNORECASE), "skill:postgresql", "backend"),
    (re.compile(r"\b(?:mysql)\b", re.IGNORECASE), "skill:mysql", "backend"),
    (re.compile(r"\b(?:mongodb|mongo)\b", re.IGNORECASE), "skill:mongodb", "backend"),
    (re.compile(r"\b(?:redis)\b", re.IGNORECASE), "skill:redis", "backend"),
    (re.compile(r"\b(?:docker)\b", re.IGNORECASE), "skill:docker", "devops"),
    (re.compile(r"\b(?:kubernetes|k8s)\b", re.IGNORECASE), "skill:kubernetes", "devops"),
    (re.compile(r"\b(?:aws|amazon\s+web\s+services)\b", re.IGNORECASE), "skill:aws", "devops"),
    (re.compile(r"\b(?:rest\s+api|microservices)\b", re.IGNORECASE), "skill:rest_api", "backend"),
    (re.compile(r"\b(?:graphql)\b", re.IGNORECASE), "skill:graphql", "backend"),
    (re.compile(r"\b(?:kafka|rabbitmq)\b", re.IGNORECASE), "skill:kafka", "backend"),
    (re.compile(r"\b(?:sql)\b", re.IGNORECASE), "skill:sql", "data"),
    (re.compile(r"\b(?:spark|pyspark)\b", re.IGNORECASE), "skill:spark", "data"),
    (re.compile(r"\b(?:tableau|power\s*bi)\b", re.IGNORECASE), "skill:data_viz", "data"),
    (re.compile(r"\b(?:selenium|cypress|playwright)\b", re.IGNORECASE), "skill:test_automation", "qa"),
]


def compile_jd_rule_based(
    jd_text: str,
    ontology: OntologyGraph | None = None,
) -> RequirementSetIR:
    """Deterministic rule-based compiler parsing JD text into structured RequirementIRs."""
    ont = ontology or get_ontology_graph()
    clean_text = sanitize_contact_pii(jd_text)

    # 1. Detect overall job title
    raw_lines = [ln.strip() for ln in clean_text.splitlines() if ln.strip()]
    raw_first = raw_lines[0] if raw_lines else "Software Engineer"
    job_title = re.sub(
        r"^(?:lowongan\s+kerja|job\s+opening|posisi|position)\s*:\s*", "", raw_first, flags=re.IGNORECASE
    ).strip()
    if not job_title:
        job_title = raw_first
    overall_role = resolve_role_family(job_title, ontology=ont) or "backend"

    requirements: list[RequirementIR] = []
    seen_concepts: set[str] = set()
    req_idx = 1

    current_section = "REQUIREMENTS"

    for idx, line in enumerate(raw_lines):
        lower = line.lower()
        # Skip job title / header line
        if idx == 0 and (line == raw_first or re.search(r"\b(?:lowongan\s+kerja|job\s+opening)\b", lower)):
            continue
        if re.search(r"^(?:lowongan\s+kerja|job\s+opening|posisi|position)\s*:", lower):
            continue
        if re.search(r"\b(?:kualifikasi|persyaratan|requirements|qualifications)\b", lower):
            current_section = "REQUIREMENTS"
            continue
        if re.search(r"\b(?:nilai\s+tambah|diutamakan|preferred|nice\s+to\s+have|plus)\b", lower):
            current_section = "NICE_TO_HAVE"
            continue
        if len(line) < 5 or line.startswith("#"):
            continue

        # Check for policy compliance flags
        lint_res = lint_text(line)
        l_flags = lint_res.get("flags", [])

        # Default importance
        importance = determine_importance(
            line, default="MUST_HAVE" if current_section == "REQUIREMENTS" else "NICE_TO_HAVE"
        )

        # 1. Experience / Role Equivalence Detection
        role_detected = resolve_role_family(line, ontology=ont)
        m_years = YEARS_REGEX.search(line)

        if role_detected or (m_years and ("pengalaman" in lower or "experience" in lower)):
            target_role = role_detected or overall_role
            target_domain = target_role
            facets = decompose_role_to_facets(target_role, ontology=ont)
            dur_policy = extract_duration_policy(line, target_domain=target_domain)
            if not dur_policy and m_years:
                dur_policy = DurationPolicySchema(min_months=24.0, target_domain=target_domain)

            req = RequirementIR(
                requirement_id=f"REQ-{req_idx:02d}",
                description=line,
                category="EXPERIENCE",
                kind="ROLE_EQUIVALENCE",
                importance=importance,
                weight=25.0 if importance == "MUST_HAVE" else 15.0,
                concepts=[f"role:{target_role}"],
                target_domains=[target_domain],
                duration_policy=dur_policy,
                accepted_evidence=["T1", "T2", "T3", "T4"],
                depth_floor="L1",
                facets=facets,
                hard_filter=False,
                source_text=line,
                lint_flags=l_flags,
                role_family=target_role,
            )
            requirements.append(req)
            req_idx += 1
            continue

        # 2. Skill Detection
        matched_skills: list[str] = []
        matched_domain = overall_role
        for pat, sk_concept, sk_domain in KNOWN_SKILL_PATTERNS:
            if pat.search(line):
                matched_skills.append(sk_concept)
                matched_domain = sk_domain

        if matched_skills:
            new_skills = [s for s in matched_skills if s not in seen_concepts]
            if not new_skills and len(matched_skills) > 0:
                new_skills = matched_skills
            for s in new_skills:
                seen_concepts.add(s)

            req = RequirementIR(
                requirement_id=f"REQ-{req_idx:02d}",
                description=line,
                category="HARD_SKILLS",
                kind="SKILL",
                importance=importance,
                weight=10.0 if importance == "MUST_HAVE" else 5.0,
                concepts=matched_skills,
                target_domains=[matched_domain],
                duration_policy=None,
                accepted_evidence=["T0", "T1", "T2", "T3", "T4"],
                depth_floor="L1",
                facets=[],
                hard_filter=False,
                source_text=line,
                lint_flags=l_flags,
            )
            requirements.append(req)
            req_idx += 1
            continue

        # 3. Education detection
        if re.search(
            r"\b(?:s1|d3|sarjana|bachelor|diploma|pendidikan|jurusan|computer\s+science|informatika)\b", lower
        ):
            req = RequirementIR(
                requirement_id=f"REQ-{req_idx:02d}",
                description=line,
                category="EDUCATION_CERT",
                kind="EDUCATION",
                importance=importance,
                weight=10.0,
                concepts=["education:tertiary"],
                target_domains=[],
                duration_policy=None,
                accepted_evidence=["T0", "T1", "T2"],
                depth_floor="L0",
                facets=[],
                hard_filter=False,
                source_text=line,
                lint_flags=l_flags,
            )
            requirements.append(req)
            req_idx += 1
            continue

    # If no requirements were extracted (e.g. short prompt), construct primary role requirement
    if not requirements:
        facets = decompose_role_to_facets(overall_role, ontology=ont)
        req = RequirementIR(
            requirement_id="REQ-01",
            description=f"Minimal pengalaman sebagai {job_title}",
            category="EXPERIENCE",
            kind="ROLE_EQUIVALENCE",
            importance="MUST_HAVE",
            weight=30.0,
            concepts=[f"role:{overall_role}"],
            target_domains=[overall_role],
            duration_policy=DurationPolicySchema(min_months=24.0, target_domain=overall_role),
            accepted_evidence=["T1", "T2", "T3", "T4"],
            depth_floor="L1",
            facets=facets,
            hard_filter=False,
            source_text=job_title,
            lint_flags=[],
            role_family=overall_role,
        )
        requirements.append(req)

    return RequirementSetIR(
        job_title=job_title,
        requirements=requirements,
        category_weights=dict(DEFAULT_CATEGORY_WEIGHTS),
        version=1,
    )


async def compile_with_llm(
    jd_text: str,
    client: Any = None,
    tenant_id: uuid.UUID | None = None,
    ontology: OntologyGraph | None = None,
) -> RequirementSetIR | None:
    """9Router LLM adapter (ag/gemini-3.8-flash-high) compiling JD text to RequirementSetIR."""
    gateway = client if client is not None else ModelGateway()
    clean_text = sanitize_contact_pii(jd_text)

    # Pre-flight PII guard
    if hasattr(gateway, "verify_redacted_text"):
        try:
            gateway.verify_redacted_text(clean_text)
        except Exception as e:
            logger.warning(f"PII preflight blocked LLM JD compiler: {e}")
            return None

    model = getattr(settings, "LLM_MODEL_JD_COMPILER", "ag/gemini-3.8-flash-high")

    sys_prompt = (
        "You are an expert Job Description (JD) compiler for high-precision CV screening (Blueprint v2.1).\n"
        "Your role is to deconstruct a job description into structured RequirementIR objects.\n"
        "Rules:\n"
        "1. For role experience qualifications (e.g. 'Frontend Developer', 'Backend Engineer'), set kind='ROLE_EQUIVALENCE', "
        "target_domains=[role], duration_policy with min_months, and decompose the role into atomic testable facets (F1..F5).\n"
        "2. For core facets mandatory for the role, set core=true. For supplementary/nice-to-have facets, set core=false.\n"
        "3. Output strictly valid JSON matching the schema:\n"
        "{\n"
        '  "job_title": "string",\n'
        '  "category_weights": {"EXPERIENCE": 40, "HARD_SKILLS": 30, "EDUCATION_CERT": 15, "ACHIEVEMENT": 15},\n'
        '  "requirements": [\n'
        "    {\n"
        '      "requirement_id": "REQ-01",\n'
        '      "description": "string",\n'
        '      "category": "EXPERIENCE",\n'
        '      "kind": "ROLE_EQUIVALENCE",\n'
        '      "importance": "MUST_HAVE",\n'
        '      "weight": 25.0,\n'
        '      "concepts": ["role:frontend"],\n'
        '      "target_domains": ["frontend"],\n'
        '      "duration_policy": {"min_months": 36.0, "target_domain": "frontend"},\n'
        '      "accepted_evidence": ["T1", "T2", "T3", "T4"],\n'
        '      "depth_floor": "L1",\n'
        '      "facets": [\n'
        '        {"facet_key": "F1", "hypothesis": "membangun komponen UI di framework SPA", "core": true, "concepts": ["skill:react"]}\n'
        "      ]\n"
        "    }\n"
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"Compile this Job Description into structured RequirementIR with facet decomposition:\n\n{clean_text}"
    )

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        resp = await gateway.call_chat(
            messages=messages,
            task="jd_compiler",
            tenant_id=tenant_id,
            json_mode=True,
            model=model,
        )
        if isinstance(resp, dict):
            if "choices" in resp and resp["choices"]:
                content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                content = resp.get("raw_content") or resp.get("content", "")
            parsed = (
                parse_llm_json(content)
                if isinstance(content, str)
                else (content if isinstance(content, dict) else None)
            )
            if isinstance(parsed, dict) and "requirements" in parsed:
                # Validate through Pydantic
                req_set = RequirementSetIR.model_validate(parsed)
                # Ensure policy lint flags are populated
                for r in req_set.requirements:
                    lint_res = lint_text(r.description)
                    r.lint_flags = lint_res.get("flags", [])
                return req_set
    except Exception as e:
        logger.warning(f"LLM JD compilation failed, falling back to rule-based: {e}")

    return None


async def compile_job_requirements_ir(
    jd_text: str,
    tenant_id: uuid.UUID | None = None,
    use_llm: bool = True,
    client: Any = None,
    ontology: OntologyGraph | None = None,
) -> RequirementSetIR:
    """Primary compiler entrypoint converting raw JD text into a complete RequirementSetIR.

    Attempts 9Router LLM compilation if enabled, with automated graceful fallback
    to deterministic rule-based decomposition.
    """
    ont = ontology or get_ontology_graph()

    if use_llm:
        res = await compile_with_llm(jd_text, client=client, tenant_id=tenant_id, ontology=ont)
        if res is not None and len(res.requirements) > 0:
            return res

    return compile_jd_rule_based(jd_text, ontology=ont)


# ----------------------------------------------------------------------
# Database Persistence Helpers
# ----------------------------------------------------------------------


async def save_requirement_ir_to_db(
    conn: Any,
    requirement_set_id: uuid.UUID,
    tenant_id: uuid.UUID,
    req: RequirementIR,
) -> uuid.UUID:
    """Persists a RequirementIR and its decomposed facets into PostgreSQL.

    Inserts into both `requirements` and `requirement_facets` tables.
    """
    r_id = uuid.uuid4()
    dur_policy_json = json.dumps(req.duration_policy.model_dump()) if req.duration_policy else "{}"

    async with conn.cursor() as cur:
        # 1. Insert requirement row
        await cur.execute(
            """
            INSERT INTO requirements (
                id, tenant_id, requirement_set_id, requirement_id, description,
                category, kind, importance, weight, concepts, params, hard_filter,
                source_text, lint_flags, target_domains, duration_policy,
                accepted_evidence, depth_floor
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                r_id,
                tenant_id,
                requirement_set_id,
                req.requirement_id,
                req.description,
                req.category,
                req.kind,
                req.importance,
                req.weight,
                req.concepts,
                json.dumps(req.params),
                req.hard_filter,
                req.source_text,
                req.lint_flags,
                req.target_domains,
                dur_policy_json,
                req.accepted_evidence,
                req.depth_floor,
            ),
        )

        # 2. Insert requirement facets
        for facet in req.facets:
            await cur.execute(
                """
                INSERT INTO requirement_facets (
                    requirement_uuid, facet_key, hypothesis, core, concepts
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (requirement_uuid, facet_key)
                DO UPDATE SET
                    hypothesis = EXCLUDED.hypothesis,
                    core = EXCLUDED.core,
                    concepts = EXCLUDED.concepts
                """,
                (
                    r_id,
                    facet.facet_key,
                    facet.hypothesis,
                    facet.core,
                    facet.concepts,
                ),
            )

        await conn.commit()
    return r_id


async def load_requirement_ir_from_db(
    conn: Any,
    requirement_uuid: uuid.UUID,
) -> RequirementIR:
    """Loads a RequirementIR with all associated facets from PostgreSQL."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, tenant_id, requirement_set_id, requirement_id, description,
                   category, kind, importance, weight, concepts, params, hard_filter,
                   source_text, lint_flags, target_domains, duration_policy,
                   accepted_evidence, depth_floor
            FROM requirements
            WHERE id = %s
            """,
            (requirement_uuid,),
        )
        row = await cur.fetchone()
        if not row:
            raise KeyError(f"Requirement with id {requirement_uuid} not found")

        # Load facets
        await cur.execute(
            """
            SELECT facet_key, hypothesis, core, concepts
            FROM requirement_facets
            WHERE requirement_uuid = %s
            ORDER BY facet_key ASC
            """,
            (requirement_uuid,),
        )
        facet_rows = await cur.fetchall()

    facets = [
        RequirementFacet(
            facet_key=f["facet_key"],
            hypothesis=f["hypothesis"],
            core=f["core"],
            concepts=list(f["concepts"] or []),
        )
        for f in facet_rows
    ]

    dur_policy_raw = row["duration_policy"]
    dur_policy = None
    if dur_policy_raw and isinstance(dur_policy_raw, dict) and dur_policy_raw.get("min_months") is not None:
        dur_policy = DurationPolicySchema.model_validate(dur_policy_raw)
    elif isinstance(dur_policy_raw, str) and dur_policy_raw not in ("", "{}"):
        parsed = json.loads(dur_policy_raw)
        if parsed.get("min_months") is not None:
            dur_policy = DurationPolicySchema.model_validate(parsed)

    params_raw = row["params"]
    params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})

    return RequirementIR(
        requirement_id=row["requirement_id"],
        description=row["description"],
        category=row["category"],
        kind=row["kind"],
        importance=row["importance"],
        weight=float(row["weight"]),
        concepts=list(row["concepts"] or []),
        target_domains=list(row["target_domains"] or []),
        duration_policy=dur_policy,
        accepted_evidence=list(row["accepted_evidence"] or []),
        depth_floor=row["depth_floor"] or "L1",
        facets=facets,
        hard_filter=row["hard_filter"],
        source_text=row["source_text"] or "",
        lint_flags=list(row["lint_flags"] or []),
        params=params,
    )


async def save_facet_judgment_to_db(
    conn: Any,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    requirement_id: str,
    facet_key: str,
    tenant_id: uuid.UUID,
    verdict: str,
    depth_level: str | None = None,
    support_atom_ids: list[uuid.UUID] | None = None,
    method: str = "matcher",
    analysis: str | None = None,
    nli_p_entail: float | None = None,
    rationale_code: str | None = None,
    superseded_by_critic: bool = False,
) -> None:
    """Inserts or updates a facet evaluation judgment in `facet_judgments`."""
    valid_uuids: list[uuid.UUID] = []
    if support_atom_ids:
        for sa in support_atom_ids:
            if isinstance(sa, uuid.UUID):
                valid_uuids.append(sa)
            elif isinstance(sa, str):
                with contextlib.suppress(ValueError):
                    valid_uuids.append(uuid.UUID(sa))

    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO facet_judgments (
                run_id, candidate_id, requirement_id, facet_key, tenant_id,
                verdict, depth_level, support_atom_ids, method, analysis,
                nli_p_entail, rationale_code, superseded_by_critic
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, candidate_id, requirement_id, facet_key)
            DO UPDATE SET
                verdict = EXCLUDED.verdict,
                depth_level = EXCLUDED.depth_level,
                support_atom_ids = EXCLUDED.support_atom_ids,
                method = EXCLUDED.method,
                analysis = EXCLUDED.analysis,
                nli_p_entail = EXCLUDED.nli_p_entail,
                rationale_code = EXCLUDED.rationale_code,
                superseded_by_critic = EXCLUDED.superseded_by_critic
            """,
            (
                run_id,
                candidate_id,
                requirement_id,
                facet_key,
                tenant_id,
                verdict,
                depth_level,
                valid_uuids,
                method,
                analysis,
                nli_p_entail,
                rationale_code,
                superseded_by_critic,
            ),
        )
        await conn.commit()


async def save_domain_duration_to_db(
    conn: Any,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    domain: str,
    tenant_id: uuid.UUID,
    policy_hash: str,
    months_lo: float,
    months_hi: float,
    month_ledger: list[dict[str, Any]] | None = None,
) -> None:
    """Inserts or updates accumulated domain duration in `domain_durations`."""
    ledger_json = json.dumps(month_ledger or [])
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO domain_durations (
                run_id, candidate_id, domain, tenant_id, policy_hash,
                months_lo, months_hi, month_ledger
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_id, candidate_id, domain)
            DO UPDATE SET
                policy_hash = EXCLUDED.policy_hash,
                months_lo = EXCLUDED.months_lo,
                months_hi = EXCLUDED.months_hi,
                month_ledger = EXCLUDED.month_ledger
            """,
            (
                run_id,
                candidate_id,
                domain,
                tenant_id,
                policy_hash,
                months_lo,
                months_hi,
                ledger_json,
            ),
        )
        await conn.commit()
