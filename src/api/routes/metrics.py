"""Prometheus metrics endpoint (/metrics) for CV Screening Platform (M6)."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection

router = APIRouter(tags=["Metrics"])
metrics_security = HTTPBearer(auto_error=False)

_cached_metrics_text: str | None = None
_cached_metrics_time: float = 0.0


def clear_metrics_cache() -> None:
    """Helper for testing to invalidate cached Prometheus metrics."""
    global _cached_metrics_text, _cached_metrics_time
    _cached_metrics_text = None
    _cached_metrics_time = 0.0


def verify_metrics_token(credentials: HTTPAuthorizationCredentials | None = Security(metrics_security)) -> None:
    if not credentials or credentials.credentials != settings.METRICS_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized metrics access",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/metrics", response_class=Response, dependencies=[Depends(verify_metrics_token)])
async def get_prometheus_metrics():
    """Returns real Prometheus-formatted operational and business metrics."""
    global _cached_metrics_text, _cached_metrics_time
    now = time.monotonic()
    if _cached_metrics_text is not None and (now - _cached_metrics_time) < 20.0:
        return Response(content=_cached_metrics_text, media_type="text/plain; version=0.0.4; charset=utf-8")

    async with get_connection() as conn, conn.cursor() as cur:
        # 1. Total processed CVs (status = READY)
        await cur.execute("SELECT count(*) as cnt FROM documents WHERE status = 'READY'")
        row = await cur.fetchone()
        cv_processed_ready = row["cnt"] if row else 0

        # 2. Total documents by status
        await cur.execute("SELECT status, count(*) as cnt FROM documents GROUP BY status")
        cv_status_counts = {r["status"]: r["cnt"] for r in await cur.fetchall()}

        # 3. Failures per reason (from reasons array)
        await cur.execute(
            """
            SELECT unnest(reasons) as reason, count(*) as cnt
            FROM documents
            WHERE status IN ('REJECTED', 'NEEDS_REVIEW') AND cardinality(reasons) > 0
            GROUP BY reason
            """
        )
        fail_reasons = {r["reason"]: r["cnt"] for r in await cur.fetchall()}

        # 4. LLM calls per task
        await cur.execute("SELECT task, count(*) as cnt FROM model_calls GROUP BY task")
        llm_task_counts = {r["task"]: r["cnt"] for r in await cur.fetchall()}
        total_calls = sum(llm_task_counts.values())

        # 5. Tokens in / out and latency
        await cur.execute(
            """
            SELECT coalesce(sum(tokens_in), 0) as total_tokens_in,
                   coalesce(sum(tokens_out), 0) as total_tokens_out,
                   coalesce(avg(latency_ms), 0) as avg_latency
            FROM model_calls
            """
        )
        tokens_row = await cur.fetchone()
        tokens_in = tokens_row["total_tokens_in"] if tokens_row else 0
        tokens_out = tokens_row["total_tokens_out"] if tokens_row else 0
        avg_llm_lat_s = float(tokens_row["avg_latency"] or 0) / 1000.0

        # 6. LLM cache entries
        await cur.execute("SELECT count(*) as cnt FROM llm_cache")
        cache_row = await cur.fetchone()
        cache_entries = cache_row["cnt"] if cache_row else 0

    lines = [
        "# HELP cv_processed_total Total count of successfully processed CVs (READY)",
        "# TYPE cv_processed_total counter",
        f"cv_processed_total {cv_processed_ready}",
        "",
        "# HELP cv_status_total Current count of documents by status",
        "# TYPE cv_status_total gauge",
    ]

    for st_name in sorted(cv_status_counts.keys()):
        lines.append(f'cv_status_total{{status="{st_name}"}} {cv_status_counts[st_name]}')

    lines.extend(
        [
            "",
            "# HELP cv_failures_total Total count of CV failures grouped by exact reason",
            "# TYPE cv_failures_total counter",
        ]
    )
    for r_name in sorted(fail_reasons.keys()):
        safe_r = r_name.replace('"', '\\"')
        lines.append(f'cv_failures_total{{reason="{safe_r}"}} {fail_reasons[r_name]}')

    lines.extend(
        [
            "",
            "# HELP llm_calls_total Total calls made to LLM gateway by task",
            "# TYPE llm_calls_total counter",
            f"llm_calls_total {total_calls}",
        ]
    )
    for task_name in sorted(llm_task_counts.keys()):
        lines.append(f'llm_calls_total{{task="{task_name}"}} {llm_task_counts[task_name]}')

    lines.extend(
        [
            "",
            "# HELP llm_tokens_total Total tokens processed by LLM",
            "# TYPE llm_tokens_total counter",
            f'llm_tokens_total{{type="prompt"}} {tokens_in}',
            f'llm_tokens_total{{type="completion"}} {tokens_out}',
            "",
            "# HELP pipeline_stage_latency_seconds Average measured stage latency in seconds",
            "# TYPE pipeline_stage_latency_seconds gauge",
            f'pipeline_stage_latency_seconds{{stage="llm_model"}} {avg_llm_lat_s:.3f}',
            "",
            "# HELP llm_cache_entries_total Total cached LLM verification entries in database",
            "# TYPE llm_cache_entries_total gauge",
            f"llm_cache_entries_total {cache_entries}",
            "",
        ]
    )

    _cached_metrics_text = "\n".join(lines) + "\n"
    _cached_metrics_time = now
    return Response(content=_cached_metrics_text, media_type="text/plain; version=0.0.4; charset=utf-8")
