"""Graph B: Autonomous Job Screening and Matching Pipeline (v2.1).

Implements Section C4, C5, C6, C7, and C10 of Blueprint v2.1:
1. S0: Compiles JD or requirement criteria into RequirementIR (5 facets per role qualification).
2. S3: Retrieves relevant visible evidence per facet via S3 hybrid retriever.
3. S4: Tests S4 Ontology Shortcut to short-circuit capability matches without LLM calls.
4. S6: Executes Matcher Agent with Directional Entailment (R1 analysis-first) for remaining facets.
5. S2: Aggregates temporal duration via Weighted Calendar Union sweep-line algorithm.
6. S7: Aggregates facets and temporal results into requirement states (STRONG, PARTIAL, etc.).
7. Escalation: Evaluates triggers E1-E6. If triggered, dispatches Critic Agent (cc/claude-sonnet-5-5).
8. S9: Computes final composite score and band classification via Scorer v2.
9. S10: Produces deterministic candidate ranking with transparent grounding atoms.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from src.agents.critic import (
    CriticFacetReview,
    CriticInput,
    evaluate_escalation_triggers,
    resolve_disagreements,
    run_critic_agent,
)
from src.agents.matcher import (
    FacetEvaluationInput,
    FacetEvaluationResult,
    run_matcher_agent,
)
from src.domain.atoms import EvidenceAtom
from src.domain.matching import (
    AggregatedRequirementResult,
    RequirementState,
    aggregate_requirement_facets,
    partition_facets_by_ontology_shortcut,
)
from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import get_ontology_graph
from src.domain.requirements.compiler import (
    compile_job_requirements_ir,
    decompose_role_to_facets,
    save_domain_duration_to_db,
    save_facet_judgment_to_db,
    save_requirement_ir_to_db,
)
from src.domain.requirements.schemas import (
    RequirementFacet,
    RequirementSetIR,
)
from src.domain.scoring.scorer_v2 import ScoreResultV2, rank_v2, score_v2
from src.domain.temporal.date_normalizer import normalize_date_range
from src.domain.temporal.weighted_union import (
    DurationPolicy,
    TemporalEntry,
    calculate_weighted_union,
    compute_entry_weight,
)
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger


@dataclass
class CandidateInput:
    """Input representation of a candidate to be evaluated in Graph B."""

    candidate_id: str | uuid.UUID
    atoms: list[EvidenceAtom] = field(default_factory=list)
    profile_id: str | uuid.UUID | None = None
    raw_title: str | None = None
    experiences: list[Any] = field(default_factory=list)
    atom_tags: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)


@dataclass
class CandidateScreeningResult:
    """Detailed evaluation result for an individual candidate."""

    candidate_id: str
    band: str
    final_score: float
    raw_score: float
    recommendation: str
    color: str
    profile_id: str | None = None
    rank: int = 1
    requirement_results: dict[str, AggregatedRequirementResult] = field(default_factory=dict)
    facet_judgments: list[FacetEvaluationResult | dict[str, Any]] = field(default_factory=list)
    critic_reviews: list[CriticFacetReview] = field(default_factory=list)
    grounding_atoms: list[dict[str, Any]] = field(default_factory=list)
    escalation_triggers: list[str] = field(default_factory=list)
    domain_durations: dict[str, Any] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    category_scores: dict[str, float] = field(default_factory=dict)
    depth_breakdown: dict[str, str] = field(default_factory=dict)
    score_result: ScoreResultV2 | None = None
    strong_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "rank": self.rank,
            "band": self.band,
            "final_score": self.final_score,
            "raw_score": self.raw_score,
            "recommendation": self.recommendation,
            "color": self.color,
            "flags": self.flags,
            "escalation_triggers": self.escalation_triggers,
            "grounding_atoms_count": len(self.grounding_atoms),
            "requirement_states": {
                req_id: r.state.value if hasattr(r.state, "value") else str(r.state)
                for req_id, r in self.requirement_results.items()
            },
        }


@dataclass
class ScreeningResult:
    """Full ranking and evaluation result produced by Graph B."""

    run_id: uuid.UUID
    requirement_set_ir: RequirementSetIR
    candidates: list[CandidateScreeningResult] = field(default_factory=list)

    @property
    def top_candidate(self) -> CandidateScreeningResult | None:
        return self.candidates[0] if self.candidates else None


def _build_temporal_entries(experiences: Sequence[Any]) -> list[TemporalEntry]:
    """Converts diverse experience objects or dicts into TemporalEntry for calendar union."""
    entries: list[TemporalEntry] = []
    for idx, exp in enumerate(experiences, start=1):
        entry_id = str(getattr(exp, "entry_ref", None) or getattr(exp, "entry_id", None) or f"exp_{idx}")
        emp_type = getattr(exp, "employment_type", None) or (
            exp.get("employment_type") if isinstance(exp, dict) else None
        )
        emp_type = (emp_type or "full-time").strip().lower()

        # Interval resolution
        interval = getattr(exp, "interval", None)
        if interval is None:
            start_d = getattr(exp, "date_text_start", None) or (
                exp.get("date_text_start") or exp.get("start_date") if isinstance(exp, dict) else None
            )
            end_d = getattr(exp, "date_text_end", None) or (
                exp.get("date_text_end") or exp.get("end_date") if isinstance(exp, dict) else None
            )
            interval = normalize_date_range(start_raw=start_d, end_raw=end_d)

        # Domain weights from allocations
        domain_weights: dict[str, float] = {}
        raw_allocs = (
            getattr(exp, "domain_allocations", None)
            or (exp.get("domain_allocations") if isinstance(exp, dict) else [])
        )
        allocations = list(raw_allocs) if raw_allocs else []
        for alloc in allocations:
            dom = getattr(alloc, "domain", None) or (alloc.get("domain") if isinstance(alloc, dict) else None)
            lvl = getattr(alloc, "level", None) or (alloc.get("level") if isinstance(alloc, dict) else "PRIMARY")
            lvl_val = getattr(lvl, "value", lvl)
            if dom:
                w, _ = compute_entry_weight(allocation_level=str(lvl_val), employment_type=emp_type)
                domain_weights[str(dom).lower()] = w

        entries.append(
            TemporalEntry(
                entry_id=entry_id,
                interval=interval,
                weight=1.0,
                domain_weights=domain_weights,
                employment_type=emp_type,
            )
        )
    return entries


class ScreeningPipeline:
    """Graph B: Autonomous Job Screening and Matching Pipeline."""

    def __init__(
        self,
        client: Any = None,
        critic_client: Any = None,
        ontology: OntologyGraph | None = None,
    ) -> None:
        self.client = client
        self.critic_client = critic_client or client
        self.ontology = ontology or get_ontology_graph()

    async def run(
        self,
        candidates: Sequence[CandidateInput | dict[str, Any]],
        job_description: str | None = None,
        requirement_set: RequirementSetIR | dict[str, Any] | None = None,
        run_id: uuid.UUID | str | None = None,
        tenant_id: uuid.UUID | str | None = None,
        save_to_db: bool = False,
        conn: Any = None,
        critic_model: str = "cc/claude-sonnet-5-5",
    ) -> ScreeningResult:
        """Executes full Graph B screening and matching pipeline.

        Args:
            candidates: Sequence of candidate input records or dictionaries.
            job_description: Optional raw Job Description text (compiled into RequirementIR).
            requirement_set: Optional pre-compiled RequirementSetIR or dictionary.
            run_id: Optional screening run UUID.
            tenant_id: Optional tenant identifier.
            save_to_db: Whether to persist screening records to PostgreSQL.
            conn: Optional database connection.
            critic_model: Model string for Critic Agent escalation.

        Returns:
            ScreeningResult containing deterministically ranked candidate screening results.
        """
        active_run_id = uuid.UUID(str(run_id)) if run_id else uuid.uuid4()
        active_tenant_id = uuid.UUID(str(tenant_id)) if tenant_id else uuid.uuid4()

        # ------------------------------------------------------------------
        # Step S0: Compile / Load RequirementIR
        # ------------------------------------------------------------------
        req_set_ir: RequirementSetIR
        if requirement_set is not None:
            if isinstance(requirement_set, RequirementSetIR):
                req_set_ir = requirement_set
            else:
                req_set_ir = RequirementSetIR.model_validate(requirement_set)
        elif job_description:
            req_set_ir = await compile_job_requirements_ir(
                jd_text=job_description,
                tenant_id=active_tenant_id,
                use_llm=(self.client is not None),
                client=self.client,
                ontology=self.ontology,
            )
        else:
            raise ValueError("Either job_description or requirement_set must be provided to ScreeningPipeline.")

        # Ensure all requirements have decomposed facets
        for req in req_set_ir.requirements:
            if not req.facets and req.description:
                req.facets = decompose_role_to_facets(
                    role_or_title=req.description,
                    ontology=self.ontology,
                )

        logger.info(
            f"ScreeningPipeline S0: Processing {len(req_set_ir.requirements)} requirements for "
            f"{len(candidates)} candidates (run_id={active_run_id})"
        )

        candidate_results: list[CandidateScreeningResult] = []

        # ------------------------------------------------------------------
        # Evaluate each candidate independently
        # ------------------------------------------------------------------
        for cand in candidates:
            c_res = await self._evaluate_single_candidate(
                cand=cand,
                req_set_ir=req_set_ir,
                run_id=active_run_id,
                tenant_id=active_tenant_id,
                critic_model=critic_model,
            )
            candidate_results.append(c_res)

        # ------------------------------------------------------------------
        # Step S10: Rank Candidates Deterministically
        # ------------------------------------------------------------------
        items_to_rank: list[dict[str, Any]] = []
        for c_res in candidate_results:
            items_to_rank.append(
                {
                    "candidate_id": c_res.candidate_id,
                    "result": c_res.score_result,
                    "strong_count": c_res.strong_count,
                    "res_obj": c_res,
                }
            )

        ranked_items = rank_v2(items_to_rank, run_id=str(active_run_id))
        ranked_candidates: list[CandidateScreeningResult] = []
        for rank_idx, item in enumerate(ranked_items, start=1):
            cand_obj: CandidateScreeningResult = item["res_obj"]
            cand_obj.rank = rank_idx
            ranked_candidates.append(cand_obj)

        # ------------------------------------------------------------------
        # Database Persistence (optional)
        # ------------------------------------------------------------------
        if save_to_db:
            if conn is not None:
                await self._persist_screening_artifacts(
                    conn=conn,
                    run_id=active_run_id,
                    tenant_id=active_tenant_id,
                    req_set=req_set_ir,
                    candidate_results=ranked_candidates,
                )
            else:
                async with get_connection() as managed_conn:
                    await self._persist_screening_artifacts(
                        conn=managed_conn,
                        run_id=active_run_id,
                        tenant_id=active_tenant_id,
                        req_set=req_set_ir,
                        candidate_results=ranked_candidates,
                    )

        return ScreeningResult(
            run_id=active_run_id,
            requirement_set_ir=req_set_ir,
            candidates=ranked_candidates,
        )

    async def _evaluate_single_candidate(
        self,
        cand: CandidateInput | dict[str, Any],
        req_set_ir: RequirementSetIR,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        critic_model: str,
    ) -> CandidateScreeningResult:
        """Evaluates an individual candidate across all requirements."""
        if isinstance(cand, dict):
            c_id = str(cand.get("candidate_id") or uuid.uuid4())
            p_id = str(cand.get("profile_id")) if cand.get("profile_id") else None
            atoms = cand.get("atoms", [])
            raw_title = cand.get("raw_title")
            experiences = cand.get("experiences", [])
            atom_tags = cand.get("atom_tags", {})
            metadata = cand.get("metadata", {})
            initial_flags = list(cand.get("flags", []))
        else:
            c_id = str(cand.candidate_id)
            p_id = str(cand.profile_id) if cand.profile_id else None
            atoms = cand.atoms
            raw_title = cand.raw_title
            experiences = cand.experiences
            atom_tags = cand.atom_tags
            metadata = cand.metadata
            initial_flags = list(cand.flags)

        candidate_flags = list(initial_flags)
        if metadata.get("flags"):
            candidate_flags.extend(metadata["flags"])
        if metadata.get("has_hidden_text"):
            candidate_flags.append("HIDDEN_TEXT")

        all_facet_judgments: list[FacetEvaluationResult] = []
        requirement_results: dict[str, AggregatedRequirementResult] = {}
        all_domain_durations: dict[str, Any] = {}

        temporal_entries = _build_temporal_entries(experiences)
        facet_to_req_id: dict[str, str] = {}

        # ------------------------------------------------------------------
        # Process Each Requirement
        # ------------------------------------------------------------------
        for req in req_set_ir.requirements:
            req_facets = req.facets or []
            for f in req_facets:
                facet_to_req_id[f.facet_key] = req.requirement_id

            # Step S4: Ontology Shortcut
            facets_for_shortcut: list[RequirementFacet | dict[str, Any]] = list(req_facets)
            shortcut_dict, remaining_facets = partition_facets_by_ontology_shortcut(
                facets=facets_for_shortcut,
                candidate_atoms=atoms,
                ontology=self.ontology,
                atom_tags=atom_tags,
            )
            shortcut_judgments = list(shortcut_dict.values())

            # Step S6: Matcher Agent for remaining facets
            matcher_judgments: list[FacetEvaluationResult] = []
            if remaining_facets:
                facets_for_matcher: list[RequirementFacet | FacetEvaluationInput | dict[str, Any]] = list(remaining_facets)
                # Retrieve evidence per facet
                matcher_output = await run_matcher_agent(
                    facets=facets_for_matcher,
                    candidate_atoms=atoms,
                    client=self.client,
                    tenant_id=tenant_id,
                    raw_title=raw_title,
                    all_candidate_atoms=atoms,
                )
                matcher_judgments = matcher_output.evaluations

            combined_req_judgments = list(shortcut_judgments) + list(matcher_judgments)
            all_facet_judgments.extend(combined_req_judgments)

            # Step S2: Temporal Engine (Weighted Calendar Union)
            domain_duration_dict: dict[str, Any] | None = None
            if req.duration_policy is not None or req.target_domains:
                domain_name = req.target_domains[0] if req.target_domains else "general"
                min_m = req.duration_policy.min_months if req.duration_policy else 0.0

                dur_policy = DurationPolicy(
                    alloc_weights=(
                        req.duration_policy.alloc_weights
                        if req.duration_policy and req.duration_policy.alloc_weights
                        else None
                    )
                    or {"PRIMARY": 1.0, "SECONDARY": 0.5, "INCIDENTAL": 0.0},
                    emp_weights=(
                        req.duration_policy.emp_weights
                        if req.duration_policy and req.duration_policy.emp_weights
                        else None
                    )
                    or {
                        "full-time": 1.0,
                        "full_time": 1.0,
                        "kontrak": 1.0,
                        "part-time": 0.5,
                        "magang": 0.5,
                        "internship": 0.5,
                        "freelance": 0.75,
                        "unknown": 1.0,
                    },
                )

                union_res = calculate_weighted_union(
                    entries=temporal_entries,
                    domain=domain_name,
                    min_months=min_m,
                    policy=dur_policy,
                )

                domain_duration_dict = {
                    "domain": domain_name,
                    "months_lo": union_res.months_lo,
                    "months_hi": union_res.months_hi,
                    "month_ledger": union_res.month_ledger,
                    "state": union_res.state,
                    "flags": union_res.flags,
                    "min_months": min_m,
                }
                all_domain_durations[req.requirement_id] = domain_duration_dict
                if union_res.flags:
                    candidate_flags.extend(union_res.flags)

            # Step S7: Aggregate Requirement Facets and Temporal Duration
            combined_judgments_any: list[FacetEvaluationResult | dict[str, Any]] = list(combined_req_judgments)
            agg_result = aggregate_requirement_facets(
                requirement=req,
                judgments=combined_judgments_any,
                candidate_atoms=atoms,
                domain_duration=domain_duration_dict,
            )
            requirement_results[req.requirement_id] = agg_result
            if agg_result.flags:
                candidate_flags.extend(agg_result.flags)

        # ------------------------------------------------------------------
        # Step S8: Escalation Triggers and Critic Agent
        # ------------------------------------------------------------------
        prelim_states = {
            req_id: r.state.value if hasattr(r.state, "value") else str(r.state)
            for req_id, r in requirement_results.items()
        }
        req_set_dict = req_set_ir.model_dump()
        all_judgments_any: list[FacetEvaluationResult | dict[str, Any]] = list(all_facet_judgments)

        prelim_score = score_v2(
            states=prelim_states,
            requirement_set=req_set_dict,
            facet_judgments=all_judgments_any,
            atoms=atoms,
            flags=candidate_flags,
        )

        escalation_triggers = evaluate_escalation_triggers(
            candidate_id=c_id,
            requirement_scores=prelim_score,
            judgments=all_judgments_any,
            atoms=atoms,
            candidate_metadata=metadata,
        )

        critic_reviews: list[CriticFacetReview] = []
        final_facet_judgments = list(all_facet_judgments)

        if escalation_triggers:
            logger.info(
                f"Escalation triggers active for candidate {c_id}: {escalation_triggers}. Invoking Critic Agent."
            )
            critic_input = CriticInput(
                candidate_id=c_id,
                judgments=all_judgments_any,
                atoms=atoms,
                escalation_triggers=escalation_triggers,
                requirement_scores={
                    "final_score": prelim_score.final_score,
                    "band": prelim_score.band,
                },
                raw_title=raw_title,
            )
            critic_output = await run_critic_agent(
                critic_input=critic_input,
                client=self.critic_client,
                tenant_id=tenant_id,
                model=critic_model,
            )
            critic_reviews = critic_output.facet_reviews

            # Resolve disputes and update judgments if downgraded
            all_judgments_for_dispute: list[FacetEvaluationResult | dict[str, Any]] = list(all_facet_judgments)
            resolved_judgments, critic_flags, _ = resolve_disagreements(
                judgments=all_judgments_for_dispute,
                critic_output=critic_output,
            )
            final_facet_judgments = resolved_judgments
            candidate_flags.extend(critic_flags)

            # Re-aggregate requirements that experienced judgment changes
            re_judgments_by_req: dict[str, list[FacetEvaluationResult]] = {}
            for j in final_facet_judgments:
                rid = facet_to_req_id.get(j.facet_key)
                if rid:
                    re_judgments_by_req.setdefault(rid, []).append(j)

            for req in req_set_ir.requirements:
                if req.requirement_id in re_judgments_by_req:
                    re_judgments_any: list[FacetEvaluationResult | dict[str, Any]] = list(re_judgments_by_req[req.requirement_id])
                    re_agg = aggregate_requirement_facets(
                        requirement=req,
                        judgments=re_judgments_any,
                        candidate_atoms=atoms,
                        domain_duration=all_domain_durations.get(req.requirement_id),
                    )
                    requirement_results[req.requirement_id] = re_agg
                    if re_agg.flags:
                        candidate_flags.extend(re_agg.flags)

        # ------------------------------------------------------------------
        # Step S9: Final Composite Score via Scorer v2
        # ------------------------------------------------------------------
        final_states = {
            req_id: r.state.value if hasattr(r.state, "value") else str(r.state)
            for req_id, r in requirement_results.items()
        }
        all_candidate_flags = sorted(list(set(candidate_flags)))
        final_judgments_any: list[FacetEvaluationResult | dict[str, Any]] = list(final_facet_judgments)

        final_scoring = score_v2(
            states=final_states,
            requirement_set=req_set_dict,
            facet_judgments=final_judgments_any,
            atoms=atoms,
            flags=all_candidate_flags,
        )

        # ------------------------------------------------------------------
        # Transparent Grounding Atoms Resolution
        # ------------------------------------------------------------------
        used_atom_keys: set[str] = set()
        for fj in final_facet_judgments:
            supp = getattr(fj, "support_atoms", None) or (fj.get("support_atoms", []) if isinstance(fj, dict) else [])
            for sid in supp:
                used_atom_keys.add(str(sid))

        grounding_atoms: list[dict[str, Any]] = []
        for atom in atoms:
            ak = getattr(atom, "atom_key", None) or (atom.get("atom_key") if isinstance(atom, dict) else "")
            if ak in used_atom_keys:
                if hasattr(atom, "to_dict"):
                    grounding_atoms.append(atom.to_dict())
                elif isinstance(atom, dict):
                    grounding_atoms.append(dict(atom))
                else:
                    grounding_atoms.append(
                        {
                            "atom_key": ak,
                            "kind": getattr(atom, "kind", ""),
                            "entry_ref": getattr(atom, "entry_ref", None),
                            "page": getattr(atom, "page", 1),
                            "char_start": getattr(atom, "char_start", 0),
                            "char_end": getattr(atom, "char_end", 0),
                            "red_start": getattr(atom, "red_start", 0),
                            "red_end": getattr(atom, "red_end", 0),
                            "text_redacted": getattr(atom, "text_redacted", ""),
                            "visibility": getattr(atom, "visibility", "VISIBLE"),
                        }
                    )

        return CandidateScreeningResult(
            candidate_id=c_id,
            profile_id=p_id,
            band=final_scoring.band,
            final_score=final_scoring.final_score,
            raw_score=final_scoring.raw_score,
            recommendation=final_scoring.recommendation,
            color=final_scoring.color,
            requirement_results=requirement_results,
            facet_judgments=final_judgments_any,
            critic_reviews=critic_reviews,
            grounding_atoms=grounding_atoms,
            escalation_triggers=escalation_triggers,
            domain_durations=all_domain_durations,
            flags=final_scoring.flags,
            category_scores=final_scoring.category_scores,
            depth_breakdown=final_scoring.depth_breakdown,
            score_result=final_scoring,
            strong_count=len([s for s in final_states.values() if s == "STRONG" or s == RequirementState.STRONG.value]),
        )

    async def _persist_screening_artifacts(
        self,
        conn: Any,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        req_set: RequirementSetIR,
        candidate_results: Sequence[CandidateScreeningResult],
    ) -> None:
        """Persists requirements, facet judgments, durations, and candidate results in Postgres."""
        # 1. Save requirements and facets
        for req in req_set.requirements:
            await save_requirement_ir_to_db(
                conn=conn,
                requirement_set_id=req_set.requirement_set_id,
                tenant_id=tenant_id,
                req=req,
            )

        # Build facet_key -> requirement_id lookup
        facet_to_req: dict[str, str] = {}
        for req in req_set.requirements:
            for f in req.facets or []:
                facet_to_req[f.facet_key] = req.requirement_id

        # 2. Save candidate facet judgments and domain durations
        for c_res in candidate_results:
            c_uuid = uuid.UUID(str(c_res.candidate_id))

            for j in c_res.facet_judgments:
                fkey = getattr(j, "facet_key", "") or (j.get("facet_key", "") if isinstance(j, dict) else "")
                req_id = (
                    facet_to_req.get(fkey, "")
                    or getattr(j, "requirement_id", "")
                    or (j.get("requirement_id", "") if isinstance(j, dict) else "")
                )
                await save_facet_judgment_to_db(
                    conn=conn,
                    run_id=run_id,
                    candidate_id=c_uuid,
                    requirement_id=req_id,
                    facet_key=fkey,
                    tenant_id=tenant_id,
                    verdict=str(getattr(j, "verdict", None) or (j.get("verdict") if isinstance(j, dict) else "UNKNOWN")),
                    method=str(getattr(j, "method", None) or (j.get("method") if isinstance(j, dict) else "llm")),
                    depth_level=getattr(j, "depth_level", None)
                    or (j.get("depth_level") if isinstance(j, dict) else "L0"),
                    analysis=getattr(j, "analysis", "") or (j.get("analysis", "") if isinstance(j, dict) else ""),
                    support_atom_ids=getattr(j, "support_atoms", [])
                    or (j.get("support_atoms", []) if isinstance(j, dict) else []),
                    rationale_code=getattr(j, "rationale_code", None)
                    or (j.get("rationale_code") if isinstance(j, dict) else None),
                )

            for _req_id, dur in c_res.domain_durations.items():
                await save_domain_duration_to_db(
                    conn=conn,
                    run_id=run_id,
                    candidate_id=c_uuid,
                    domain=dur.get("domain", "general"),
                    tenant_id=tenant_id,
                    policy_hash="default_v2_policy",
                    months_lo=float(dur.get("months_lo", 0.0)),
                    months_hi=float(dur.get("months_hi", 0.0)),
                    month_ledger=dur.get("month_ledger", []),
                )

        await conn.commit()


async def run_screening_pipeline(
    candidates: Sequence[CandidateInput | dict[str, Any]],
    job_description: str | None = None,
    requirement_set: RequirementSetIR | dict[str, Any] | None = None,
    run_id: uuid.UUID | str | None = None,
    tenant_id: uuid.UUID | str | None = None,
    client: Any = None,
    critic_client: Any = None,
    ontology: OntologyGraph | None = None,
    save_to_db: bool = False,
    conn: Any = None,
    critic_model: str = "cc/claude-sonnet-5-5",
) -> ScreeningResult:
    """Convenience helper function to execute Graph B ScreeningPipeline."""
    pipeline = ScreeningPipeline(
        client=client,
        critic_client=critic_client,
        ontology=ontology,
    )
    return await pipeline.run(
        candidates=candidates,
        job_description=job_description,
        requirement_set=requirement_set,
        run_id=run_id,
        tenant_id=tenant_id,
        save_to_db=save_to_db,
        conn=conn,
        critic_model=critic_model,
    )
