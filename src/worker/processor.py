"""Document ingestion, parsing, redaction, and embedding pipeline processor."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from src.domain.pii import EMAIL_REGEX, PHONE_REGEX
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger
from src.worker.adapter import extract_candidate_profile
from src.worker.embedding import embed_texts
from src.worker.redaction import extract_identity_and_redact, redact_text
from src.worker.sanitizer import sanitize_file


async def process_document(doc_id: uuid.UUID) -> dict[str, Any]:
    logger.info(f"Starting processing for document {doc_id}...")
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status
            FROM documents
            WHERE id = %s
            FOR UPDATE
            """,
            (doc_id,),
        )
        doc = await cur.fetchone()
        if not doc:
            logger.error(f"Document {doc_id} not found")
            return {"status": "NOT_FOUND"}

        if doc["status"] in ("READY", "REJECTED", "DUPLICATE"):
            logger.info(f"Document {doc_id} already in terminal state {doc['status']}, skipping.")
            return {"status": doc["status"]}

        vault_file = Path(settings.STORAGE_VAULT_PATH) / str(doc["tenant_id"]) / doc["storage_key"]
        if not vault_file.exists():
            logger.error(f"Vault file {vault_file} missing on disk")
            await cur.execute(
                "UPDATE documents SET status = 'REJECTED', reasons = ARRAY['File missing in storage'] WHERE id = %s",
                (doc_id,),
            )
            await conn.commit()
            return {"status": "REJECTED", "error": "file_missing"}

        content = vault_file.read_bytes()
        filename = doc["original_filename"]

        try:
            # 1. Sanitize file & inspect edge cases
            san = sanitize_file(content, filename)
            if not san.is_valid or san.status == "REJECTED":
                await cur.execute(
                    """
                    UPDATE documents
                    SET status = 'REJECTED', reasons = %s, flags = %s
                    WHERE id = %s
                    """,
                    (san.reasons, san.flags, doc_id),
                )
                await conn.commit()
                logger.info(f"Document {filename} REJECTED: {san.reasons}")
                return {"status": "REJECTED", "reasons": san.reasons}

            # 2. Check Deduplication against other documents in the same job
            await cur.execute(
                """
                SELECT id, original_filename
                FROM documents
                WHERE job_id = %s AND sha256 = %s AND id != %s AND status IN ('READY', 'RECEIVED', 'NEEDS_REVIEW')
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (doc["job_id"], doc["sha256"], doc_id),
            )
            dup_row = await cur.fetchone()
            if dup_row:
                await cur.execute(
                    """
                    UPDATE documents
                    SET status = 'DUPLICATE', duplicate_of = %s
                    WHERE id = %s
                    """,
                    (dup_row["id"], doc_id),
                )
                await conn.commit()
                logger.info(f"Document {filename} marked as DUPLICATE of {dup_row['original_filename']}")
                return {"status": "DUPLICATE", "duplicate_of": dup_row["original_filename"]}

            # If empty content or not a CV -> mark NEEDS_REVIEW
            if san.status == "NEEDS_REVIEW":
                await cur.execute(
                    """
                    UPDATE documents
                    SET status = 'NEEDS_REVIEW', reasons = %s, flags = %s
                    WHERE id = %s
                    """,
                    (san.reasons, san.flags, doc_id),
                )
                await conn.commit()
                logger.info(f"Document {filename} marked as NEEDS_REVIEW: {san.reasons}")
                return {"status": "NEEDS_REVIEW", "reasons": san.reasons}

            # 3. Extract Candidate Profile via production adapter in worker thread
            raw_profile = await asyncio.to_thread(extract_candidate_profile, content, filename)
            # 4. Separate Identity and Redact Matching Profile
            identity_rec, matching_profile, chunks = extract_identity_and_redact(raw_profile)

            # 5. Determine or Deduplicate Candidate Record
            candidate_id = doc.get("candidate_id")
            candidate_code = None

            email_val = (identity_rec.get("email") or "").strip().lower() or None
            phone_val = (identity_rec.get("phone") or "").strip() or None
            email_hash = hashlib.sha256(email_val.encode()).hexdigest() if email_val else None
            phone_hash = hashlib.sha256(phone_val.encode()).hexdigest() if phone_val else None

            if not candidate_id and (email_val or phone_val or email_hash or phone_hash):
                # Search if candidate identity already exists for this tenant
                clauses = []
                params: list[Any] = [doc["tenant_id"]]
                if email_val:
                    clauses.append("ci.email = %s")
                    params.append(email_val)
                if email_hash:
                    clauses.append("ci.email_hash = %s")
                    params.append(email_hash)
                if phone_val:
                    clauses.append("ci.phone = %s")
                    params.append(phone_val)
                if phone_hash:
                    clauses.append("ci.phone_hash = %s")
                    params.append(phone_hash)

                if clauses:
                    query = f"""
                        SELECT ci.candidate_id, c.candidate_code
                        FROM candidate_identities ci
                        JOIN candidates c ON c.id = ci.candidate_id AND c.tenant_id = ci.tenant_id
                        WHERE ci.tenant_id = %s AND ({" OR ".join(clauses)})
                        LIMIT 1
                    """
                    await cur.execute(query, tuple(params))
                    existing_cand = await cur.fetchone()
                    if existing_cand:
                        candidate_id = existing_cand["candidate_id"]
                        candidate_code = existing_cand["candidate_code"]

            if candidate_id and not candidate_code:
                await cur.execute(
                    "SELECT candidate_code FROM candidates WHERE id = %s AND tenant_id = %s",
                    (candidate_id, doc["tenant_id"]),
                )
                cand_row = await cur.fetchone()
                candidate_code = cand_row["candidate_code"] if cand_row else None

            if not candidate_id:
                candidate_id = uuid.uuid4()
                await cur.execute("SELECT nextval('candidate_code_seq') as seq")
                seq_row = await cur.fetchone()
                seq_val = seq_row["seq"] if seq_row and seq_row["seq"] else 1
                candidate_code = f"C-{seq_val:04d}"

                await cur.execute(
                    """
                    INSERT INTO candidates (id, tenant_id, candidate_code, status)
                    VALUES (%s, %s, %s, 'ACTIVE')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (candidate_id, doc["tenant_id"], candidate_code),
                )

            # Link document to candidate_id
            await cur.execute(
                "UPDATE documents SET candidate_id = %s WHERE id = %s AND tenant_id = %s",
                (candidate_id, doc_id, doc["tenant_id"]),
            )

            # 6. Save Identity (Encrypted other_personal via pgcrypto)
            other_p_json = json.dumps(identity_rec["other_personal"])
            await cur.execute(
                """
                INSERT INTO candidate_identities (
                    candidate_id, tenant_id, full_name, email, phone, email_hash, phone_hash, location_raw, other_personal
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, pgp_sym_encrypt(%s, %s))
                ON CONFLICT (candidate_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    email_hash = EXCLUDED.email_hash,
                    phone_hash = EXCLUDED.phone_hash,
                    location_raw = EXCLUDED.location_raw,
                    other_personal = EXCLUDED.other_personal
                """,
                (
                    candidate_id,
                    doc["tenant_id"],
                    identity_rec["full_name"],
                    email_val,
                    phone_val,
                    email_hash,
                    phone_hash,
                    identity_rec["location_raw"],
                    other_p_json,
                    settings.PII_ENCRYPTION_KEY,
                ),
            )

            # 7. Compute full_text_redacted and Save Candidate Profile (Upsert)
            full_text_redacted = redact_text(
                san.extracted_text,
                identity_rec["full_name"],
                [email_val] if email_val else [],
                [phone_val] if phone_val else [],
            )

            quality_flags = list(set(san.flags + raw_profile.get("quality", {}).get("warnings", [])))

            # Check text-level duplication across other documents in the same job
            norm_text = re.sub(r"\s+", " ", full_text_redacted.lower()).strip()
            if norm_text:
                await cur.execute(
                    """
                    SELECT d.id, d.original_filename
                    FROM documents d
                    JOIN candidate_profiles cp ON cp.document_id = d.id AND cp.tenant_id = d.tenant_id
                    WHERE d.job_id = %s AND d.tenant_id = %s AND d.id != %s
                      AND trim(regexp_replace(lower(cp.full_text_redacted), '[[:space:]]+', ' ', 'g')) = %s
                      AND d.status IN ('READY', 'RECEIVED', 'NEEDS_REVIEW')
                    LIMIT 1
                    """,
                    (doc["job_id"], doc["tenant_id"], doc_id, norm_text),
                )
                text_dup = await cur.fetchone()
                if text_dup:
                    await cur.execute(
                        """
                        UPDATE documents
                        SET status = 'DUPLICATE', duplicate_of = %s, reasons = ARRAY['Text content duplicate of ' || %s]
                        WHERE id = %s
                        """,
                        (text_dup["id"], text_dup["original_filename"], doc_id),
                    )
                    await conn.commit()
                    logger.info(
                        f"Document {filename} marked as DUPLICATE of {text_dup['original_filename']} by text fingerprint"
                    )
                    return {"status": "DUPLICATE", "duplicate_of": text_dup["original_filename"]}

            # Check if candidate already has another document in this job -> POSSIBLE_DUPLICATE_OF
            await cur.execute(
                """
                SELECT d.id, c.candidate_code
                FROM documents d
                JOIN candidates c ON c.id = d.candidate_id AND c.tenant_id = d.tenant_id
                WHERE d.job_id = %s AND d.tenant_id = %s AND d.id != %s
                  AND d.candidate_id = %s
                  AND d.status <> 'DUPLICATE'
                LIMIT 1
                """,
                (doc["job_id"], doc["tenant_id"], doc_id, candidate_id),
            )
            prior_cand_doc = await cur.fetchone()
            if prior_cand_doc and prior_cand_doc["candidate_code"]:
                quality_flags.append(f"POSSIBLE_DUPLICATE_OF:{prior_cand_doc['candidate_code']}")

            await cur.execute(
                """
                INSERT INTO candidate_profiles (
                    id, tenant_id, document_id, profile, matching_profile, full_text_redacted, extractor_version, quality
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id) DO UPDATE SET
                    profile = EXCLUDED.profile,
                    matching_profile = EXCLUDED.matching_profile,
                    full_text_redacted = EXCLUDED.full_text_redacted,
                    quality = EXCLUDED.quality
                RETURNING id
                """,
                (
                    uuid.uuid4(),
                    doc["tenant_id"],
                    doc_id,
                    json.dumps(raw_profile),
                    json.dumps(matching_profile),
                    full_text_redacted,
                    f"cv-extractor-{settings.EXTRACTOR_VERSION}",
                    json.dumps({"flags": quality_flags, "confidence": san.is_valid}),
                ),
            )
            prof_row = await cur.fetchone()
            profile_id = prof_row["id"]

            # 7b. Run Profiling Pipeline (Graph A) to generate and save evidence atoms, offset map, experiences, allocations, and tags
            pii_spans_list: list[tuple[int, int, str]] = []
            if san.extracted_text:
                for m in EMAIL_REGEX.finditer(san.extracted_text):
                    pii_spans_list.append((m.start(), m.end(), "[EMAIL]"))
                for m in PHONE_REGEX.finditer(san.extracted_text):
                    pii_spans_list.append((m.start(), m.end(), "[TELEPON]"))
                for target, repl in [
                    (email_val, "[EMAIL]"),
                    (phone_val, "[TELEPON]"),
                ]:
                    if target:
                        for m in re.finditer(re.escape(target), san.extracted_text, flags=re.IGNORECASE):
                            pii_spans_list.append((m.start(), m.end(), repl))
                if identity_rec.get("full_name"):
                    for m in re.finditer(re.escape(identity_rec["full_name"]), san.extracted_text, flags=re.IGNORECASE):
                        pii_spans_list.append((m.start(), m.end(), "[NAMA]"))

            pii_spans_list.sort(key=lambda s: (s[0], -(s[1] - s[0])))
            clean_pii_spans: list[tuple[int, int, str]] = []
            last_end = -1
            for s_start, s_end, s_repl in pii_spans_list:
                if s_start >= last_end:
                    clean_pii_spans.append((s_start, s_end, s_repl))
                    last_end = s_end

            from src.domain.pipeline.profiling_pipeline import run_profiling_pipeline

            raw_title = raw_profile.get("headline") or (
                matching_profile.get("experiences", [{}])[0].get("title")
                if matching_profile.get("experiences")
                else None
            )

            # Visibility gate input: the PDF itself (spans, colours, rendered ink). None for other formats.
            pdf_doc = None
            if filename.lower().endswith(".pdf"):
                try:
                    import fitz

                    pdf_doc = fitz.open(stream=content, filetype="pdf")
                except Exception:
                    pdf_doc = None
            try:
                profiling_result = await run_profiling_pipeline(
                    profile_id=profile_id,
                    raw_text=san.extracted_text,
                    pdf_spans=pdf_doc,
                    candidate_profile=matching_profile,
                    pii_spans=clean_pii_spans,
                    document_id=doc_id,
                    tenant_id=doc["tenant_id"],
                    raw_title=raw_title,
                    save_to_db=True,
                    conn=conn,
                )
            finally:
                if pdf_doc is not None:
                    pdf_doc.close()
            if profiling_result.flags:
                quality_flags = list(set(quality_flags + profiling_result.flags))

            # Clean existing chunks if re-processing
            await cur.execute("DELETE FROM profile_chunks WHERE profile_id = %s", (profile_id,))

            # 8. Generate & Insert Profile Chunks with Embeddings
            chunk_texts = [c["text_redacted"] for c in chunks]
            embeddings = await asyncio.to_thread(embed_texts, chunk_texts)

            chunk_params = [
                (
                    doc["tenant_id"],
                    profile_id,
                    c["kind"],
                    c["entry_ref"],
                    c["text_redacted"],
                    hashlib.sha256(c["text_redacted"].encode()).hexdigest(),
                    emb,
                    settings.EMBEDDING_MODEL,
                )
                for c, emb in zip(chunks, embeddings)
            ]

            if chunk_params:
                await cur.executemany(
                    """
                    INSERT INTO profile_chunks (
                        tenant_id, profile_id, kind, entry_ref, text_redacted, chunk_hash, embedding, embedding_model
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    chunk_params,
                )

            # 9. Link Candidate ID and Mark Document READY
            doc_status = "READY"
            await cur.execute(
                """
                UPDATE documents
                SET status = %s, candidate_id = %s, flags = %s, reasons = '{}'::text[]
                WHERE id = %s
                """,
                (doc_status, candidate_id, quality_flags, doc_id),
            )
            await conn.commit()
            logger.info(f"Successfully ingested and processed document {filename} (status: {doc_status})")
            return {"status": doc_status, "profile_id": str(profile_id), "candidate_code": candidate_code}
        except Exception as e:
            logger.exception(f"Processing failed for document {filename}: {e}")
            try:
                await conn.rollback()
                async with conn.cursor() as err_cur:
                    await err_cur.execute(
                        """
                        UPDATE documents
                        SET status = 'NEEDS_REVIEW', reasons = array_append(reasons, 'PROCESSING_ERROR: ' || %s)
                        WHERE id = %s
                        """,
                        (str(e)[:150], doc_id),
                    )
                    await conn.commit()
            except Exception as rollback_err:
                logger.error(f"Failed to record processing error for document {doc_id}: {rollback_err}")
            return {"status": "NEEDS_REVIEW", "reasons": [f"PROCESSING_ERROR: {str(e)[:150]}"]}
