"""The scoring call must outlast the slow upstream model (observed 113-136 s per answer) instead of discarding its answer."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from src.domain import tig
from src.domain.tig import TigConfig
from tests.test_tig_transparency import candidate, model_answer


@pytest.mark.asyncio
async def test_assessment_waits_long_enough_for_a_slow_model(monkeypatch):
    waited = {}
    real_wait_for = asyncio.wait_for

    async def call_chat(messages, **kwargs):
        return model_answer(80)

    async def spy_wait_for(awaitable, timeout):
        waited["timeout"] = timeout
        return await real_wait_for(awaitable, None)

    monkeypatch.setattr(tig.gateway, "call_chat", call_chat)
    monkeypatch.setattr(tig.asyncio, "wait_for", spy_wait_for)
    result = await tig.assess_application(candidate(), "Auditor", TigConfig(), uuid4())
    assert result["score"] == 80
    # Longer than the slowest observed answer; the HTTP client's own 180 s limit is what finally cuts a hung call.
    assert waited["timeout"] >= 180
