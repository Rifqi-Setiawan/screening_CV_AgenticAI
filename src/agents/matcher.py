"""Matcher Agent implementation for Directional Entailment facet evaluation (v2.1).

Implements Section C2 S6 of the Blueprint:
- Evaluates qualification facets against literal evidence atoms.
- Batches <= 6 facets per LLM call via 9Router (ag/gemini-3.8-flash-high).
- Presents job title strictly as context_only after atoms to avoid title-bias.
- Marks claim/summary atoms with [CLAIM] to enforce T0 ceiling.
- Enforces R1 rule: `analysis` (<= 60 tokens) placed BEFORE `verdict`.
- Handles `needs_more_context=True` by expanding neighbor atoms for the same entry (max 1 loop).
- Persists evaluations to database table `facet_judgments`.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from pathlib import Path
from typing import Any

from src.agents.prompt_safety import DATA_RULE, atom_text_for_llm, fence_untrusted, neutralize_for_fence
from src.agents.schemas.matcher import (
    DepthLevel,
    FacetEvaluationInput,
    FacetEvaluationResult,
    FacetVerdict,
    MatcherBatchOutput,
)
from src.domain.atoms import EvidenceAtom
from src.domain.requirements.compiler import save_facet_judgment_to_db
from src.domain.requirements.schemas import RequirementFacet
from src.infrastructure.config import settings
from src.infrastructure.gateway import ModelGateway, parse_llm_json
from src.infrastructure.logging import logger

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_matcher_system_prompt() -> str:
    """Loads system prompt for the Matcher Agent."""
    prompt_file = PROMPTS_DIR / "matcher_v1.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Matcher system prompt not found at {prompt_file}")
    return prompt_file.read_text(encoding="utf-8") + "\n\n" + DATA_RULE


def build_matcher_user_prompt(
    facets: list[RequirementFacet | FacetEvaluationInput | dict[str, Any]],
    atoms: list[EvidenceAtom | dict[str, Any]],
    raw_title: str | None = None,
) -> str:
    """Formats requirement facets and candidate evidence atoms for Matcher LLM evaluation."""
    lines: list[str] = [
        "### Facets to Evaluate:",
    ]
    for f in facets:
        fkey = f.facet_key if isinstance(f, (RequirementFacet, FacetEvaluationInput)) else str(f.get("facet_key", ""))
        hyp = f.hypothesis if isinstance(f, (RequirementFacet, FacetEvaluationInput)) else str(f.get("hypothesis", ""))
        core = f.core if isinstance(f, (RequirementFacet, FacetEvaluationInput)) else bool(f.get("core", True))
        concepts = (
            f.concepts if isinstance(f, (RequirementFacet, FacetEvaluationInput)) else list(f.get("concepts", []))
        )
        depth_floor = getattr(f, "depth_floor", None) or (f.get("depth_floor") if isinstance(f, dict) else "L1")
        core_str = "CORE" if core else "SUPPORTING"
        concepts_str = f" [concepts: {', '.join(concepts)}]" if concepts else ""
        lines.append(f'- Facet [{fkey}] ({core_str}, floor: {depth_floor}){concepts_str}: "{hyp}"')

    lines.append("\n### Candidate Evidence Atoms (untrusted document data):")
    atom_lines: list[str] = []
    for a in atoms:
        akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else "")
        akind = getattr(a, "kind", None) or (a.get("kind") if isinstance(a, dict) else "")
        eref = getattr(a, "entry_ref", None) or (a.get("entry_ref") if isinstance(a, dict) else None)
        text = getattr(a, "text_redacted", None) or (a.get("text_redacted") if isinstance(a, dict) else "")

        claim_tag = " [CLAIM/MENTION_ONLY]" if akind in ("summary_sentence", "skill_list_item", "self_claim") else ""
        ref_str = f" [entry: {eref}]" if eref else ""
        atom_lines.append(f"- [{akey}] (kind: {akind}{ref_str}{claim_tag}): {atom_text_for_llm(str(text or ''))}")
    lines.append(fence_untrusted("\n".join(atom_lines)))

    if raw_title:
        lines.append(
            f"\n### Context Only (Weak Prior):\nCandidate's stated job title is '{neutralize_for_fence(raw_title)[:120]}'. "
            "WARNING: This title is provided strictly as background context. It MUST NOT be the sole basis "
            "for deciding whether facets are entailed or not entailed."
        )

    lines.append(
        "\n### Task Instructions:\n"
        "Evaluate directional entailment for each facet against the literal evidence atoms above.\n"
        "Output strictly valid JSON matching the schema.\n"
        "CRITICAL: The 'analysis' field (<= 60 tokens) MUST appear before 'verdict'."
    )
    return "\n".join(lines)


async def _call_matcher_single_batch(
    facets: list[RequirementFacet | FacetEvaluationInput | dict[str, Any]],
    atoms: list[EvidenceAtom | dict[str, Any]],
    client: Any,
    tenant_id: uuid.UUID | None,
    raw_title: str | None,
    model: str,
) -> MatcherBatchOutput:
    """Invokes LLM for a single batch of <= 6 facets."""
    sys_prompt = load_matcher_system_prompt()
    user_prompt = build_matcher_user_prompt(facets=facets, atoms=atoms, raw_title=raw_title)

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    gateway = client if client is not None else ModelGateway()
    logger.info(f"Calling Matcher Agent for {len(facets)} facets with {len(atoms)} atoms using model {model}")

    response_data = await gateway.call_chat(
        messages=messages,
        task="matcher",
        tenant_id=tenant_id,
        json_mode=True,
        model=model,
    )

    if response_data is None:
        logger.warning("Matcher LLM call returned None; returning fallback output")
        fallback_evals = [
            FacetEvaluationResult(
                facet_key=(
                    f.facet_key
                    if isinstance(f, (RequirementFacet, FacetEvaluationInput))
                    else str(f.get("facet_key", ""))
                ),
                analysis="LLM call returned None (gateway unavailable).",
                verdict=FacetVerdict.UNKNOWN,
                support_atoms=[],
                depth_level=DepthLevel.L0,
                rationale_code="GATEWAY_FALLBACK",
            )
            for f in facets
        ]
        return MatcherBatchOutput(evaluations=fallback_evals, flags=["MATCHER_GATEWAY_NONE"])

    if isinstance(response_data, dict) and "raw_content" in response_data:
        parsed = parse_llm_json(response_data["raw_content"])
        if parsed is None or not isinstance(parsed, dict):
            logger.warning("Failed to parse Matcher JSON output")
            fallback_evals = [
                FacetEvaluationResult(
                    facet_key=(
                        f.facet_key
                        if isinstance(f, (RequirementFacet, FacetEvaluationInput))
                        else str(f.get("facet_key", ""))
                    ),
                    analysis="Failed to parse model JSON output.",
                    verdict=FacetVerdict.UNKNOWN,
                    support_atoms=[],
                    depth_level=DepthLevel.L0,
                    rationale_code="JSON_PARSE_ERROR",
                )
                for f in facets
            ]
            return MatcherBatchOutput(evaluations=fallback_evals, flags=["MATCHER_JSON_PARSE_ERROR"])
        raw_dict = parsed
    elif isinstance(response_data, dict):
        raw_dict = response_data
    else:
        logger.warning(f"Unexpected response type from LLM gateway: {type(response_data)}")
        return MatcherBatchOutput(flags=["MATCHER_INVALID_RESPONSE_TYPE"])

    try:
        return MatcherBatchOutput.model_validate(raw_dict)
    except Exception as e:
        logger.warning(f"Schema validation error in Matcher output: {e}")
        # Build graceful fallback for any unparsed facets
        evals: list[FacetEvaluationResult] = []
        raw_evals = raw_dict.get("evaluations") or raw_dict.get("results") or raw_dict.get("judgments") or []
        for re_item in raw_evals:
            with contextlib.suppress(Exception):
                evals.append(FacetEvaluationResult.model_validate(re_item))
        return MatcherBatchOutput(evaluations=evals, flags=["MATCHER_VALIDATION_PARTIAL"])


async def run_matcher_agent(
    facets: list[RequirementFacet | FacetEvaluationInput | dict[str, Any]],
    candidate_atoms: list[EvidenceAtom | dict[str, Any]],
    client: Any = None,
    tenant_id: uuid.UUID | None = None,
    raw_title: str | None = None,
    all_candidate_atoms: list[EvidenceAtom | dict[str, Any]] | None = None,
    model: str | None = None,
) -> MatcherBatchOutput:
    """Executes Matcher Agent with batching <= 6 facets and context expansion loop.

    Args:
        facets: Qualification facets to evaluate.
        candidate_atoms: Initial top-K evidence atoms.
        client: Optional ModelGateway or mock client.
        tenant_id: Optional tenant identifier.
        raw_title: Optional candidate raw job title.
        all_candidate_atoms: All candidate atoms for neighbor context retrieval.
        model: Model identifier override (defaults to settings.LLM_MODEL_MATCHER or 'ag/gemini-3.8-flash-high').

    Returns:
        MatcherBatchOutput containing validated FacetEvaluationResult per facet.
    """
    selected_model: str = str(model or getattr(settings, "LLM_MODEL_MATCHER", "ag/gemini-3.8-flash-high"))
    all_atoms = all_candidate_atoms or candidate_atoms

    # Batching <= 6 facets per call (R3)
    batch_size = 6
    all_evaluations: list[FacetEvaluationResult] = []
    global_flags: list[str] = []

    # Batches are independent: run them concurrently (the gateway caps in-flight requests globally).
    chunks = [facets[i : i + batch_size] for i in range(0, len(facets), batch_size)]
    batch_outputs = await asyncio.gather(
        *(
            _call_matcher_single_batch(
                facets=chunk,
                atoms=candidate_atoms,
                client=client,
                tenant_id=tenant_id,
                raw_title=raw_title,
                model=selected_model,
            )
            for chunk in chunks
        )
    )
    for batch_output in batch_outputs:
        all_evaluations.extend(batch_output.evaluations)
        global_flags.extend(batch_output.flags)

    # Context Expansion Loop: check if any facet requested needs_more_context
    needs_context_facets: list[RequirementFacet | FacetEvaluationInput | dict[str, Any]] = []
    entry_refs_to_expand: set[str] = set()

    for ev in all_evaluations:
        if ev.needs_more_context:
            # Find entry_refs of supporting atoms or general candidate entry_refs
            for sa in ev.support_atoms:
                for a in candidate_atoms:
                    akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else "")
                    eref = getattr(a, "entry_ref", None) or (a.get("entry_ref") if isinstance(a, dict) else None)
                    if akey == sa and eref:
                        entry_refs_to_expand.add(str(eref))

            # Locate original facet object
            f_orig = next(
                (
                    f
                    for f in facets
                    if (
                        f.facet_key
                        if isinstance(f, (RequirementFacet, FacetEvaluationInput))
                        else str(f.get("facet_key", ""))
                    )
                    == ev.facet_key
                ),
                None,
            )
            if f_orig:
                needs_context_facets.append(f_orig)

    # Perform max 1 loop of neighbor context expansion if needed
    if needs_context_facets and entry_refs_to_expand and all_atoms:
        logger.info(
            f"needs_more_context=True for {len(needs_context_facets)} facets. Expanding neighbor atoms from entries: {entry_refs_to_expand}"
        )
        global_flags.append("NEEDS_MORE_CONTEXT_TRIGGERED")

        # Collect neighbor atoms from all candidate atoms
        expanded_atoms: list[EvidenceAtom | dict[str, Any]] = []
        seen_keys: set[str] = set()

        # Include initial candidate atoms first
        for a in candidate_atoms:
            akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else "")
            if akey:
                seen_keys.add(str(akey))
                expanded_atoms.append(a)

        # Include neighbor atoms from the target entry_refs
        for a in all_atoms:
            akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else "")
            eref = getattr(a, "entry_ref", None) or (a.get("entry_ref") if isinstance(a, dict) else None)
            if eref and str(eref) in entry_refs_to_expand and str(akey) not in seen_keys:
                seen_keys.add(str(akey))
                expanded_atoms.append(a)

        # Re-run matcher for only the affected facets
        retry_output = await _call_matcher_single_batch(
            facets=needs_context_facets,
            atoms=expanded_atoms,
            client=client,
            tenant_id=tenant_id,
            raw_title=raw_title,
            model=selected_model,
        )

        # Merge retry evaluations back
        retry_map = {r.facet_key: r for r in retry_output.evaluations}
        final_evals: list[FacetEvaluationResult] = []
        for ev in all_evaluations:
            if ev.facet_key in retry_map:
                final_evals.append(retry_map[ev.facet_key])
            else:
                final_evals.append(ev)
        all_evaluations = final_evals

    return MatcherBatchOutput(
        evaluations=all_evaluations,
        flags=sorted(list(set(global_flags))),
    )


async def save_matcher_results(
    conn: Any,
    run_id: uuid.UUID,
    candidate_id: uuid.UUID,
    requirement_id: str,
    output: MatcherBatchOutput,
    tenant_id: uuid.UUID,
    atom_key_to_uuid: dict[str, uuid.UUID] | None = None,
    method: str = "matcher",
) -> int:
    """Persists Matcher evaluations to the `facet_judgments` table."""
    key_map = dict(atom_key_to_uuid or {})

    # If atom UUID mapping is incomplete, query evidence_atoms from DB
    if not key_map:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, atom_key FROM evidence_atoms WHERE profile_id = %s",
                (candidate_id,),
            )
            rows = await cur.fetchall()
            for r in rows:
                key_map[r["atom_key"]] = r["id"]

    saved_count = 0
    for ev in output.evaluations:
        supp_uuids: list[uuid.UUID] = []
        for akey in ev.support_atoms:
            u = key_map.get(str(akey))
            if u:
                supp_uuids.append(u)

        await save_facet_judgment_to_db(
            conn=conn,
            run_id=run_id,
            candidate_id=candidate_id,
            requirement_id=requirement_id,
            facet_key=ev.facet_key,
            tenant_id=tenant_id,
            verdict=ev.verdict.value,
            depth_level=ev.depth_level.value,
            support_atom_ids=supp_uuids,
            support_atom_keys=[str(a) for a in ev.support_atoms],
            method=method,
            analysis=ev.analysis,
            rationale_code=ev.rationale_code,
            superseded_by_critic=False,
        )
        saved_count += 1

    return saved_count
