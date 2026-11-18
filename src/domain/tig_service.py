"""Queue execution for TIG assessments."""

from __future__ import annotations

from uuid import UUID

from psycopg.types.json import Jsonb

from src.domain.tig import Application, TigConfig, assess_application
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection


async def assess_queued_application(application_id: UUID, queue_id: int) -> None:
    # Read the snapshot and release the DB connection before contacting the model.
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT pgp_sym_decrypt(a.form, %s) AS form, a.assessment_config, a.assessment,
                   j.tenant_id, j.title
            FROM tig_applications a
            JOIN jobs j ON j.id = a.job_id
            WHERE a.id = %s AND a.queue_id = %s
            """,
            (settings.PII_ENCRYPTION_KEY, application_id, queue_id),
        )
        row = await cur.fetchone()
    if not row or row["assessment"] is not None:
        return

    result = await assess_application(
        Application.model_validate_json(row["form"]),
        row["title"],
        TigConfig.model_validate(row["assessment_config"]),
        row["tenant_id"],
    )
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE tig_applications SET assessment = %s, assessed_at = now()
            WHERE id = %s AND queue_id = %s AND assessment IS NULL
            """,
            (Jsonb(result), application_id, queue_id),
        )
