"""Tests verifying database persistence and constraints for evidence_atoms and redaction_offset_maps."""

from __future__ import annotations

import json
import uuid

import psycopg
import pytest

from src.infrastructure.database import get_connection


@pytest.mark.asyncio
async def test_evidence_atoms_and_offset_maps_tables_exist():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name IN ('evidence_atoms', 'redaction_offset_maps')
            """
        )
        rows = await cur.fetchall()
        found = {r["table_name"] for r in rows}
        assert "evidence_atoms" in found
        assert "redaction_offset_maps" in found


@pytest.mark.asyncio
async def test_evidence_atoms_indexes_exist():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'evidence_atoms'
            """
        )
        rows = await cur.fetchall()
        index_defs = {r["indexname"]: r["indexdef"] for r in rows}

        assert "idx_evidence_atoms_embedding" in index_defs
        assert "hnsw" in index_defs["idx_evidence_atoms_embedding"].lower()
        assert "vector_cosine_ops" in index_defs["idx_evidence_atoms_embedding"]

        assert "idx_evidence_atoms_fts" in index_defs
        assert "gin" in index_defs["idx_evidence_atoms_fts"].lower()


@pytest.mark.asyncio
async def test_evidence_atoms_crud_and_constraints():
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    profile_id = uuid.uuid4()

    async with get_connection() as conn, conn.cursor() as cur:
        # Create prerequisite job, candidate, document, and profile
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text)
            VALUES (%s, %s, 'Software Engineer', 'Job Description text')
            """,
            (job_id, tenant_id),
        )
        await cur.execute(
            """
            INSERT INTO candidates (id, tenant_id, candidate_code)
            VALUES (%s, %s, 'CAND-TEST-001')
            """,
            (candidate_id, tenant_id),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, candidate_id, original_filename, sha256, storage_key, status)
            VALUES (%s, %s, %s, %s, 'cv.pdf', 'hash123', 'cv.pdf', 'READY')
            """,
            (doc_id, tenant_id, job_id, candidate_id),
        )
        await cur.execute(
            """
            INSERT INTO candidate_profiles (id, tenant_id, document_id, profile, matching_profile, extractor_version)
            VALUES (%s, %s, %s, '{}'::jsonb, '{}'::jsonb, 'v2.1')
            """,
            (profile_id, tenant_id, doc_id),
        )

        # 1. Insert into redaction_offset_maps
        segments = [
            {"orig_start": 0, "orig_end": 10, "red_start": 0, "red_end": 10, "is_pii": False},
            {"orig_start": 10, "orig_end": 20, "red_start": 10, "red_end": 16, "is_pii": True, "replacement": "[NAMA]"},
        ]
        await cur.execute(
            """
            INSERT INTO redaction_offset_maps (document_id, tenant_id, segments)
            VALUES (%s, %s, %s)
            """,
            (doc_id, tenant_id, json.dumps(segments)),
        )

        # 2. Insert into evidence_atoms
        await cur.execute(
            """
            INSERT INTO evidence_atoms (
                tenant_id, profile_id, atom_key, kind, visibility, entry_ref,
                page, char_start, char_end, red_start, red_end, text_redacted
            ) VALUES (
                %s, %s, 'E1.B1', 'exp_bullet', 'VISIBLE', 'exp_1',
                1, 50, 100, 46, 96, 'Built scalable microservices in Python'
            )
            """,
            (tenant_id, profile_id),
        )

        # Verify FTS column was generated automatically
        await cur.execute(
            "SELECT atom_key, text_redacted, fts FROM evidence_atoms WHERE profile_id = %s",
            (profile_id,),
        )
        row = await cur.fetchone()
        assert row is not None
        assert row["atom_key"] == "E1.B1"
        assert row["fts"] is not None

        # Verify UNIQUE(profile_id, atom_key)
        with pytest.raises(psycopg.errors.UniqueViolation):
            await cur.execute(
                """
                INSERT INTO evidence_atoms (
                    tenant_id, profile_id, atom_key, kind, visibility, text_redacted
                ) VALUES (%s, %s, 'E1.B1', 'exp_bullet', 'VISIBLE', 'Duplicate')
                """,
                (tenant_id, profile_id),
            )
        await conn.rollback()

        # Clean up
        await cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
        await cur.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
        await conn.commit()
