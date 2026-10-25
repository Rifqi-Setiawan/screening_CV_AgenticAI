import pytest

from src.infrastructure.gateway import (
    ModelGateway,
    PrivacyViolationError,
    parse_llm_json,
)


def test_parse_llm_json():
    # 1. Direct JSON
    assert parse_llm_json('{"key": "value"}') == {"key": "value"}
    # 2. Markdown block
    assert parse_llm_json('Here is output:\n```json\n{"state": "STRONG"}\n```') == {"state": "STRONG"}
    # 3. Outer curly braces with text around
    assert parse_llm_json('Result: {"status": "ok"} Thank you.') == {"status": "ok"}
    # 4. JSON Array
    assert parse_llm_json('[{"id": "R1"}, {"id": "R2"}]') == [{"id": "R1"}, {"id": "R2"}]
    # 5. Invalid
    assert parse_llm_json("no json here") is None


def test_privacy_violation_error_on_raw_pii():
    gw = ModelGateway()
    with pytest.raises(PrivacyViolationError):
        gw.verify_redacted_text("Candidate email is user@example.com")

    with pytest.raises(PrivacyViolationError):
        gw.verify_redacted_text("Candidate phone is +628123456789")

    # Clean text does not raise
    gw.verify_redacted_text("Candidate has 3 years of Python experience [EMAIL] [TELEPON]")


@pytest.mark.asyncio
async def test_gateway_persistent_client_reuse():
    gw = ModelGateway()
    c1 = gw.get_client()
    c2 = gw.get_client()
    assert c1 is c2
    await gw.close()
    assert gw._client is None
