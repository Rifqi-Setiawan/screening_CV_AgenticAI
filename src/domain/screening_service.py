"""Screening execution service handling asynchronous scoring, eligibility evaluation, and ranking (FX-30)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from datetime import date
from typing import Any

from src.domain.eligibility import evaluate_all
from src.domain.kind_rules import (
    eval_achievement,
    eval_certification,
    eval_education,
    eval_experience_duration,
    eval_leadership,
    eval_responsibility,
    eval_skill,
)
from src.domain.scorer import rank, score
from src.domain.verifier import verify_requirement_with_llm
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger


async def execute_screening_run(run_id: uuid.UUID) -> dict[str, Any]:
    """Executes an immutable screening run asynchronously over all ready CVs for the job."""
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
        effective_as_of = str(run_row["as_of"]) if run_row["as_of"] else date.today().isoformat()
        params = run_row["params"] or {}
        use_verifier = params.get("use_verifier", False)
        elig_snapshot = run_row["eligibility_snapshot"] or []

        # Mark RUNNING
        await cur.execute(
            "UPDATE screening_runs SET status = 'RUNNING', started_at = COALESCE(started_at, now()) WHERE id = %s",
            (run_id,),
        )
        await conn.commit()

        # Fetch requirement set
        await cur.execute(
            "SELECT category_weights FROM requirement_sets WHERE id = %s AND tenant_id = %s",
            (req_set_id, tenant_id),
        )
        set_row = await cur.fetchone()
        cat_weights = set_row["category_weights"] if set_row else {}

        await cur.execute(
            """
            SELECT requirement_id, description, category, kind, importance, weight, concepts, params, source_text, lint_flags
            FROM requirements
            WHERE requirement_set_id = %s AND tenant_id = %s
            ORDER BY requirement_id
            """,
            (req_set_id, tenant_id),
        )
        requirements = [dict(r) for r in await cur.fetchall()]
        req_set_dict = {
            "category_weights": cat_weights,
            "requirements": requirements,
        }

        # Fetch all documents and candidate profiles
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

        scoring_items: list[dict[str, Any]] = []
        eval_cache: dict[str, dict[str, Any]] = {}

        verifier_semaphore = asyncio.Semaphore(settings.VERIFIER_CONCURRENCY)

        for idx, cv in enumerate(cv_rows, 1):
            doc_id = cv["document_id"]
            cand_id = cv["candidate_id"] or doc_id
            file_name = cv["file_name"]
            matching_prof = cv["matching_profile"] or {}
            full_text = cv.get("full_text_redacted") or ""
            flags = list(cv["flags"] or [])
            reasons = list(cv["reasons"] or [])

            if cv["quality_status"] in ("REJECTED", "NEEDS_REVIEW", "DUPLICATE"):
                eval_cache[str(cand_id)] = {
                    "cv_id": cand_id,
                    "document_id": doc_id,
                    "file_name": file_name,
                    "status": cv["quality_status"],
                    "states": {},
                    "metrics": {},
                    "evidence": {},
                    "flags": flags,
                    "reasons": reasons,
                    "score_res": None,
                }
                continue

            states_map: dict[str, str] = {}
            metrics_map: dict[str, Any] = {}
            ev_map: dict[str, list[dict[str, Any]]] = {}

            for r in req_set_dict["requirements"]:
                rid = r["requirement_id"]
                kind = r["kind"]
                if kind == "EXPERIENCE_DURATION":
                    st, conf, m, evs, flgs = eval_experience_duration(matching_prof, r, as_of=effective_as_of)
                    metrics_map.update(m)
                elif kind == "SKILL":
                    st, conf, m, evs, flgs = eval_skill(matching_prof, r)
                elif kind == "RESPONSIBILITY":
                    st, conf, m, evs, flgs = eval_responsibility(matching_prof, r)
                elif kind == "EDUCATION":
                    st, conf, m, evs, flgs = eval_education(matching_prof, r)
                elif kind == "CERTIFICATION":
                    st, conf, m, evs, flgs = eval_certification(matching_prof, r)
                elif kind == "ACHIEVEMENT":
                    st, conf, m, evs, flgs = eval_achievement(matching_prof, r)
                elif kind == "LEADERSHIP":
                    st, _conf, m, evs, flgs = eval_leadership(matching_prof, r)
                else:
                    st, _conf, m, evs, flgs = "NOT_DEMONSTRATED", 0.9, {}, [], []

                # Hybrid semantic retrieval fallback (FX-32)
                if (
                    settings.SCORING_MODE == "hybrid"
                    and kind in ("SKILL", "RESPONSIBILITY", "ACHIEVEMENT", "LEADERSHIP")
                    and st == "NOT_DEMONSTRATED"
                    and cv.get("profile_id")
                ):
                    from src.domain.retrieval import retrieve_evidence, split_sentences

                    top_chunks, sim = await retrieve_evidence(
                        profile_id=cv["profile_id"],
                        requirement=r,
                        tenant_id=tenant_id,
                    )
                    if sim >= settings.SEMANTIC_THRESHOLD and top_chunks:
                        st = "PARTIAL"
                        flgs = list(flgs) + ["SEMANTIC_MATCH"]
                        sentences = split_sentences(top_chunks[0]["text"])
                        sample_sentence = sentences[0] if sentences else top_chunks[0]["text"][:120]
                        evs = [{"quote": sample_sentence, "context": top_chunks[0]["kind"], "verified": True}]

                flags.extend(flgs)

                # Optional LLM verifier bounded with semaphore
                if use_verifier and st in ("PARTIAL", "STRONG") and evs:
                    async with verifier_semaphore:
                        v_st, v_quote, v_flgs = await verify_requirement_with_llm(
                            full_text, r, st, [e.get("quote", "") for e in evs]
                        )
                        st = v_st
                        flags.extend(v_flgs)

                states_map[rid] = st
                ev_map[rid] = evs

            score_res = score(states_map, req_set_dict)
            strong_count = sum(1 for v in states_map.values() if v == "STRONG")

            scoring_items.append(
                {
                    "candidate_id": str(cand_id),
                    "cv_id": cand_id,
                    "document_id": doc_id,
                    "file_name": file_name,
                    "result": score_res,
                    "strong_count": strong_count,
                }
            )
            eval_cache[str(cand_id)] = {
                "cv_id": cand_id,
                "document_id": doc_id,
                "file_name": file_name,
                "status": "SCORED",
                "states": states_map,
                "metrics": metrics_map,
                "evidence": ev_map,
                "flags": flags,
                "reasons": reasons,
                "score_res": score_res,
            }

            # Periodic progress update every 10 CVs
            if idx % 10 == 0 or idx == total_docs:
                await cur.execute(
                    "UPDATE screening_runs SET progress = %s WHERE id = %s",
                    (json.dumps({"done": idx, "total": total_docs}), run_id),
                )
                await conn.commit()

        # Deterministic tie-broken ranking
        ranked_items = rank(scoring_items, run_id=str(run_id))
        rank_lookup = {str(item["cv_id"]): r_idx + 1 for r_idx, item in enumerate(ranked_items)}

        # Persist candidate scores, requirement scores, evidence, and eligibility
        for str_cid, c_data in eval_cache.items():
            cv_id_val = c_data["cv_id"]
            doc_id_val = c_data["document_id"]
            cand_rank = rank_lookup.get(str_cid, 999)
            s_res = c_data["score_res"]

            # Ensure candidate record exists in `candidates` table
            await cur.execute("SELECT id FROM candidates WHERE id = %s AND tenant_id = %s", (cv_id_val, tenant_id))
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
                    (cv_id_val, tenant_id, cand_code),
                )
                await cur.execute(
                    "UPDATE documents SET candidate_id = %s WHERE id = %s AND tenant_id = %s AND candidate_id IS NULL",
                    (cv_id_val, doc_id_val, tenant_id),
                )

            raw_sc = s_res.raw_score if s_res else 0.0
            fin_sc = s_res.final_score if s_res else 0.0
            bnd = s_res.band if s_res else "R"
            rec = s_res.recommendation if s_res else "MANUAL_CHECK"
            if "NOT_A_CV" in c_data.get("flags", []) or any("NOT_A_CV" in str(r) for r in c_data.get("reasons", [])):
                rec = "REJECTED_NOT_A_CV"
            cat_b = s_res.category_breakdown if s_res else {}
            cov = s_res.coverage if s_res else 1.0
            cand_flags = list(set(c_data["flags"] + (s_res.flags if s_res else [])))

            await cur.execute(
                """
                INSERT INTO candidate_scores (
                    run_id, candidate_id, tenant_id, document_id, rank, band,
                    raw_score, final_score, capped, recommendation, category_scores, flags, coverage
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, false, %s, %s, %s, %s)
                ON CONFLICT (run_id, candidate_id) DO UPDATE SET
                    rank = EXCLUDED.rank, final_score = EXCLUDED.final_score, coverage = EXCLUDED.coverage
                """,
                (
                    run_id,
                    cv_id_val,
                    tenant_id,
                    doc_id_val,
                    cand_rank,
                    bnd,
                    raw_sc,
                    fin_sc,
                    rec,
                    json.dumps(cat_b),
                    cand_flags,
                    cov,
                ),
            )

            # Batch insert requirement scores & evidence via executemany
            req_params = [
                (
                    run_id,
                    cv_id_val,
                    req_obj["requirement_id"],
                    tenant_id,
                    c_data["states"].get(req_obj["requirement_id"], "NOT_DEMONSTRATED"),
                )
                for req_obj in req_set_dict["requirements"]
            ]
            if req_params:
                await cur.executemany(
                    """
                    INSERT INTO requirement_scores (
                        run_id, candidate_id, requirement_id, tenant_id, state, confidence, method, metrics
                    )
                    VALUES (%s, %s, %s, %s, %s, 0.95, 'rule', '{}'::jsonb)
                    ON CONFLICT (run_id, candidate_id, requirement_id) DO NOTHING
                    """,
                    req_params,
                )

            ev_params = []
            for req_obj in req_set_dict["requirements"]:
                req_id_str = req_obj["requirement_id"]
                for ev_item in c_data["evidence"].get(req_id_str, []):
                    ev_params.append(
                        (
                            uuid.uuid4(),
                            run_id,
                            cv_id_val,
                            req_id_str,
                            tenant_id,
                            ev_item.get("quote", ""),
                            ev_item.get("context", "experience"),
                            ev_item.get("verified", True),
                        )
                    )
            if ev_params:
                await cur.executemany(
                    """
                    INSERT INTO evidence (
                        id, run_id, candidate_id, requirement_id, tenant_id, quote, context, verified
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    ev_params,
                )

            # Evaluate candidate administrative eligibility
            await cur.execute(
                """
                SELECT pgp_sym_decrypt(other_personal, %s) as decrypted_personal, other_personal
                FROM candidate_identities
                WHERE candidate_id = %s AND tenant_id = %s
                """,
                (settings.PII_ENCRYPTION_KEY, cv_id_val, tenant_id),
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
                    cv_id_val,
                    tenant_id,
                    doc_id_val,
                    elig_eval["overall_status"],
                    json.dumps(elig_eval["details"]),
                ),
            )

        # Mark screening run COMPLETED
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
