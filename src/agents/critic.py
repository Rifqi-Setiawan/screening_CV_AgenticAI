"""Critic Agent implementation for Adversarial Multi-Model verification (v2.1).

Implements Section C2 S8 and C5 of the Blueprint:
- Evaluates escalation triggers E1..E6 (MUST_HAVE band gate, border scores,
  NLI disagreement, >=60% T0 mention atoms, inconsistent allocation/date uncertainty,
  hidden text/injection suspects).
- Executes Critic Agent using an independent model family (cc/claude-sonnet-5-5 via 9Router).
- Enforces R1 and Blueprint C2 rule: `analysis` (freeform reasoning) MUST precede verdict.
- Adversarially tests claims against literal evidence, watching for keyword stuffing.
- Resolves disputes conservatively: when Critic and Matcher disagree, falls back to
  conservative state and sets flag AGENT_DISAGREEMENT -> MANUAL_CHECK.
"""

from __future__ import annotations

import contextlib
import uuid
from pathlib import Path
from typing import Any

from src.agents.schemas.critic import (
    CriticFacetReview,
    CriticInput,
    CriticOutput,
    VerdictAction,
)
from src.agents.schemas.matcher import (
    FacetEvaluationResult,
    FacetVerdict,
)
from src.domain.atoms import AtomKind, EvidenceAtom
from src.infrastructure.gateway import ModelGateway, parse_llm_json
from src.infrastructure.logging import logger

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Ranking of verdicts from most conservative (0) to strongest (4)
VERDICT_CONSERVATISM_RANK: dict[str, int] = {
    "CONTRADICTED": 0,
    "NOT_ENTAILED": 1,
    "UNKNOWN": 2,
    "PARTIAL": 3,
    "ENTAILED": 4,
}

# T0 atom kinds representing unproven claims / skill mentions
T0_ATOM_KINDS = {
    AtomKind.SKILL_LIST_ITEM.value,
    AtomKind.SUMMARY_SENTENCE.value,
    "skill_list_item",
    "summary_sentence",
    "self_claim",
    "summary_claim",
}

# Band cutoffs for E2 border proximity check (+- 3 points)
BAND_THRESHOLDS = (49.0, 50.0, 70.0, 74.0, 75.0)


def load_critic_system_prompt() -> str:
    """Loads system prompt for the Critic Agent."""
    prompt_file = PROMPTS_DIR / "critic_v1.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Critic system prompt not found at {prompt_file}")
    return prompt_file.read_text(encoding="utf-8")


def evaluate_escalation_triggers(
    candidate_id: str,
    requirement_scores: Any = None,
    judgments: list[FacetEvaluationResult | dict[str, Any]] | None = None,
    atoms: list[EvidenceAtom | dict[str, Any]] | None = None,
    candidate_metadata: dict[str, Any] | None = None,
) -> list[str]:
    """Evaluates whether any of the escalation triggers E1..E6 are active.

    Triggers:
    - E1: MUST_HAVE requirement that is not STRONG (determines gate/band).
    - E2: Candidate score is within +- 3 points of a band boundary (49, 50, 70, 74, 75).
    - E3: Disagreement between NLI entailment and Matcher judgments.
    - E4: >= 60% of supporting evidence atoms are T0 mentions/claims.
    - E5: INCONSISTENT_ALLOCATION or DATE_UNCERTAIN altering state.
    - E6: HIDDEN_TEXT or INJECTION_SUSPECT detected in input or atoms.
    """
    triggers: set[str] = set()
    judgments_list = judgments or []
    atoms_list = atoms or []
    meta = candidate_metadata or {}
    meta_flags: set[str] = set(meta.get("flags", []))

    # --- E1: MUST_HAVE determines gate/band ---
    if requirement_scores is not None:
        must_not_strong: list[str] = []
        if hasattr(requirement_scores, "must_have_not_strong"):
            must_not_strong = list(requirement_scores.must_have_not_strong)
        elif isinstance(requirement_scores, dict):
            must_not_strong = list(requirement_scores.get("must_have_not_strong", []))
            # Check requirements dict list
            reqs = requirement_scores.get("requirements", [])
            for r in reqs:
                if isinstance(r, dict) and r.get("importance") == "MUST_HAVE":
                    st = r.get("state") or r.get("status")
                    if st and st != "STRONG":
                        must_not_strong.append(r.get("requirement_id", "req"))

        if must_not_strong:
            triggers.add("E1")

    # Check judgments for must-have flags
    for j in judgments_list:
        j_dict = j if isinstance(j, dict) else j.model_dump()
        if j_dict.get("importance") == "MUST_HAVE":
            verd = str(j_dict.get("verdict", "")).upper()
            if verd not in ("ENTAILED", "STRONG"):
                triggers.add("E1")
        if "E1" in j_dict.get("flags", []):
            triggers.add("E1")

    # --- E2: Score within +-3 points of band boundary ---
    score_val: float | None = None
    if requirement_scores is not None:
        if hasattr(requirement_scores, "final_score"):
            score_val = float(requirement_scores.final_score)
        elif hasattr(requirement_scores, "raw_score"):
            score_val = float(requirement_scores.raw_score)
        elif isinstance(requirement_scores, dict):
            raw_s = requirement_scores.get("final_score")
            if raw_s is None:
                raw_s = requirement_scores.get("raw_score")
            if raw_s is None:
                raw_s = requirement_scores.get("score")
            if raw_s is not None:
                score_val = float(raw_s)
        elif isinstance(requirement_scores, (int, float)):
            score_val = float(requirement_scores)

    if score_val is not None and any(abs(score_val - boundary) <= 3.0 for boundary in BAND_THRESHOLDS):
        triggers.add("E2")

    # --- E3: NLI vs Matcher disagreement ---
    if meta.get("nli_disagreement") or "NLI_DISAGREEMENT" in meta_flags:
        triggers.add("E3")

    for j in judgments_list:
        j_dict = j if isinstance(j, dict) else j.model_dump()
        nli_v = j_dict.get("nli_verdict")
        match_v = j_dict.get("verdict")
        if nli_v and match_v and str(nli_v).upper() != str(match_v).upper():
            triggers.add("E3")
        if j_dict.get("nli_disagreement") or j_dict.get("rationale_code") == "NLI_DISAGREEMENT":
            triggers.add("E3")
        if "NLI_DISAGREEMENT" in j_dict.get("flags", []):
            triggers.add("E3")

    # --- E4: >= 60% supporting atoms are T0 (mention/skill list/summary) ---
    all_supp_atoms: list[str] = []
    for j in judgments_list:
        j_dict = j if isinstance(j, dict) else j.model_dump()
        supps = j_dict.get("support_atoms") or j_dict.get("support_atom_ids") or []
        for s in supps:
            all_supp_atoms.append(str(s))

    if all_supp_atoms:
        atom_kind_map: dict[str, str] = {}
        atom_tier_map: dict[str, str] = {}
        for a in atoms_list:
            akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else "")
            akind = getattr(a, "kind", None) or (a.get("kind") if isinstance(a, dict) else "")
            atier = getattr(a, "tier", None) or (a.get("tier") if isinstance(a, dict) else None)
            if akey:
                atom_kind_map[str(akey)] = str(akind)
                if atier:
                    atom_tier_map[str(akey)] = str(atier)

        t0_count = 0
        for sa in all_supp_atoms:
            kind = atom_kind_map.get(sa, "")
            tier = atom_tier_map.get(sa, "")
            if kind in T0_ATOM_KINDS or tier == "T0":
                t0_count += 1

        t0_ratio = t0_count / len(all_supp_atoms)
        if t0_ratio >= 0.60:
            triggers.add("E4")

    if "HIGH_T0_EVIDENCE_RATIO" in meta_flags or "E4" in meta_flags:
        triggers.add("E4")

    # --- E5: INCONSISTENT_ALLOCATION or DATE_UNCERTAIN ---
    e5_indicators = {"INCONSISTENT_ALLOCATION", "DATE_UNCERTAIN"}
    if meta_flags.intersection(e5_indicators):
        triggers.add("E5")

    for j in judgments_list:
        j_dict = j if isinstance(j, dict) else j.model_dump()
        j_flags = set(j_dict.get("flags", []))
        if j_flags.intersection(e5_indicators):
            triggers.add("E5")

    # Check atoms for flags
    for a in atoms_list:
        a_flags = set(getattr(a, "flags", None) or (a.get("flags") if isinstance(a, dict) else []) or [])
        if a_flags.intersection(e5_indicators):
            triggers.add("E5")

    # --- E6: HIDDEN_TEXT or INJECTION_SUSPECT ---
    e6_indicators = {"HIDDEN_TEXT", "PROMPT_INJECTION", "INJECTION_SUSPECT", "SECURITY_ALERT"}
    if meta_flags.intersection(e6_indicators):
        triggers.add("E6")

    for a in atoms_list:
        a_vis = getattr(a, "visibility", None) or (a.get("visibility") if isinstance(a, dict) else "")
        if str(a_vis).upper() == "HIDDEN":
            triggers.add("E6")
        a_flags = set(getattr(a, "flags", None) or (a.get("flags") if isinstance(a, dict) else []) or [])
        if a_flags.intersection(e6_indicators):
            triggers.add("E6")

    for j in judgments_list:
        j_dict = j if isinstance(j, dict) else j.model_dump()
        j_flags = set(j_dict.get("flags", []))
        if j_flags.intersection(e6_indicators):
            triggers.add("E6")

    return sorted(list(triggers))


def build_critic_user_prompt(critic_input: CriticInput) -> str:
    """Formats requirement facets, Matcher judgments, and atoms for Critic LLM review."""
    lines: list[str] = [
        f"### Adversarial Verification for Candidate: {critic_input.candidate_id}",
        f"Active Escalation Triggers: {', '.join(critic_input.escalation_triggers) if critic_input.escalation_triggers else 'None'}",
        "\n### Facet Judgments Under Review (from Matcher Agent):",
    ]

    judgments_by_key: dict[str, Any] = {}
    for j in critic_input.judgments:
        j_dict = j if isinstance(j, dict) else j.model_dump()
        fkey = j_dict.get("facet_key", "")
        if fkey:
            judgments_by_key[fkey] = j_dict

    # Review target facets or all facets present in judgments
    target_facets = critic_input.facets_to_review or [
        {"facet_key": k, "hypothesis": j.get("hypothesis", "")} for k, j in judgments_by_key.items()
    ]

    for f in target_facets:
        fkey = f.get("facet_key", "")
        hyp = f.get("hypothesis", "")
        j = judgments_by_key.get(fkey, {})
        matcher_verdict = j.get("verdict", "UNKNOWN")
        matcher_depth = j.get("depth_level", "L0")
        matcher_analysis = j.get("analysis", "(no analysis)")
        supp_atoms = j.get("support_atoms", [])
        lines.append(
            f'- Facet [{fkey}]: "{hyp}"\n'
            f"  Matcher Verdict: {matcher_verdict} (depth: {matcher_depth})\n"
            f"  Matcher Analysis: {matcher_analysis}\n"
            f"  Claimed Support Atoms: {', '.join(supp_atoms) if supp_atoms else 'none'}"
        )

    lines.append("\n### Candidate Evidence Atoms:")
    for a in critic_input.atoms:
        akey = getattr(a, "atom_key", None) or (a.get("atom_key") if isinstance(a, dict) else "")
        akind = getattr(a, "kind", None) or (a.get("kind") if isinstance(a, dict) else "")
        eref = getattr(a, "entry_ref", None) or (a.get("entry_ref") if isinstance(a, dict) else None)
        text = getattr(a, "text_redacted", None) or (a.get("text_redacted") if isinstance(a, dict) else "")
        tier = getattr(a, "tier", None) or (a.get("tier") if isinstance(a, dict) else "")

        claim_tag = " [T0/CLAIM/MENTION_ONLY]" if akind in T0_ATOM_KINDS or tier == "T0" else ""
        ref_str = f" [entry: {eref}]" if eref else ""
        lines.append(f"- [{akey}] (kind: {akind}{ref_str}{claim_tag}): {text}")

    if critic_input.raw_title:
        lines.append(
            f"\n### Candidate Stated Title: '{critic_input.raw_title}' (context_only, weak prior)\n"
            "REMINDER: Do not allow stated title to justify ungrounded competency claims."
        )

    lines.append(
        "\n### Adversarial Task Instructions:\n"
        "1. Scrutinize whether evidence atoms literally prove Matcher's claims. Watch for keyword stuffing.\n"
        "2. Any evidence grounded primarily in T0 mentions/claims is strictly capped at PARTIAL / L0.\n"
        "3. DOWNGRADE weak claims. UPGRADE only if unambiguous evidence was missed.\n"
        "4. Enforce R1: In your output JSON, provide freeform 'analysis' BEFORE 'verdict_action' and 'final_verdict'.\n"
        "Output strictly valid JSON conforming to the Critic schema."
    )
    return "\n".join(lines)


async def run_critic_agent(
    critic_input: CriticInput | dict[str, Any],
    client: Any = None,
    tenant_id: uuid.UUID | None = None,
    model: str = "cc/claude-sonnet-5-5",
) -> CriticOutput:
    """Invokes the Critic Agent via 9Router using an independent model family (cc/claude-sonnet-5-5).

    Args:
        critic_input: Input payload containing judgments, atoms, and escalation triggers.
        client: Optional ModelGateway instance or mock client.
        tenant_id: Optional tenant isolation identifier.
        model: LLM model identifier (defaults to cc/claude-sonnet-5-5).

    Returns:
        CriticOutput containing adversarial facet reviews and disagreement status.
    """
    inp = critic_input if isinstance(critic_input, CriticInput) else CriticInput.model_validate(critic_input)
    sys_prompt = load_critic_system_prompt()
    user_prompt = build_critic_user_prompt(inp)

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_prompt},
    ]

    gateway = client if client is not None else ModelGateway()
    logger.info(
        f"Calling Critic Agent for candidate {inp.candidate_id} with model {model} (triggers: {inp.escalation_triggers})"
    )

    response_data = await gateway.call_chat(
        messages=messages,
        task="critic",
        tenant_id=tenant_id,
        json_mode=True,
        model=model,
    )

    if isinstance(response_data, dict):
        if "raw_content" in response_data:
            parsed = parse_llm_json(response_data["raw_content"])
            raw_dict = parsed if isinstance(parsed, dict) else {}
        else:
            raw_dict = response_data
    elif isinstance(response_data, str):
        parsed = parse_llm_json(response_data)
        raw_dict = parsed if isinstance(parsed, dict) else {}
    else:
        raw_dict = {}

    # Extract or build reviews
    facet_reviews: list[CriticFacetReview] = []
    raw_reviews = (
        raw_dict.get("facet_reviews")
        or raw_dict.get("reviews")
        or raw_dict.get("evaluations")
        or raw_dict.get("results")
        or []
    )

    # Build map of original judgments for comparison
    matcher_map: dict[str, Any] = {}
    for j in inp.judgments:
        j_dict = j if isinstance(j, dict) else j.model_dump()
        fkey = j_dict.get("facet_key", "")
        if fkey:
            matcher_map[fkey] = j_dict

    has_disagreement = False
    disagreement_flags: list[str] = []

    for r_item in raw_reviews:
        try:
            review = CriticFacetReview.model_validate(r_item)
            fkey = review.facet_key
            original_j = matcher_map.get(fkey)
            if original_j:
                orig_verdict_str = str(original_j.get("verdict", "")).upper()
                with contextlib.suppress(Exception):
                    review.original_verdict = FacetVerdict(orig_verdict_str)

                # Detect disagreement
                is_dispute = review.verdict_action in (VerdictAction.DOWNGRADE, VerdictAction.UPGRADE) or (
                    orig_verdict_str and review.final_verdict.value != orig_verdict_str
                )
                if is_dispute:
                    review.is_disagreement = True
                    has_disagreement = True
                    flag_name = f"{review.verdict_action.value}:{fkey}"
                    if flag_name not in disagreement_flags:
                        disagreement_flags.append(flag_name)

            facet_reviews.append(review)
        except Exception as e:
            logger.warning(f"Failed to parse Critic review item {r_item}: {e}")

    if has_disagreement and "AGENT_DISAGREEMENT" not in disagreement_flags:
        disagreement_flags.append("AGENT_DISAGREEMENT")

    rec = "MANUAL_CHECK" if has_disagreement else raw_dict.get("final_recommendation")

    return CriticOutput(
        candidate_id=inp.candidate_id,
        facet_reviews=facet_reviews,
        overall_reasoning=raw_dict.get("overall_reasoning"),
        escalation_triggers=inp.escalation_triggers,
        has_disagreement=has_disagreement,
        disagreement_flags=disagreement_flags,
        final_recommendation=rec,
    )


def resolve_facet_dispute(
    matcher_verdict: str | FacetVerdict,
    critic_verdict: str | FacetVerdict,
    verdict_action: str | VerdictAction | None = None,
) -> tuple[FacetVerdict, bool, list[str]]:
    """Resolves a dispute between Matcher and Critic by selecting the more conservative verdict.

    Conservative ranking:
    CONTRADICTED (most conservative) < NOT_ENTAILED < UNKNOWN < PARTIAL < ENTAILED (least conservative).

    Returns:
        tuple of (resolved_verdict, is_disagreement, flags)
    """
    m_str = matcher_verdict.value if isinstance(matcher_verdict, FacetVerdict) else str(matcher_verdict).upper()
    c_str = critic_verdict.value if isinstance(critic_verdict, FacetVerdict) else str(critic_verdict).upper()
    action = (
        verdict_action.value
        if isinstance(verdict_action, VerdictAction)
        else (str(verdict_action).upper() if verdict_action else None)
    )

    flags: list[str] = []
    is_disagreement = False

    if m_str != c_str or action in ("DOWNGRADE", "UPGRADE"):
        is_disagreement = True
        flags.append("AGENT_DISAGREEMENT")

    # Select conservative fallback
    m_rank = VERDICT_CONSERVATISM_RANK.get(m_str, 2)
    c_rank = VERDICT_CONSERVATISM_RANK.get(c_str, 2)

    # Pick the lower rank (more conservative)
    resolved_str = m_str if m_rank <= c_rank else c_str

    try:
        resolved_verdict = FacetVerdict(resolved_str)
    except ValueError:
        resolved_verdict = FacetVerdict.UNKNOWN

    return resolved_verdict, is_disagreement, flags


def resolve_disagreements(
    judgments: list[FacetEvaluationResult | dict[str, Any]],
    critic_output: CriticOutput | dict[str, Any],
) -> tuple[list[FacetEvaluationResult], list[str], str | None]:
    """Applies conservative resolution across all facet judgments when Critic disagrees.

    Returns:
        (resolved_judgments, combined_flags, recommendation)
    """
    output = critic_output if isinstance(critic_output, CriticOutput) else CriticOutput.model_validate(critic_output)
    critic_reviews = {r.facet_key: r for r in output.facet_reviews}

    resolved: list[FacetEvaluationResult] = []
    flags: list[str] = list(output.disagreement_flags)
    has_dispute = output.has_disagreement

    for j in judgments:
        j_obj = j if isinstance(j, FacetEvaluationResult) else FacetEvaluationResult.model_validate(j)
        fkey = j_obj.facet_key
        review = critic_reviews.get(fkey)

        if review is not None:
            resolved_verdict, is_dispute, dispute_flags = resolve_facet_dispute(
                matcher_verdict=j_obj.verdict,
                critic_verdict=review.final_verdict,
                verdict_action=review.verdict_action,
            )
            if is_dispute:
                has_dispute = True
                for df in dispute_flags:
                    if df not in flags:
                        flags.append(df)

            # Construct new resolved evaluation result
            resolved_item = FacetEvaluationResult(
                facet_key=fkey,
                analysis=f"[Critic Review: {review.verdict_action.value}] {review.analysis}",
                verdict=resolved_verdict,
                support_atoms=review.support_atoms if review.support_atoms else j_obj.support_atoms,
                depth_level=review.depth_level if review.depth_level else j_obj.depth_level,
                rationale_code=f"CRITIC_{review.verdict_action.value}",
                needs_more_context=j_obj.needs_more_context,
            )
            resolved.append(resolved_item)
        else:
            resolved.append(j_obj)

    recommendation = "MANUAL_CHECK" if has_dispute else None
    return resolved, flags, recommendation
