from unittest.mock import patch

from src.infrastructure.config import settings
from src.infrastructure.gateway import resolve_router_key


def test_resolve_router_key_from_settings():
    with patch.object(settings, "LLM_GATEWAY_KEY", "test-env-key-123"):
        key = resolve_router_key()
        assert key == "test-env-key-123"


def test_resolve_router_key_from_os_environ():
    with (
        patch.object(settings, "LLM_GATEWAY_KEY", ""),
        patch.dict("os.environ", {"LLM_GATEWAY_KEY": "os-env-key-456"}),
    ):
        key = resolve_router_key()
        assert key == "os-env-key-456"
