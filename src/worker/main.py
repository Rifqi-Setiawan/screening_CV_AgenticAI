"""Queue worker for scoring submitted TIG applications."""

from __future__ import annotations

import asyncio
import signal
from uuid import UUID

from src.domain.tig_service import assess_queued_application
from src.infrastructure.database import close_db_pool, get_connection
from src.infrastructure.logging import logger

_running = True


def handle_stop(sig, frame):
    global _running
    _running = False


async def worker_loop():
    logger.info("TIG assessment worker ready.")
    try:
        while _running:
            try:
                if not await handle_task():
                    await asyncio.sleep(0.5)
            except Exception as error:
                logger.error("TIG worker poll failed: %s", type(error).__name__)
                await asyncio.sleep(1)
    finally:
        await close_db_pool()


async def handle_task() -> bool:
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            WITH expired AS (
                UPDATE jobs_queue
                SET status = 'FAILED', error = 'TIG assessment worker lease expired'
                WHERE type = 'tig_assessment' AND status = 'RUNNING'
                  AND locked_at < now() - interval '10 minutes' AND attempts >= max_attempts
            )
            UPDATE jobs_queue
            SET status = 'RUNNING', locked_at = now(), attempts = attempts + 1
            WHERE id = (
                SELECT id FROM jobs_queue
                WHERE type = 'tig_assessment' AND attempts < max_attempts AND (
                    (status = 'PENDING' AND run_after <= now())
                    OR (status = 'RUNNING' AND locked_at < now() - interval '10 minutes')
                )
                ORDER BY id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, payload, attempts, max_attempts
            """
        )
        task = await cur.fetchone()

    if not task:
        return False
    task_id = task["id"]
    attempts = task["attempts"]

    try:
        await assess_queued_application(UUID(task["payload"]["application_id"]), task_id)
    except Exception as error:
        # An error may contain form details; save only its class.
        reason = type(error).__name__
        retry = attempts < task["max_attempts"]
        async with get_connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE jobs_queue
                SET status = %s, error = %s, run_after = now() + (%s * interval '1 minute')
                WHERE id = %s AND status = 'RUNNING' AND attempts = %s
                """,
                ("PENDING" if retry else "FAILED", reason, attempts, task_id, attempts),
            )
        logger.warning("TIG assessment task %s failed: %s", task_id, reason)
    else:
        async with get_connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "UPDATE jobs_queue SET status = 'DONE', error = NULL "
                "WHERE id = %s AND status = 'RUNNING' AND attempts = %s",
                (task_id, attempts),
            )
    return True


def main():
    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
