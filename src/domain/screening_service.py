"""Screening execution service handling asynchronous scoring, eligibility evaluation, and ranking (FX-30 & Graph B)."""

from __future__ import annotations

import contextlib
import json
import uuid
from typing import Any

from src.domain.atoms import EvidenceAtom, atomize_candidate_profile
from src.domain.eligibility import evaluate_all
from src.domain.ontology.loader import get_ontology_graph
from src.domain.pipeline.screening_pipeline import (
    CandidateInput,
    run_screening_pipeline,
)
from src.domain.requirements.compiler import decompose_role_to_facets
from src.domain.requirements.schemas import (
    DurationPolicySchema,
    RequirementFacet,
    RequirementIR,
    RequirementSetIR,
)
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger


async def _eval_candidate_eligibility(
    cur: Any,
    cid_val: uuid.UUID,
    did_val: uuid.UUID,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    elig_snapshot: list[Any],
) -> None:
    """Evaluates candidate administrative eligibility and upserts to candidate_eligibility."""
    await cur.execute(
        """
        SELECT pgp_sym_decrypt(other_personal, %s) as decrypted_personal, other_personal
        FROM candidate_identities
        WHERE candidate_id = %s AND tenant_id = %s
        """,
        (settings.PII_ENCRYPTION_KEY, cid_val, tenant_id),
    )
    id_row = await cur.fetchone()
    parsed_other_p = {}
    if id_row:
        dec = id_row.get("decrypted_personal")
        if dec:
            with contextlib.suppress(Exception):
                parsed_other_p = json.loads(dec)
        elif id_row.get("other_personal"):
            with contextlib.suppress(Exception):
                raw_bytes = id_row["other_personal"]
                if isinstance(raw_bytes, (bytes, memoryview)):
                    parsed_other_p = json.loads(bytes(raw_bytes).decode("utf-8"))
                elif isinstance(raw_bytes, str):
                    parsed_other_p = json.loads(raw_bytes)

    elig_eval = evaluate_all(elig_snapshot, parsed_other_p)
    await cur.execute(
        """
        INSERT INTO candidate_eligibility (
            run_id, candidate_id, tenant_id, document_id, overall_status, details
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (run_id, candidate_id) DO UPDATE SET
            overall_status = EXCLUDED.overall_status, details = EXCLUDED.details, evaluated_at = now()
        """,
        (
            run_id,
            cid_val,
            tenant_id,
            did_val,
            elig_eval["overall_status"],
            json.dumps(elig_eval["details"]),
        ),
    )


async def execute_screening_run(run_id: uuid.UUID) -> dict[str, Any]:
    """Executes an immutable screening run asynchronously using Graph B over all ready CVs for the job."""
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, tenant_id, job_id, requirement_set_id, status, as_of, params, eligibility_snapshot
            FROM screening_runs
            WHERE id = %s
            FOR UPDATE
            """,
            (run_id,),
        )
        run_row = await cur.fetchone()
        if not run_row:
            raise ValueError(f"Screening run {run_id} not found.")

        # Immutability check
        if run_row["status"] in ("COMPLETED", "DONE"):
            logger.info(f"Screening run {run_id} is already completed. Skipping rerun.")
            return {"status": run_row["status"], "run_id": str(run_id)}

        tenant_id = run_row["tenant_id"]
        job_id = run_row["job_id"]
        req_set_id = run_row["requirement_set_id"]
        elig_snapshot = run_row["eligibility_snapshot"] or []

        # Mark RUNNING
        await cur.execute(
            "UPDATE screening_runs SET status = 'RUNNING', started_at = COALESCE(started_at, now()) WHERE id = %s",
            (run_id,),
        )
        await conn.commit()

        # 1. Fetch Job and Requirement Set
        await cur.execute("SELECT title FROM jobs WHERE id = %s AND tenant_id = %s", (job_id, tenant_id))
        job_row = await cur.fetchone()
        job_title = job_row["title"] if job_row else ""

        await cur.execute(
            "SELECT category_weights FROM requirement_sets WHERE id = %s AND tenant_id = %s",
            (req_set_id, tenant_id),
        )
        set_row = await cur.fetchone()
        cat_weights = set_row["category_weights"] if set_row else {}

        await cur.execute(
            """
            SELECT id, requirement_id, description, category, kind, importance, weight,
                   concepts, params, source_text, lint_flags, target_domains, duration_policy,
                   accepted_evidence, depth_floor
            FROM requirements
            WHERE requirement_set_id = %s AND tenant_id = %s
            ORDER BY requirement_id
            """,
            (req_set_id, tenant_id),
        )
        req_rows = await cur.fetchall()

        ontology = get_ontology_graph()

        requirements_ir_list: list[RequirementIR] = []
        for r in req_rows:
            req_uuid = r["id"]
            await cur.execute(
                """
                SELECT facet_key, hypothesis, core, concepts
                FROM requirement_facets
                WHERE requirement_uuid = %s
                ORDER BY facet_key
                """,
                (req_uuid,),
            )
            facet_rows = await cur.fetchall()

            facets: list[RequirementFacet] = []
            if facet_rows:
                for fr in facet_rows:
                    facets.append(
                        RequirementFacet(
                            facet_key=fr["facet_key"],
                            hypothesis=fr["hypothesis"],
                            core=fr["core"],
                            concepts=list(fr["concepts"] or []),
                        )
                    )
            else:
                facets = decompose_role_to_facets(
                    role_or_title=r["description"] or r["requirement_id"],
                    ontology=ontology,
                )
                for f in facets:
                    await cur.execute(
                        """
                        INSERT INTO requirement_facets (requirement_uuid, facet_key, hypothesis, core, concepts)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (requirement_uuid, facet_key) DO NOTHING
                        """,
                        (req_uuid, f.facet_key, f.hypothesis, f.core, list(f.concepts)),
                    )

            dur_policy = r.get("duration_policy") or {}
            dur_schema = (
                DurationPolicySchema.model_validate(dur_policy)
                if isinstance(dur_policy, dict) and dur_policy
                else DurationPolicySchema()
            )

            req_ir = RequirementIR(
                requirement_id=r["requirement_id"],
                description=r["description"] or "",
                category=r["category"] or "HARD_SKILLS",
                kind=r["kind"] or "SKILL",
                importance=r["importance"] or "MUST_HAVE",
                weight=float(r["weight"] or 10.0),
                concepts=list(r["concepts"] or []),
                target_domains=list(r["target_domains"] or []),
                duration_policy=dur_schema,
                accepted_evidence=list(r["accepted_evidence"] or []),
                depth_floor=r.get("depth_floor") or "L1",
                facets=facets,
            )
            requirements_ir_list.append(req_ir)

        req_set_ir = RequirementSetIR(
            requirement_set_id=req_set_id,
            job_title=job_title,
            requirements=requirements_ir_list,
            category_weights=cat_weights,
        )

        # 2. Fetch all documents and candidate profiles
        await cur.execute(
            """
            SELECT d.id as document_id, d.original_filename as file_name, d.sha256 as file_hash,
                   d.status as quality_status, d.flags, d.reasons, d.candidate_id,
                   cp.id as profile_id, cp.matching_profile, cp.full_text_redacted
            FROM documents d
            LEFT JOIN candidate_profiles cp ON cp.document_id = d.id AND cp.tenant_id = d.tenant_id
            WHERE d.job_id = %s AND d.tenant_id = %s
            """,
            (job_id, tenant_id),
        )
        cv_rows = await cur.fetchall()
        total_docs = len(cv_rows)

        # Update initial progress
        await cur.execute(
            "UPDATE screening_runs SET progress = %s WHERE id = %s",
            (json.dumps({"done": 0, "total": total_docs}), run_id),
        )
        await conn.commit()

        eval_cache: dict[str, dict[str, Any]] = {}
        candidate_inputs: list[CandidateInput] = []

        for cv in cv_rows:
            doc_id = cv["document_id"]
            cand_id = cv["candidate_id"] or doc_id
            file_name = cv["file_name"]
            matching_prof = cv["matching_profile"] or {}
            profile_id = cv["profile_id"]
            flags = list(cv["flags"] or [])
            reasons = list(cv["reasons"] or [])

            if cv["quality_status"] in ("REJECTED", "NEEDS_REVIEW", "DUPLICATE"):
                eval_cache[str(cand_id)] = {
                    "cv_id": cand_id,
                    "document_id": doc_id,
                    "file_name": file_name,
                    "status": cv["quality_status"],
                    "flags": flags,
                    "reasons": reasons,
                }
                continue

            # Load evidence atoms from DB
            atoms: list[EvidenceAtom] = []
            if profile_id:
                await cur.execute(
                    """
                    SELECT id, atom_key, kind, visibility, entry_ref, page,
                           char_start, char_end, red_start, red_end, bbox, text_redacted
                    FROM evidence_atoms
                    WHERE profile_id = %s AND tenant_id = %s
                    ORDER BY page, char_start
                    """,
                    (profile_id, tenant_id),
                )
                atom_rows = await cur.fetchall()
                for ar in atom_rows:
                    raw_bbox = ar["bbox"]
                    parsed_bbox: list[float] | None = None
                    if isinstance(raw_bbox, list):
                        parsed_bbox = [float(x) for x in raw_bbox]
                    elif isinstance(raw_bbox, str):
                        try:
                            l_val = json.loads(raw_bbox)
                            if isinstance(l_val, list):
                                parsed_bbox = [float(x) for x in l_val]
                        except Exception:
                            parsed_bbox = None

                    atoms.append(
                        EvidenceAtom(
                            id=ar["id"],
                            atom_key=ar["atom_key"],
                            kind=ar["kind"],
                            visibility=ar["visibility"],
                            entry_ref=ar["entry_ref"],
                            page=ar["page"],
                            char_start=ar["char_start"],
                            char_end=ar["char_end"],
                            red_start=ar["red_start"],
                            red_end=ar["red_end"],
                            bbox=parsed_bbox,
                            text_redacted=ar["text_redacted"],
                        )
                    )

            if not atoms and matching_prof:
                atoms = atomize_candidate_profile(profile=matching_prof)

            # Load experience entries and allocations from DB
            experiences: list[dict[str, Any]] = []
            if profile_id:
                await cur.execute(
                    """
                    SELECT ee.id, ee.entry_ref, ee.title_raw, ee.employment_type,
                           ee.date_text_start, ee.date_text_end, ee.start_lo, ee.start_hi, ee.end_lo, ee.end_hi,
                           ee.is_current, ee.date_flags,
                           COALESCE(
                               json_agg(
                                   json_build_object(
                                       'domain', eda.domain,
                                       'level', eda.level,
                                       'support_atom_ids', eda.support_atom_ids,
                                       'code_atom_ratio', eda.code_atom_ratio,
                                       'flags', eda.flags
                                   )
                               ) FILTER (WHERE eda.domain IS NOT NULL),
                               '[]'::json
                           ) as domain_allocations
                    FROM experience_entries ee
                    LEFT JOIN experience_domain_allocations eda ON eda.experience_id = ee.id
                    WHERE ee.profile_id = %s
                    GROUP BY ee.id
                    """,
                    (profile_id,),
                )
                exp_rows = await cur.fetchall()
                for er in exp_rows:
                    experiences.append(dict(er))

            if not experiences and matching_prof.get("experiences"):
                experiences = matching_prof["experiences"]

            # Load atom tags from DB
            atom_tags_dict: dict[str, Any] = {}
            if profile_id:
                await cur.execute(
                    """
                    SELECT at.atom_id, ea.atom_key, at.domains, at.activities, at.concepts,
                           at.evidence_type, at.impact_quantified, at.impact_kind
                    FROM atom_tags at
                    JOIN evidence_atoms ea ON ea.id = at.atom_id
                    WHERE ea.profile_id = %s
                    """,
                    (profile_id,),
                )
                tag_rows = await cur.fetchall()
                for tr in tag_rows:
                    t_data = dict(tr)
                    atom_tags_dict[str(tr["atom_id"])] = t_data
                    if tr["atom_key"]:
                        atom_tags_dict[tr["atom_key"]] = t_data

            raw_title = matching_prof.get("headline") or (
                experiences[0].get("title") or experiences[0].get("title_raw") if experiences else None
            )

            cand_input = CandidateInput(
                candidate_id=cand_id,
                atoms=atoms,
                profile_id=profile_id,
                raw_title=raw_title,
                experiences=experiences,
                atom_tags=atom_tags_dict,
                flags=flags,
            )
            candidate_inputs.append(cand_input)
            eval_cache[str(cand_id)] = {
                "cv_id": cand_id,
                "document_id": doc_id,
                "file_name": file_name,
                "status": "READY",
                "flags": flags,
                "reasons": reasons,
            }

        # 3. Run Screening Pipeline (Graph B)
        screening_res = await run_screening_pipeline(
            candidates=candidate_inputs,
            requirement_set=req_set_ir,
            run_id=run_id,
            tenant_id=tenant_id,
            save_to_db=True,
            conn=conn,
        )

        # Helper to ensure candidate record exists in candidates table
        async def _ensure_candidate(cid: uuid.UUID, did: uuid.UUID) -> None:
            await cur.execute("SELECT id FROM candidates WHERE id = %s AND tenant_id = %s", (cid, tenant_id))
            if not await cur.fetchone():
                await cur.execute("SELECT nextval('candidate_code_seq') as seq")
                seq_row = await cur.fetchone()
                seq_val = seq_row["seq"] if seq_row and seq_row["seq"] else 1
                cand_code = f"C-{seq_val:04d}"
                await cur.execute(
                    """
                    INSERT INTO candidates (id, tenant_id, candidate_code, status)
                    VALUES (%s, %s, %s, 'ACTIVE')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (cid, tenant_id, cand_code),
                )
                await cur.execute(
                    "UPDATE documents SET candidate_id = %s WHERE id = %s AND tenant_id = %s AND candidate_id IS NULL",
                    (cid, did, tenant_id),
                )

        # 4. Save evaluated candidate scores, requirement scores, evidence, eligibility
        for c_res in screening_res.candidates:
            cid_val = uuid.UUID(str(c_res.candidate_id))
            cached = eval_cache.get(str(cid_val), {})
            did_val = cached.get("document_id") or cid_val

            await _ensure_candidate(cid_val, did_val)

            cov = c_res.score_result.coverage if c_res.score_result else 1.0
            cand_flags = list(set(cached.get("flags", []) + c_res.flags))

            await cur.execute(
                """
                INSERT INTO candidate_scores (
                    run_id, candidate_id, tenant_id, document_id, rank, band,
                    raw_score, final_score, capped, recommendation, category_scores, flags, coverage
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s, %s, %s)
                ON CONFLICT (run_id, candidate_id) DO UPDATE SET
                    rank = EXCLUDED.rank, final_score = EXCLUDED.final_score, coverage = EXCLUDED.coverage,
                    band = EXCLUDED.band, raw_score = EXCLUDED.raw_score, recommendation = EXCLUDED.recommendation,
                    category_scores = EXCLUDED.category_scores, flags = EXCLUDED.flags
                """,
                (
                    run_id,
                    cid_val,
                    tenant_id,
                    did_val,
                    c_res.rank,
                    c_res.band,
                    c_res.raw_score,
                    c_res.final_score,
                    c_res.recommendation,
                    json.dumps(c_res.category_scores),
                    cand_flags,
                    cov,
                ),
            )

            for req_id, r_res in c_res.requirement_results.items():
                st_val = getattr(r_res, "state", None)
                st_str = str(getattr(st_val, "value", st_val or "NOT_DEMONSTRATED"))
                conf_val = getattr(r_res, "confidence", 1.0)
                await cur.execute(
                    """
                    INSERT INTO requirement_scores (
                        run_id, candidate_id, tenant_id, requirement_id, state, confidence, method, metrics
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'rule', %s)
                    ON CONFLICT (run_id, candidate_id, requirement_id) DO UPDATE SET
                        state = EXCLUDED.state, confidence = EXCLUDED.confidence
                    """,
                    (
                        run_id,
                        cid_val,
                        tenant_id,
                        str(req_id),
                        st_str,
                        conf_val,
                        json.dumps({}),
                    ),
                )

            for ga in c_res.grounding_atoms:
                ak = ga.get("atom_key") or str(ga.get("id"))
                txt = ga.get("text_redacted") or ""
                await cur.execute(
                    """
                    INSERT INTO evidence (
                        id, run_id, candidate_id, requirement_id, tenant_id, quote, context, verified
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                    """,
                    (
                        uuid.uuid4(),
                        run_id,
                        cid_val,
                        "facet_evidence",
                        tenant_id,
                        txt[:500],
                        f"Atom: {ak}",
                    ),
                )

            await _eval_candidate_eligibility(cur, cid_val, did_val, tenant_id, run_id, elig_snapshot)

        # 5. Handle disqualified / rejected candidates
        for _str_cid, c_data in eval_cache.items():
            if c_data.get("status") in ("REJECTED", "NEEDS_REVIEW", "DUPLICATE"):
                cid_val = c_data["cv_id"]
                did_val = c_data["document_id"]
                await _ensure_candidate(cid_val, did_val)

                rec = (
                    "REJECTED_NOT_A_CV"
                    if "NOT_A_CV" in c_data.get("flags", [])
                    or any("NOT_A_CV" in str(r) for r in c_data.get("reasons", []))
                    else "MANUAL_CHECK"
                )
                await cur.execute(
                    """
                    INSERT INTO candidate_scores (
                        run_id, candidate_id, tenant_id, document_id, rank, band,
                        raw_score, final_score, capped, recommendation, category_scores, flags, coverage
                    )
                    VALUES (%s, %s, %s, %s, 999, 'R', 0.0, 0.0, false, %s, '{}'::jsonb, %s, 1.0)
                    ON CONFLICT (run_id, candidate_id) DO UPDATE SET
                        rank = EXCLUDED.rank, final_score = EXCLUDED.final_score, recommendation = EXCLUDED.recommendation
                    """,
                    (run_id, cid_val, tenant_id, did_val, rec, c_data.get("flags", [])),
                )
                await _eval_candidate_eligibility(cur, cid_val, did_val, tenant_id, run_id, elig_snapshot)

        # 6. Mark screening run COMPLETED
        await cur.execute(
            """
            UPDATE screening_runs
            SET status = 'COMPLETED', progress = %s, finished_at = now()
            WHERE id = %s
            """,
            (json.dumps({"done": total_docs, "total": total_docs}), run_id),
        )
        await conn.commit()
        logger.info(f"Screening run {run_id} completed successfully ({total_docs} candidates evaluated).")
        return {"status": "COMPLETED", "run_id": str(run_id), "total_candidates": total_docs}
