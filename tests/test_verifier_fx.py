import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.verifier import verify_requirement_with_llm
from src.worker.redaction import redact_text


def test_redactor_strips_pii_cleanly():
    raw_text = "John Doe is a Senior Python Developer.\nEmail: john.doe@example.com, Phone: +6281234567890\nGender: Laki-laki\nTanggal Lahir: 1995-05-15\nExperienced with FastAPI."
    redacted = redact_text(raw_text, name="John Doe", emails=["john.doe@example.com"], phones=["+6281234567890"])

    assert "john.doe@example.com" not in redacted
    assert "+6281234567890" not in redacted
    assert "John" not in redacted
    assert "Doe" not in redacted
    assert "Laki-laki" not in redacted
    assert "[EMAIL]" in redacted
    assert "[TELEPON]" in redacted
    assert "FastAPI" in redacted


@pytest.mark.asyncio
async def test_verifier_with_valid_text_calls_llm():
    req = {
        "requirement_id": "R1",
        "description": "5+ years backend python",
        "category": "HARD_SKILLS",
        "kind": "SKILL",
    }
    cv_text = "Worked as Senior Backend Engineer building microservices with Python and PostgreSQL for 6 years."
    snippets = ["experience: Senior Backend Engineer building microservices with Python"]

    mock_llm_res = {
        "state": "STRONG",
        "quote": "Senior Backend Engineer building microservices with Python",
        "reason": "Strong Python experience mentioned",
    }

    with (
        patch("src.domain.verifier._get_db_cache", return_value=None),
        patch("src.domain.verifier.gateway.call_chat", new_callable=AsyncMock) as mock_call,
    ):
        mock_call.return_value = mock_llm_res
        state, quote, flags = await verify_requirement_with_llm(cv_text, req, "PARTIAL", snippets)
        assert state == "STRONG"
        assert quote == "Senior Backend Engineer building microservices with Python"
        assert flags == []
        assert mock_call.called


@pytest.mark.asyncio
async def test_verifier_grounding_hardening_checks():
    req = {
        "requirement_id": "R1",
        "description": "Python skill",
        "category": "HARD_SKILLS",
        "kind": "SKILL",
    }
    cv_text = "Python developer in university club."
    snippets = ["projects: Python developer in university club"]

    # 1. Quote < 5 chars -> GROUNDING_FAIL
    mock_short = {"state": "STRONG", "quote": "Py", "reason": "short"}
    with (
        patch("src.domain.verifier._get_db_cache", return_value=None),
        patch("src.domain.verifier.gateway.call_chat", new_callable=AsyncMock) as mock_call,
    ):
        mock_call.return_value = mock_short
        state, quote, flags = await verify_requirement_with_llm(cv_text, req, "PARTIAL", snippets)
        assert state == "PARTIAL"
        assert "GROUNDING_FAIL" in flags

    # 2. Quote outside snippet -> GROUNDING_FAIL
    mock_outside = {"state": "STRONG", "quote": "Invented quote not in snippets", "reason": "hallucinated"}
    with (
        patch("src.domain.verifier._get_db_cache", return_value=None),
        patch("src.domain.verifier.gateway.call_chat", new_callable=AsyncMock) as mock_call,
    ):
        mock_call.return_value = mock_outside
        state, quote, flags = await verify_requirement_with_llm(cv_text, req, "PARTIAL", snippets)
        assert state == "PARTIAL"
        assert "GROUNDING_FAIL" in flags

    # 3. PARTIAL only rises to STRONG if in experience context (not just university project)
    mock_non_exp = {"state": "STRONG", "quote": "Python developer in university", "reason": "academic"}
    with (
        patch("src.domain.verifier._get_db_cache", return_value=None),
        patch("src.domain.verifier.gateway.call_chat", new_callable=AsyncMock) as mock_call,
    ):
        mock_call.return_value = mock_non_exp
        state, quote, flags = await verify_requirement_with_llm(cv_text, req, "PARTIAL", snippets)
        # Should stay PARTIAL because snippet lacks experience keywords
        assert state == "PARTIAL"


@pytest.mark.asyncio
async def test_verifier_timeout_falls_back_safely():
    req = {
        "requirement_id": "R2",
        "description": "Docker expertise",
        "category": "HARD_SKILLS",
        "kind": "SKILL",
    }
    cv_text = "Experienced in Docker containerization."
    snippets = ["Experienced in Docker containerization."]

    async def slow_call(*args, **kwargs):
        await asyncio.sleep(15.0)
        return {"state": "STRONG", "quote": "Docker", "reason": "ok"}

    with patch("src.domain.verifier.gateway.call_chat", side_effect=slow_call):
        state, quote, flags = await verify_requirement_with_llm(cv_text, req, "PARTIAL", snippets)
        assert state == "PARTIAL"
        assert quote == ""
        assert "VERIFIER_TIMEOUT" in flags
