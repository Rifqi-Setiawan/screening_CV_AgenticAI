import uuid

import httpx
import pytest

from src.api.routes.metrics import clear_metrics_cache
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection


@pytest.mark.asyncio
async def test_metrics_reflect_real_database_failures(client: httpx.AsyncClient):
    clear_metrics_cache()
    headers = {"Authorization": f"Bearer {settings.METRICS_TOKEN}"}

    unique_reason = f"CORRUPTED_FILE_REASON_{uuid.uuid4().hex[:8]}"
    test_tenant = uuid.uuid4()
    job_id = uuid.uuid4()

    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text)
            VALUES (%s, %s, 'Metrics Test Job', 'JD')
            """,
            (job_id, test_tenant),
        )
        await cur.execute(
            """
            INSERT INTO documents (id, tenant_id, job_id, original_filename, size_bytes, sha256, status, reasons)
            VALUES (%s, %s, %s, 'fail.pdf', 100, %s, 'REJECTED', ARRAY[%s])
            """,
            (uuid.uuid4(), test_tenant, job_id, f"sha_{uuid.uuid4().hex[:12]}", unique_reason),
        )
        await conn.commit()

    clear_metrics_cache()
    res = await client.get("/metrics", headers=headers)
    assert res.status_code == 200
    text = res.text

    # Verify real reason is present in metrics output
    assert f'cv_failures_total{{reason="{unique_reason}"}} 1' in text

    # Verify old hardcoded strings are GONE
    assert 'pipeline_stage_latency_seconds{stage="sanitizer"} 0.052' not in text
    assert 'pipeline_stage_latency_seconds{stage="parsing_adapter"} 0.315' not in text
    assert 'llm_cache_total{result="hit"} 45' not in text
