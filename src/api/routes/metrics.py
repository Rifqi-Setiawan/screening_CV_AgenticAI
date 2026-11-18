"""Authenticated operational metrics for the TIG worker and model gateway."""

from __future__ import annotations

from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

router = APIRouter(tags=["Metrics"])
metrics_security = HTTPBearer(auto_error=False)


def verify_metrics_token(credentials: HTTPAuthorizationCredentials | None = Security(metrics_security)) -> None:
    if not credentials or not compare_digest(credentials.credentials, settings.METRICS_TOKEN):
        raise HTTPException(401, "Unauthorized metrics access", headers={"WWW-Authenticate": "Bearer"})


@router.get("/metrics", response_class=Response, dependencies=[Depends(verify_metrics_token)])
async def get_prometheus_metrics():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT count(*) AS count FROM tig_applications")
        applications = (await cur.fetchone())["count"]
        await cur.execute(
            "SELECT status, count(*) AS count FROM jobs_queue WHERE type = 'tig_assessment' GROUP BY status"
        )
        queue = {row["status"]: row["count"] for row in await cur.fetchall()}
        await cur.execute(
            """
            SELECT count(*) AS calls, COALESCE(sum(tokens_in), 0) AS tokens_in,
                   COALESCE(sum(tokens_out), 0) AS tokens_out
            FROM model_calls WHERE task = 'tig_assessment'
            """
        )
        llm = await cur.fetchone()

    lines = [
        "# TYPE tig_applications gauge",
        f"tig_applications {applications}",
        "# TYPE tig_assessment_jobs gauge",
        *(
            f'tig_assessment_jobs{{status="{status}"}} {queue.get(status, 0)}'
            for status in ("PENDING", "RUNNING", "DONE", "FAILED")
        ),
        "# TYPE tig_model_calls_total counter",
        f"tig_model_calls_total {llm['calls']}",
        "# TYPE tig_model_tokens_total counter",
        f'tig_model_tokens_total{{type="prompt"}} {llm["tokens_in"]}',
        f'tig_model_tokens_total{{type="completion"}} {llm["tokens_out"]}',
    ]
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4; charset=utf-8")
