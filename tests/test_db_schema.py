"""Tests verifying PostgreSQL schema, relations, pgvector extension, and indices."""

from __future__ import annotations

import pytest

from src.infrastructure.database import get_connection


@pytest.mark.asyncio
async def test_all_19_tables_exist():
    expected_tables = {
        "users",
        "jobs",
        "requirement_sets",
        "requirements",
        "candidates",
        "candidate_identities",
        "candidate_profiles",
        "skill_mentions",
        "profile_chunks",
        "documents",
        "jobs_queue",
        "screening_runs",
        "requirement_scores",
        "evidence",
        "candidate_scores",
        "reviews",
        "audit_logs",
        "model_calls",
        "llm_cache",
    }
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """
        )
        rows = await cur.fetchall()
        existing = {r["table_name"] for r in rows}
        missing = expected_tables - existing
        assert not missing, f"Missing tables in public schema: {missing}"


@pytest.mark.asyncio
async def test_pgvector_extension_version():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        row = await cur.fetchone()
        assert row is not None, "pgvector extension is not installed in database"
        version_str = row["extversion"]
        # Check version is at least 0.8.2
        parts = [int(p) for p in version_str.split(".")[:3]]
        assert parts >= [0, 8, 2], f"pgvector version {version_str} is below required 0.8.2"


@pytest.mark.asyncio
async def test_hnsw_vector_index():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'profile_chunks' AND indexdef LIKE '%hnsw%'
                """
        )
        row = await cur.fetchone()
        assert row is not None, "Missing HNSW index on profile_chunks"
        assert "vector_cosine_ops" in row["indexdef"]
