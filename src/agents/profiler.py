"""Profiler Agent implementation for autonomous capability and experience domain profiling (v2.1)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from src.agents.schemas.profiler import ProfilerOutput
from src.agents.validators import validate_profiler_output
from src.domain.atoms import EvidenceAtom
from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import get_ontology_graph
from src.domain.temporal.date_normalizer import normalize_date_range
from src.infrastructure.config import settings
from src.infrastructure.gateway import ModelGateway, parse_llm_json
from src.infrastructure.logging import logger

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_profiler_system_prompt() -> str:
    """Loads system prompt for the Profiler Agent."""
    prompt_file = PROMPTS_DIR / "profiler_v1.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Profiler system prompt not found at {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def build_profiler_user_prompt(
    profile_id: str | uuid.UUID,
    atoms: list[EvidenceAtom | dict[str, Any]],
    raw_title: str | None = None,
) -> str:
    """Formats evidence atoms and raw context for Profiler LLM evaluation."""
    lines: list[str] = [
        f"Profile ID: {profile_id}",
    ]
    if raw_title:
        lines.append(
            f"Context only (weak prior): Raw job title is '{raw_title}'. Do not let title override literal evidence."
        )

    lines.append("\nEvidence Atoms to classify:")
    for a in atoms:
        akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else "")
        akind = getattr(a, "kind", None) or (a.get("kind") if isinstance(a, dict) else "")
        eref = getattr(a, "entry_ref", None) or (a.get("entry_ref") if isinstance(a, dict) else None)
        text = getattr(a, "text_redacted", None) or (a.get("text_redacted") if isinstance(a, dict) else "")
        ref_str = f" [entry: {eref}]" if eref else ""
        lines.append(f"- [{akey}] (kind: {akind}{ref_str}): {text}")

    lines.append(
        "\nTask: Classify experiences, domain allocations (PRIMARY/SECONDARY/INCIDENTAL), and atom tags. Output strictly valid JSON."
    )
    return "\n".join(lines)


async def run_profiler_agent(
    profile_id: str | uuid.UUID,
    atoms: list[EvidenceAtom | dict[str, Any]],
    client: Any = None,
    tenant_id: uuid.UUID | None = None,
    raw_title: str | None = None,
    ontology: OntologyGraph | None = None,
) -> ProfilerOutput:
    """Executes Profiler Agent via 9Router LLM gateway (ag/gemini-3.8-flash-high).

    Args:
        profile_id: Candidate profile UUID.
        atoms: List of evidence atoms to profile.
        client: Optional ModelGateway or mock client.
        tenant_id: Optional tenant isolation identifier.
        raw_title: Optional raw title for weak prior context.
        ontology: Optional capability ontology graph for validation.

    Returns:
        Validated ProfilerOutput with code_atom_ratio cross-validation applied.
    """
    sys_prompt = load_profiler_system_prompt()
    user_prompt = build_profiler_user_prompt(profile_id=profile_id, atoms=atoms, raw_title=raw_title)

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    gateway = client if client is not None else ModelGateway()
    model = getattr(settings, "LLM_MODEL_PROFILER", "ag/gemini-3.8-flash-high")

    logger.info(f"Running Profiler Agent for profile {profile_id} with {len(atoms)} atoms using model {model}")

    # Invoke LLM in JSON mode
    response_data = await gateway.call_chat(
        messages=messages,
        task="profiler",
        tenant_id=tenant_id,
        json_mode=True,
        model=model,
    )

    if response_data is None:
        logger.warning("Profiler LLM call returned None; returning empty ProfilerOutput with PROFILER_FAILED flag")
        return ProfilerOutput(flags=["PROFILER_FAILED"])

    if isinstance(response_data, dict) and "raw_content" in response_data:
        parsed = parse_llm_json(response_data["raw_content"])
        if parsed is None or not isinstance(parsed, dict):
            logger.warning("Failed to parse Profiler JSON output")
            return ProfilerOutput(flags=["PROFILER_JSON_PARSE_FAILED"])
        raw_dict = parsed
    elif isinstance(response_data, dict):
        raw_dict = response_data
    else:
        logger.warning(f"Unexpected response type from LLM gateway: {type(response_data)}")
        return ProfilerOutput(flags=["PROFILER_INVALID_RESPONSE_TYPE"])

    # Parse and validate output
    active_ontology = ontology or get_ontology_graph()
    validated_output = validate_profiler_output(
        output=raw_dict,
        atoms=atoms,
        ontology=active_ontology,
    )

    return validated_output


def _is_uuid(val: Any) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


async def save_profiler_results(
    conn: Any,
    profile_id: str | uuid.UUID,
    output: ProfilerOutput,
    atoms: list[EvidenceAtom | dict[str, Any]],
    model_call_id: uuid.UUID | None = None,
    ontology_version: str | None = None,
) -> dict[str, Any]:
    """Persists validated Profiler output to database tables:

    - experience_entries
    - experience_domain_allocations
    - atom_tags
    """
    prof_uuid = uuid.UUID(str(profile_id))

    # Build atom lookup maps
    atom_key_to_uuid: dict[str, uuid.UUID] = {}
    header_atoms_by_ref: dict[str, uuid.UUID] = {}

    # Extract in-memory UUIDs
    for a in atoms:
        akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else None)
        aid = getattr(a, "id", None) or (a.get("id") if isinstance(a, dict) else None)
        akind = getattr(a, "kind", None) or (a.get("kind") if isinstance(a, dict) else None)
        eref = getattr(a, "entry_ref", None) or (a.get("entry_ref") if isinstance(a, dict) else None)

        if akey and aid and _is_uuid(aid):
            u_aid = uuid.UUID(str(aid))
            atom_key_to_uuid[str(akey)] = u_aid
            if akind == "exp_header" and eref:
                header_atoms_by_ref[str(eref)] = u_aid

    # Query DB to resolve any remaining atom keys to UUIDs
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT id, atom_key, kind, entry_ref FROM evidence_atoms WHERE profile_id = %s",
            (prof_uuid,),
        )
        db_rows = await cur.fetchall()
        for r in db_rows:
            atom_key_to_uuid[r["atom_key"]] = r["id"]
            if r.get("kind") == "exp_header" and r.get("entry_ref"):
                header_atoms_by_ref[r["entry_ref"]] = r["id"]

    saved_experiences = 0
    saved_allocations = 0
    saved_tags = 0

    async with conn.cursor() as cur:
        # 1. Save experience_entries and domain_allocations
        for exp in output.experiences:
            interval = normalize_date_range(
                start_raw=exp.date_text_start,
                end_raw=exp.date_text_end,
            )
            is_curr = bool(
                exp.is_current
                or (
                    exp.date_text_end
                    and exp.date_text_end.strip().lower()
                    in (
                        "sekarang",
                        "saat ini",
                        "kini",
                        "present",
                        "current",
                        "now",
                        "ongoing",
                        "aktif",
                    )
                )
            )
            header_atom_id = header_atoms_by_ref.get(exp.entry_ref)

            await cur.execute(
                """
                INSERT INTO experience_entries (
                    profile_id, entry_ref, header_atom_id, title_raw, employment_type,
                    date_text_start, date_text_end, start_lo, start_hi, end_lo, end_hi,
                    is_current, date_flags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (profile_id, entry_ref) DO UPDATE SET
                    header_atom_id = EXCLUDED.header_atom_id,
                    title_raw = EXCLUDED.title_raw,
                    employment_type = EXCLUDED.employment_type,
                    date_text_start = EXCLUDED.date_text_start,
                    date_text_end = EXCLUDED.date_text_end,
                    start_lo = EXCLUDED.start_lo,
                    start_hi = EXCLUDED.start_hi,
                    end_lo = EXCLUDED.end_lo,
                    end_hi = EXCLUDED.end_hi,
                    is_current = EXCLUDED.is_current,
                    date_flags = EXCLUDED.date_flags
                RETURNING id;
                """,
                (
                    prof_uuid,
                    exp.entry_ref,
                    header_atom_id,
                    exp.title_raw,
                    exp.employment_type,
                    exp.date_text_start,
                    exp.date_text_end,
                    interval.start_lo,
                    interval.start_hi,
                    interval.end_lo,
                    interval.end_hi,
                    is_curr,
                    list(interval.flags),
                ),
            )
            row = await cur.fetchone()
            exp_id = row["id"]
            saved_experiences += 1

            # Save allocations for this experience
            for alloc in exp.domain_allocations:
                # Map support atom IDs to real UUIDs
                support_uuids: list[uuid.UUID] = []
                for sid in alloc.support_atom_ids:
                    if _is_uuid(sid):
                        support_uuids.append(uuid.UUID(str(sid)))
                    elif str(sid) in atom_key_to_uuid:
                        support_uuids.append(atom_key_to_uuid[str(sid)])

                level_str = alloc.level.value if hasattr(alloc.level, "value") else str(alloc.level)
                await cur.execute(
                    """
                    INSERT INTO experience_domain_allocations (
                        experience_id, domain, level, support_atom_ids, code_atom_ratio, flags, model_call_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (experience_id, domain) DO UPDATE SET
                        level = EXCLUDED.level,
                        support_atom_ids = EXCLUDED.support_atom_ids,
                        code_atom_ratio = EXCLUDED.code_atom_ratio,
                        flags = EXCLUDED.flags,
                        model_call_id = EXCLUDED.model_call_id;
                    """,
                    (
                        exp_id,
                        alloc.domain,
                        level_str,
                        support_uuids,
                        alloc.code_atom_ratio,
                        list(alloc.flags),
                        model_call_id,
                    ),
                )
                saved_allocations += 1

        # 2. Save atom_tags
        for tag in output.atom_tags:
            atom_uuid: uuid.UUID | None = None
            if _is_uuid(tag.atom_id):
                atom_uuid = uuid.UUID(str(tag.atom_id))
            elif str(tag.atom_id) in atom_key_to_uuid:
                atom_uuid = atom_key_to_uuid[str(tag.atom_id)]

            if not atom_uuid:
                logger.warning(f"Skipping atom tag for unresolvable atom ID: {tag.atom_id}")
                continue

            ev_type = tag.evidence_type.value if hasattr(tag.evidence_type, "value") else str(tag.evidence_type)
            await cur.execute(
                """
                INSERT INTO atom_tags (
                    atom_id, domains, activities, concepts, evidence_type,
                    impact_quantified, impact_kind, model_call_id, ontology_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (atom_id) DO UPDATE SET
                    domains = EXCLUDED.domains,
                    activities = EXCLUDED.activities,
                    concepts = EXCLUDED.concepts,
                    evidence_type = EXCLUDED.evidence_type,
                    impact_quantified = EXCLUDED.impact_quantified,
                    impact_kind = EXCLUDED.impact_kind,
                    model_call_id = EXCLUDED.model_call_id,
                    ontology_version = EXCLUDED.ontology_version;
                """,
                (
                    atom_uuid,
                    list(tag.domains),
                    list(tag.activities),
                    list(tag.concepts),
                    ev_type,
                    tag.impact_quantified,
                    tag.impact_kind,
                    model_call_id,
                    ontology_version,
                ),
            )
            saved_tags += 1

    return {
        "profile_id": str(prof_uuid),
        "experiences": saved_experiences,
        "allocations": saved_allocations,
        "atom_tags": saved_tags,
    }
