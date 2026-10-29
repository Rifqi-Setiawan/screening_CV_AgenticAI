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

import asyncio
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from src.agents.critic import (
    CriticFacetReview,
    CriticInput,
    decide_critic_routing,
    evaluate_escalation_triggers,
    resolve_disagreements,
    run_critic_agent,
)
from src.agents.matcher import (
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
from src.domain.matching.domain_inference import apply_domain_inference
from src.domain.matching.retriever import expand_facet_terms, rank_atoms_in_memory
from src.domain.ontology.graph import OntologyGraph
from src.domain.ontology.loader import get_ontology_graph
from src.domain.requirements.compiler import (
    compile_job_requirements_ir,
    decompose_role_to_facets,
    save_critic_review_to_db,
    save_domain_duration_to_db,
    save_facet_judgment_to_db,
    save_requirement_ir_to_db,
)
from src.domain.requirements.facet_narrowing import ROLE_KINDS, apply_facet_narrowing, facet_signature, own_facet
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
from src.infrastructure.config import settings
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
class _PreparedCandidate:
    """Phase-1 outcome for one candidate: judged, aggregated and provisionally scored."""

    c_id: str
    p_id: str | None
    atoms: list[Any]
    raw_title: str | None
    metadata: dict[str, Any]
    candidate_flags: list[str]
    judgments: list[FacetEvaluationResult]
    requirement_results: dict[str, AggregatedRequirementResult]
    all_domain_durations: dict[str, Any]
    req_set_dict: dict[str, Any]
    prelim_score: ScoreResultV2
    triggers: list[str]
    llm_atoms: list[Any]


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
        raw_allocs = getattr(exp, "domain_allocations", None) or (
            exp.get("domain_allocations") if isinstance(exp, dict) else []
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

        # Ensure all requirements have facets: role statements get the role template, other kinds their own facet
        for req in req_set_ir.requirements:
            if not req.facets and req.description:
                if (req.kind or "").upper() in ROLE_KINDS:
                    req.facets = decompose_role_to_facets(
                        role_or_title=req.description,
                        ontology=self.ontology,
                    )
                else:
                    req.facets = [own_facet(req)]

        if settings.FACET_NARROWING_ENABLED:
            narrowed = apply_facet_narrowing(req_set_ir)
            if narrowed:
                logger.info(f"ScreeningPipeline S0: narrowed facets for {narrowed} requirement(s)")

        logger.info(
            f"ScreeningPipeline S0: Processing {len(req_set_ir.requirements)} requirements for "
            f"{len(candidates)} candidates (run_id={active_run_id})"
        )

        # ------------------------------------------------------------------
        # Phase 1: match + aggregate + preliminary score (candidates run concurrently)
        # ------------------------------------------------------------------
        gate = asyncio.Semaphore(max(1, settings.SCREENING_CANDIDATE_CONCURRENCY))

        async def _prepare(c: CandidateInput | dict[str, Any]) -> _PreparedCandidate:
            async with gate:
                return await self._prepare_candidate(cand=c, req_set_ir=req_set_ir, tenant_id=active_tenant_id)

        prepared = list(await asyncio.gather(*(_prepare(c) for c in candidates)))

        # ------------------------------------------------------------------
        # Critic routing: anomalies, provisional top-K and a reproducible random audit sample
        # ------------------------------------------------------------------
        provisional = rank_v2(
            [{"candidate_id": p.c_id, "result": p.prelim_score, "strong_count": 0} for p in prepared],
            run_id=str(active_run_id),
        )
        top_k_ids = {str(item["candidate_id"]) for item in provisional[: max(0, settings.CRITIC_TOP_K)]}
        routing_by_id = {
            p.c_id: decide_critic_routing(
                triggers=p.triggers,
                in_top_k=p.c_id in top_k_ids,
                run_id=str(active_run_id),
                candidate_id=p.c_id,
                audit_rate=settings.CRITIC_RANDOM_AUDIT_RATE,
            )
            for p in prepared
        }

        # ------------------------------------------------------------------
        # Phase 2: Critic audit (only routed candidates) + final score
        # ------------------------------------------------------------------
        async def _finalize(p: _PreparedCandidate) -> CandidateScreeningResult:
            async with gate:
                return await self._finalize_candidate(
                    prep=p,
                    req_set_ir=req_set_ir,
                    routing=routing_by_id[p.c_id],
                    tenant_id=active_tenant_id,
                    critic_model=critic_model,
                )

        candidate_results: list[CandidateScreeningResult] = list(
            await asyncio.gather(*(_finalize(p) for p in prepared))
        )

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

    async def _judge_distinct_facets(
        self,
        req_set_ir: RequirementSetIR,
        atoms: list[Any],
        atom_tags: dict[str, Any],
        raw_title: str | None,
        tenant_id: uuid.UUID,
    ) -> tuple[list[FacetEvaluationResult], list[str]]:
        """Judges every distinct facet of the requirement set exactly once (v2.2).

        Requirements frequently share identical facets (role templates); judging them once per
        requirement multiplied Matcher calls and let one weak facet depress every criterion.
        Returns one judgment per distinct facet signature, in first-seen order.
        """
        distinct: dict[tuple[str, str, tuple[str, ...]], RequirementFacet] = {}
        for req in req_set_ir.requirements:
            for f in req.facets or []:
                distinct.setdefault(facet_signature(f), f)

        # A facet_key must be unique inside one Matcher call: split signatures sharing a key into rounds.
        rounds: list[list[tuple[tuple[str, str, tuple[str, ...]], RequirementFacet]]] = []
        seen_per_key: dict[str, int] = {}
        for sig, facet in distinct.items():
            idx = seen_per_key.get(facet.facet_key, 0)
            seen_per_key[facet.facet_key] = idx + 1
            while len(rounds) <= idx:
                rounds.append([])
            rounds[idx].append((sig, facet))

        judgments: list[FacetEvaluationResult] = []
        matcher_flags: list[str] = []
        for round_items in rounds:
            facets_in_round = [f for _, f in round_items]
            shortcut_dict, remaining = partition_facets_by_ontology_shortcut(
                facets=list(facets_in_round),
                candidate_atoms=atoms,
                ontology=self.ontology,
                atom_tags=atom_tags,
            )
            judgments.extend(shortcut_dict.values())
            if remaining:
                matcher_atoms = self._atoms_for_matcher(remaining, atoms)
                matcher_output = await run_matcher_agent(
                    facets=list(remaining),
                    candidate_atoms=matcher_atoms,
                    client=self.client,
                    tenant_id=tenant_id,
                    raw_title=raw_title,
                    all_candidate_atoms=atoms,
                )
                judgments.extend(matcher_output.evaluations)
                matcher_flags.extend(matcher_output.flags)
        return judgments, matcher_flags

    @staticmethod
    def _llm_visible_atoms(atoms: list[Any], req_set_ir: RequirementSetIR | None = None) -> list[Any]:
        """Atoms the Matcher/Critic may see: kinds that are prestige/age proxies (education) stay out.

        If the recruiter explicitly asked for an education requirement, education atoms are legitimate evidence.
        """
        excluded = set(settings.MATCHER_EXCLUDED_ATOM_KINDS)
        if req_set_ir is not None and any((r.kind or "").upper() == "EDUCATION" for r in req_set_ir.requirements):
            excluded.discard("education")
        if not excluded:
            return atoms
        kept = [
            a
            for a in atoms
            if str(getattr(a, "kind", None) or (a.get("kind") if isinstance(a, dict) else "")) not in excluded
        ]
        return kept or atoms

    @staticmethod
    def _verifiable_atoms(atoms: list[Any], candidate_flags: list[str]) -> list[Any]:
        """Evidence-or-abstain: atoms whose span cannot be located in the CV are not evidence.

        If that would leave no evidence at all the atoms are kept and the candidate is flagged, so a
        parser problem never silently wipes out a CV.
        """
        if not settings.REQUIRE_VERIFIED_SPANS or not atoms:
            return atoms

        def _verified(a: Any) -> bool:
            if hasattr(a, "span_verified"):
                return bool(a.span_verified)
            return int(a.get("char_end") or 0) > int(a.get("char_start") or 0)

        verified = [a for a in atoms if _verified(a)]
        dropped = len(atoms) - len(verified)
        if dropped == 0:
            return atoms
        if not verified:
            candidate_flags.append("SPAN_VERIFICATION_UNAVAILABLE")
            return atoms
        candidate_flags.append(f"UNVERIFIED_SPAN_ATOMS:{dropped}")
        return verified

    def _atoms_for_matcher(self, facets: Sequence[Any], atoms: list[Any]) -> list[Any]:
        """Optional retrieval-before-judging: union of the top-K atoms per facet (0 = send all atoms)."""
        k = int(settings.MATCHER_RETRIEVAL_TOP_K)
        if k <= 0 or not atoms:
            return atoms
        picked: dict[str, Any] = {}
        for facet in facets:
            query_text, terms = expand_facet_terms(facet=facet, ontology=self.ontology)
            for atom in rank_atoms_in_memory(atoms, query_text, terms, None, k=k):
                picked.setdefault(atom.atom_key, atom)
        return list(picked.values()) or atoms

    async def _prepare_candidate(
        self,
        cand: CandidateInput | dict[str, Any],
        req_set_ir: RequirementSetIR,
        tenant_id: uuid.UUID,
    ) -> _PreparedCandidate:
        """Phase 1: match facets, compute durations, aggregate requirements and preliminary score."""
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

        requirement_results: dict[str, AggregatedRequirementResult] = {}
        all_domain_durations: dict[str, Any] = {}
        temporal_entries = _build_temporal_entries(experiences)

        # Steps S4 + S6: every distinct facet is judged once, then shared by the requirements using it.
        atoms = self._verifiable_atoms(atoms, candidate_flags)  # everything downstream sees only verifiable evidence
        llm_atoms = self._llm_visible_atoms(atoms, req_set_ir)
        all_facet_judgments, matcher_flags = await self._judge_distinct_facets(
            req_set_ir, llm_atoms, atom_tags, raw_title, tenant_id
        )
        candidate_flags.extend(matcher_flags)
        if settings.DOMAIN_INFERENCE_ENABLED:
            hypotheses = {f.facet_key: f.hypothesis for r in req_set_ir.requirements for f in r.facets or []}
            all_facet_judgments, inference_flags = apply_domain_inference(all_facet_judgments, hypotheses, atoms)
            candidate_flags.extend(inference_flags)
        judgment_by_key: dict[str, FacetEvaluationResult] = {}
        for j in all_facet_judgments:
            judgment_by_key.setdefault(j.facet_key, j)

        for req in req_set_ir.requirements:
            combined_req_judgments = [
                judgment_by_key[f.facet_key] for f in req.facets or [] if f.facet_key in judgment_by_key
            ]

            # Step S2: Temporal Engine (Weighted Calendar Union)
            domain_duration_dict = self._compute_domain_duration(req, temporal_entries, candidate_flags)
            if domain_duration_dict is not None:
                all_domain_durations[req.requirement_id] = domain_duration_dict

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
            apply_depth=settings.SCORER_DEPTH_FACTORS_ENABLED,
        )
        # Flags raised anywhere upstream (sanitizer, matcher INJECTION_SUSPECT, date engine) feed E4/E5/E6.
        trigger_metadata = {**metadata, "flags": sorted(set(metadata.get("flags", [])) | set(candidate_flags))}
        triggers = evaluate_escalation_triggers(
            candidate_id=c_id,
            requirement_scores=prelim_score,
            judgments=all_judgments_any,
            atoms=atoms,
            candidate_metadata=trigger_metadata,
        )
        return _PreparedCandidate(
            c_id=c_id,
            p_id=p_id,
            atoms=atoms,
            raw_title=raw_title,
            metadata=metadata,
            candidate_flags=candidate_flags,
            judgments=all_facet_judgments,
            requirement_results=requirement_results,
            all_domain_durations=all_domain_durations,
            req_set_dict=req_set_dict,
            prelim_score=prelim_score,
            triggers=triggers,
            llm_atoms=llm_atoms,
        )

    @staticmethod
    def _compute_domain_duration(
        req: Any,
        temporal_entries: list[TemporalEntry],
        candidate_flags: list[str],
    ) -> dict[str, Any] | None:
        if req.duration_policy is None and not req.target_domains:
            return None
        domain_name = req.target_domains[0] if req.target_domains else "general"
        min_m = req.duration_policy.min_months if req.duration_policy else 0.0

        dur_policy = DurationPolicy(
            alloc_weights=(
                req.duration_policy.alloc_weights if req.duration_policy and req.duration_policy.alloc_weights else None
            )
            or {"PRIMARY": 1.0, "SECONDARY": 0.5, "INCIDENTAL": 0.0},
            emp_weights=(
                req.duration_policy.emp_weights if req.duration_policy and req.duration_policy.emp_weights else None
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
        if union_res.flags:
            candidate_flags.extend(union_res.flags)
        return {
            "domain": domain_name,
            "months_lo": union_res.months_lo,
            "months_hi": union_res.months_hi,
            "month_ledger": union_res.month_ledger,
            "state": union_res.state,
            "flags": union_res.flags,
            "min_months": min_m,
        }

    async def _finalize_candidate(
        self,
        prep: _PreparedCandidate,
        req_set_ir: RequirementSetIR,
        routing: list[str],
        tenant_id: uuid.UUID,
        critic_model: str,
    ) -> CandidateScreeningResult:
        """Phase 2: Critic audit (only when routed), re-aggregation, final score and grounding atoms."""
        c_id = prep.c_id
        atoms = prep.atoms
        candidate_flags = list(prep.candidate_flags)
        requirement_results = dict(prep.requirement_results)
        all_judgments_any: list[FacetEvaluationResult | dict[str, Any]] = list(prep.judgments)

        # Step S8: Critic Agent (cross-family audit), routed by anomaly / top-K / random audit
        escalation_triggers = sorted(set(prep.triggers) | set(routing))
        critic_reviews: list[CriticFacetReview] = []
        final_facet_judgments = list(prep.judgments)

        if routing:
            logger.info(f"Critic audit for candidate {c_id}: routing={routing} triggers={prep.triggers}")
            critic_input = CriticInput(
                candidate_id=c_id,
                judgments=all_judgments_any,
                atoms=prep.llm_atoms,
                escalation_triggers=escalation_triggers,
                requirement_scores={
                    "final_score": prep.prelim_score.final_score,
                    "band": prep.prelim_score.band,
                },
                raw_title=prep.raw_title,
            )
            critic_output = await run_critic_agent(
                critic_input=critic_input,
                client=self.critic_client,
                tenant_id=tenant_id,
                model=critic_model,
            )
            critic_reviews = critic_output.facet_reviews

            resolved_judgments, critic_flags, _ = resolve_disagreements(
                judgments=list(prep.judgments),
                critic_output=critic_output,
            )
            final_facet_judgments = resolved_judgments
            candidate_flags.extend(critic_flags)

            # Re-aggregate every requirement that uses a facet (a shared facet feeds several requirements)
            by_key = {j.facet_key: j for j in final_facet_judgments}
            for req in req_set_ir.requirements:
                req_judgments = [by_key[f.facet_key] for f in req.facets or [] if f.facet_key in by_key]
                if not req_judgments:
                    continue
                re_agg = aggregate_requirement_facets(
                    requirement=req,
                    judgments=list(req_judgments),
                    candidate_atoms=atoms,
                    domain_duration=prep.all_domain_durations.get(req.requirement_id),
                )
                requirement_results[req.requirement_id] = re_agg
                if re_agg.flags:
                    candidate_flags.extend(re_agg.flags)

        # Step S9: Final Composite Score via Scorer v2
        final_states = {
            req_id: r.state.value if hasattr(r.state, "value") else str(r.state)
            for req_id, r in requirement_results.items()
        }
        all_candidate_flags = sorted(set(candidate_flags))
        final_judgments_any: list[FacetEvaluationResult | dict[str, Any]] = list(final_facet_judgments)

        final_scoring = score_v2(
            states=final_states,
            requirement_set=prep.req_set_dict,
            facet_judgments=final_judgments_any,
            atoms=atoms,
            flags=all_candidate_flags,
            apply_depth=settings.SCORER_DEPTH_FACTORS_ENABLED,
        )

        # Transparent Grounding Atoms Resolution
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
            profile_id=prep.p_id,
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
            domain_durations=prep.all_domain_durations,
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
                    verdict=str(
                        getattr(j, "verdict", None) or (j.get("verdict") if isinstance(j, dict) else "UNKNOWN")
                    ),
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

            for cr in c_res.critic_reviews:
                fkey = getattr(cr, "facet_key", "") or (cr.get("facet_key", "") if isinstance(cr, dict) else "")
                v_action = getattr(cr, "verdict_action", None) or (
                    cr.get("verdict_action") if isinstance(cr, dict) else "CONFIRM"
                )
                v_action_str = v_action.value if hasattr(v_action, "value") else str(v_action)
                f_verdict = getattr(cr, "final_verdict", None) or (
                    cr.get("final_verdict") if isinstance(cr, dict) else "UNKNOWN"
                )
                f_verdict_str = f_verdict.value if hasattr(f_verdict, "value") else str(f_verdict)
                o_verdict = getattr(cr, "original_verdict", None) or (
                    cr.get("original_verdict") if isinstance(cr, dict) else None
                )
                o_verdict_str = str(getattr(o_verdict, "value", o_verdict)) if o_verdict is not None else None
                d_level = getattr(cr, "depth_level", None) or (cr.get("depth_level") if isinstance(cr, dict) else None)
                d_level_str = str(getattr(d_level, "value", d_level)) if d_level is not None else None
                analysis_text = getattr(cr, "analysis", "") or (cr.get("analysis", "") if isinstance(cr, dict) else "")
                reasoning_text = getattr(cr, "reasoning", None) or (
                    cr.get("reasoning") if isinstance(cr, dict) else None
                )
                supp_atoms = getattr(cr, "support_atoms", []) or (
                    cr.get("support_atoms", []) if isinstance(cr, dict) else []
                )
                is_dis = getattr(cr, "is_disagreement", False) or (
                    cr.get("is_disagreement", False) if isinstance(cr, dict) else False
                )
                cr_flags = getattr(cr, "flags", []) or (cr.get("flags", []) if isinstance(cr, dict) else [])
                await save_critic_review_to_db(
                    conn=conn,
                    run_id=run_id,
                    candidate_id=c_uuid,
                    facet_key=fkey,
                    tenant_id=tenant_id,
                    verdict_action=v_action_str,
                    final_verdict=f_verdict_str,
                    analysis=analysis_text,
                    original_verdict=o_verdict_str,
                    depth_level=d_level_str,
                    reasoning=reasoning_text,
                    support_atoms=supp_atoms,
                    is_disagreement=bool(is_dis),
                    flags=cr_flags,
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
