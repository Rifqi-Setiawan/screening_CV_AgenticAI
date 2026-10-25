import pytest

from src.infrastructure.database import get_connection


@pytest.mark.asyncio
async def test_worker_stale_running_job_recovered():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jobs_queue WHERE type LIKE 'test_%'")
        # Insert a job that got stuck in RUNNING 15 minutes ago with attempts = 1
        await cur.execute(
            """
            INSERT INTO jobs_queue (type, payload, status, attempts, max_attempts, locked_at)
            VALUES ('test_stale', '{"test": 1}'::jsonb, 'RUNNING', 1, 3, now() - interval '15 minutes')
            RETURNING id
            """
        )
        job_id = (await cur.fetchone())["id"]
        await conn.commit()

        # Execute the claim query used by the worker targeting this job condition
        await cur.execute(
            """
            UPDATE jobs_queue
            SET status = 'RUNNING', locked_at = now(), attempts = attempts + 1
            WHERE id = (
                SELECT id FROM jobs_queue
                WHERE id = %s
                  AND ((status = 'PENDING' AND run_after <= now())
                   OR (status = 'RUNNING' AND locked_at < now() - interval '10 minutes' AND attempts < max_attempts))
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, status, attempts
            """,
            (job_id,),
        )
        claimed = await cur.fetchone()
        assert claimed is not None
        assert claimed["id"] == job_id
        assert claimed["status"] == "RUNNING"
        assert claimed["attempts"] == 2
        await conn.commit()


@pytest.mark.asyncio
async def test_worker_failed_job_retries_and_marks_failed():
    async with get_connection() as conn, conn.cursor() as cur:
        # Insert a job with attempts = 2, max_attempts = 3
        await cur.execute(
            """
            INSERT INTO jobs_queue (type, payload, status, attempts, max_attempts)
            VALUES ('test_retry', '{"test": 2}'::jsonb, 'PENDING', 2, 3)
            RETURNING id
            """
        )
        job_id = (await cur.fetchone())["id"]
        await conn.commit()

        # Claim job (attempt becomes 3)
        await cur.execute(
            """
            UPDATE jobs_queue
            SET status = 'RUNNING', locked_at = now(), attempts = attempts + 1
            WHERE id = %s
            RETURNING attempts, max_attempts
            """,
            (job_id,),
        )
        task = await cur.fetchone()
        attempts = task["attempts"]
        max_attempts = task["max_attempts"]

        assert attempts == 3
        assert max_attempts == 3

        # Simulate job failure logic
        err_msg = "Simulated failure"
        if attempts < max_attempts:
            await cur.execute(
                """
                UPDATE jobs_queue
                SET status = 'PENDING', error = %s, run_after = now() + (%s * interval '1 minute')
                WHERE id = %s
                """,
                (err_msg, attempts, job_id),
            )
        else:
            await cur.execute(
                """
                UPDATE jobs_queue
                SET status = 'FAILED', error = %s
                WHERE id = %s
                """,
                (err_msg, job_id),
            )
        await conn.commit()

        # Verify job is now FAILED
        await cur.execute("SELECT status, error FROM jobs_queue WHERE id = %s", (job_id,))
        res = await cur.fetchone()
        assert res["status"] == "FAILED"
        assert res["error"] == err_msg
