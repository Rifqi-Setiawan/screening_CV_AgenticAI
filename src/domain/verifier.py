"""LLM Verifier for ambiguous requirements (02_SCORING Section 5)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.gateway import gateway

VALID_STATES = {"STRONG", "PARTIAL", "NOT_DEMONSTRATED"}
VERIFIER_PROMPT_VERSION = "v1"


async def _get_db_cache(cache_key: str) -> dict[str, Any] | None:
    try:
        async with get_connection() as conn, conn.cursor() as cur:
            await cur.execute("SELECT output FROM llm_cache WHERE key = %s", (cache_key,))
            row = await cur.fetchone()
            if row and row["output"]:
                return row["output"] if isinstance(row["output"], dict) else json.loads(row["output"])
    except Exception:
        pass
    return None


async def _save_db_cache(cache_key: str, data: dict[str, Any]) -> None:
    try:
        async with get_connection() as conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO llm_cache (key, task, output)
                VALUES (%s, 'verifier', %s)
                ON CONFLICT (key) DO UPDATE SET output = EXCLUDED.output
                """,
                (cache_key, json.dumps(data)),
            )
            await conn.commit()
    except Exception:
        pass


async def verify_requirement_with_llm(
    cv_full_text: str,
    requirement: dict[str, Any],
    rule_state: str,
    snippets: list[str],
) -> tuple[str, str, list[str]]:
    """Verifies ambiguous requirement using LLM via 9Router.

    Enforces:
    1. Closed choices (STRONG, PARTIAL, NOT_DEMONSTRATED).
    2. Code-level grounding verification (quote must exist in raw CV text and snippets, min 5 chars).
    3. Grounding failure fallbacks cleanly to rule_state + GROUNDING_FAIL flag.
    4. LLM NEVER outputs numeric scores.
    5. Cache lookup to avoid redundant calls (persisted in llm_cache table with model & version).
    6. Non-blocking async execution with strict 10s timeout.
    """
    if not cv_full_text or not snippets:
        return rule_state, "", []

    cache_payload = (
        f"{VERIFIER_PROMPT_VERSION}:{settings.LLM_MODEL_VERIFIER}:"
        f"{requirement.get('requirement_id')}:{requirement.get('description')}:"
        f"{requirement.get('kind')}:{rule_state}:{':'.join(snippets)}"
    )
    cache_key = hashlib.sha256(cache_payload.encode()).hexdigest()

    cached_item = await _get_db_cache(cache_key)
    if cached_item:
        return cached_item.get("state", rule_state), cached_item.get("quote", ""), cached_item.get("flags", [])

    prompt = f"""Kamu adalah verifier kualifikasi kandidat CV.
Tugas: Periksa apakah bukti CV mendukung kualifikasi berikut.

Kriteria: {requirement.get("description", "")}
Kategori: {requirement.get("category", "")}
Kind: {requirement.get("kind", "")}

Potongan teks relevan dari CV kandidat:
{chr(10).join(f"- {s}" for s in snippets[:3])}

Pilihan status yang diizinkan HANYA:
- STRONG: Bukti sangat jelas dan kuat di pekerjaan yang relevan
- PARTIAL: Bukti sebagian, di proyek, atau relevansi terbatas
- NOT_DEMONSTRATED: Bukti tidak ditemukan atau tidak memadai

Instruksi PENTING:
- JANGAN PERNAH mengeluarkan skor angka!
- Keluarkan JSON persis format:
{{
  "state": "STRONG" | "PARTIAL" | "NOT_DEMONSTRATED",
  "quote": "kutipan persis kata demi kata dari potongan teks di atas",
  "reason": "alasan singkat 1 kalimat"
}}
"""
    messages = [
        {
            "role": "system",
            "content": "Kamu adalah JSON-only assistant. Jawab HANYA dalam JSON valid tanpa markdown formatting.",
        },
        {"role": "user", "content": prompt},
    ]

    try:
        # Strict 10-second timeout
        res = await asyncio.wait_for(
            gateway.call_chat(messages, task="verification", json_mode=True),
            timeout=10.0,
        )
    except TimeoutError:
        return rule_state, "", ["VERIFIER_TIMEOUT"]
    except Exception:
        return rule_state, "", ["VERIFIER_ERROR"]

    if not res:
        return rule_state, "", []

    try:
        data = res
        if isinstance(res, str):
            text_str = res.strip()
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text_str)
            if m:
                text_str = m.group(1).strip()
            data = json.loads(text_str)

        if not isinstance(data, dict):
            return rule_state, "", ["INVALID_LLM_STATE"]

        state = str(data.get("state", "")).upper()
        quote = str(data.get("quote", "")).strip()

        if state not in VALID_STATES:
            return rule_state, "", ["INVALID_LLM_STATE"]

        # 1. Grounding check: Quote must be at least 5 chars (e.g. quote "Python" is rejected)
        if len(quote) < 5:
            saved_data = {"state": rule_state, "quote": "", "flags": ["GROUNDING_FAIL"]}
            await _save_db_cache(cache_key, saved_data)
            return rule_state, "", ["GROUNDING_FAIL"]

        # 2. Grounding check with whitespace normalization
        norm_quote = " ".join(quote.lower().split())
        norm_cv = " ".join(cv_full_text.lower().split())
        norm_snippets = " ".join(" ".join(snippets).lower().split())

        # Quote must be present in both CV and the provided snippets
        if norm_quote not in norm_cv or norm_quote not in norm_snippets:
            saved_data = {"state": rule_state, "quote": "", "flags": ["GROUNDING_FAIL"]}
            await _save_db_cache(cache_key, saved_data)
            return rule_state, "", ["GROUNDING_FAIL"]

        # 3. Elevation check: PARTIAL can only be upgraded to STRONG if quote is from experience context
        if rule_state == "PARTIAL" and state == "STRONG":
            is_experience_context = any(
                s.lower().startswith("experience")
                or "pengalaman" in s.lower()
                or "bekerja" in s.lower()
                or "pekerjaan" in s.lower()
                for s in snippets
            )
            if not is_experience_context:
                state = "PARTIAL"

        saved_data = {"state": state, "quote": quote, "flags": []}
        await _save_db_cache(cache_key, saved_data)
        return state, quote, []

    except Exception:
        return rule_state, "", ["LLM_PARSE_ERROR"]
