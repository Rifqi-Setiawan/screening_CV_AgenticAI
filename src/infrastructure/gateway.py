"""LLM gateway client interfacing with local 9Router proxy with privacy safeguards (FX-15)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from typing import Any

import httpx

from src.domain.pii import EMAIL_REGEX, PHONE_REGEX
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger


class PrivacyViolationError(ValueError):
    pass


def resolve_router_key() -> str:
    """Resolves LLM Gateway API key strictly from environment configuration."""
    key = settings.LLM_GATEWAY_KEY or os.environ.get("LLM_GATEWAY_KEY", "")
    return key.strip()


def reset_key_cache() -> None:
    """Compatibility reset helper."""
    pass


def parse_llm_json(content_str: str) -> dict[str, Any] | list[Any] | None:
    """Robust JSON parser handling raw text, markdown blocks, and outer braces."""
    if not content_str:
        return None
    clean_text = content_str.strip()

    # 1. Direct JSON parse
    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass

    # 2. Markdown code block
    m = re.search(r"```(?:json)?\s*([\{\[].*?[\}\]])\s*```", clean_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Outer curly braces (object)
    start = clean_text.find("{")
    end = clean_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(clean_text[start : end + 1])
        except json.JSONDecodeError:
            pass

    # 4. Outer square brackets (array)
    start_b = clean_text.find("[")
    end_b = clean_text.rfind("]")
    if start_b != -1 and end_b != -1 and end_b > start_b:
        try:
            return json.loads(clean_text[start_b : end_b + 1])
        except json.JSONDecodeError:
            pass

    return None


class ModelGateway:
    def __init__(self):
        self.base_url = settings.LLM_GATEWAY_URL
        self._client: httpx.AsyncClient | None = None

    def get_client(self) -> httpx.AsyncClient:
        """Returns AsyncClient session without stale keepalive pooling."""
        limits = httpx.Limits(max_keepalive_connections=0, max_connections=10, keepalive_expiry=5.0)
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=180.0, limits=limits)
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def verify_redacted_text(self, text: str) -> None:
        """Pre-flight safety inspection: blocks requests if raw emails or phones are present.

        Applies strictly to ALL tasks without bypass.
        """
        if EMAIL_REGEX.search(text):
            raise PrivacyViolationError("Blocked LLM request: raw unredacted email detected in payload.")
        if PHONE_REGEX.search(text):
            raise PrivacyViolationError("Blocked LLM request: raw unredacted phone number detected in payload.")

    async def call_chat(
        self,
        messages: list[dict[str, str]],
        task: str = "jd_compilation",
        tenant_id: uuid.UUID | None = None,
        json_mode: bool = True,
        model: str | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        if settings.LLM_DATA_POLICY == "paid_or_local_only":
            logger.warning("LLM call skipped: policy 'paid_or_local_only' restricts dev router usage.")
            return None

        # Pre-flight safety inspection
        combined_prompt = " ".join([m.get("content", "") for m in messages])
        self.verify_redacted_text(combined_prompt)

        api_key = resolve_router_key()
        if model is None:
            if task in ("profiler", "profiling"):
                model = settings.LLM_MODEL_PROFILER
            elif task == "critic":
                model = settings.LLM_MODEL_CRITIC
            elif task == "verification":
                model = settings.LLM_MODEL_VERIFIER
            else:
                model = settings.LLM_MODEL_JD_COMPILER

        input_hash = hashlib.sha256(combined_prompt.encode()).hexdigest()
        t0 = time.time()

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}" if api_key else "",
        }

        call_id = uuid.uuid4()
        status_str = "FAILED"
        tokens_in = tokens_out = 0
        output_hash = ""

        max_retries = 3
        backoff_sec = 0.5

        for attempt in range(max_retries):
            try:
                client = self.get_client()
                res = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                latency_ms = int((time.time() - t0) * 1000)

                # Retry on 429 rate limit or 5xx server error
                if res.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                    logger.warning(
                        f"9Router returned HTTP {res.status_code}, retrying in {backoff_sec}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(backoff_sec)
                    backoff_sec *= 2.0
                    continue

                if res.status_code == 200:
                    status_str = "SUCCESS"
                    content_str = ""
                    tokens_in = tokens_out = 0

                    if res.text.strip().startswith("data:"):
                        content_parts = []
                        for line in res.text.splitlines():
                            line = line.strip()
                            if line.startswith("data:") and line != "data: [DONE]":
                                chunk_data = line[5:].strip()
                                if chunk_data:
                                    try:
                                        c = json.loads(chunk_data)
                                        for ch in c.get("choices", []):
                                            content_parts.append(
                                                ch.get("delta", {}).get("content", "")
                                                or ch.get("message", {}).get("content", "")
                                            )
                                    except Exception:
                                        pass
                        content_str = "".join(content_parts)
                    else:
                        resp_data = res.json()
                        usage = resp_data.get("usage", {})
                        tokens_in = usage.get("prompt_tokens", 0)
                        tokens_out = usage.get("completion_tokens", 0)
                        content_str = resp_data["choices"][0]["message"]["content"]

                    output_hash = hashlib.sha256(content_str.encode()).hexdigest()

                    # Record model call without storing CV text
                    await self._record_call(
                        call_id=call_id,
                        tenant_id=tenant_id,
                        task=task,
                        model=model,
                        input_hash=input_hash,
                        output_hash=output_hash,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        latency_ms=latency_ms,
                        status=status_str,
                    )

                    parsed = parse_llm_json(content_str)
                    if parsed is not None:
                        return parsed
                    return {"raw_content": content_str}

                else:
                    logger.warning(f"9Router returned HTTP {res.status_code}: {res.text[:200]}")
                    return None

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                await self.close()
                if attempt < max_retries - 1:
                    logger.warning(f"9Router network error ({e}), retrying in {backoff_sec}s...")
                    await asyncio.sleep(backoff_sec)
                    backoff_sec *= 2.0
                    continue
                logger.warning(f"9Router connection failed after {max_retries} attempts: {e}")
                return None
            except Exception as e:
                await self.close()
                logger.warning(f"9Router call failed: {e}")
                return None

        return None

    async def _record_call(
        self,
        call_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        task: str,
        model: str,
        input_hash: str,
        output_hash: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        status: str,
    ) -> None:
        try:
            async with get_connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO model_calls (
                        id, tenant_id, task, provider, model, prompt_version, input_hash, output_hash,
                        tokens_in, tokens_out, latency_ms, status
                    )
                    VALUES (%s, %s, %s, '9router', %s, 'v1.0', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        call_id,
                        tenant_id,
                        task,
                        model,
                        input_hash,
                        output_hash,
                        tokens_in,
                        tokens_out,
                        latency_ms,
                        status,
                    ),
                )
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to record model call: {e}")


gateway = ModelGateway()
