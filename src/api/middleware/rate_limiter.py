"""In-memory sliding window rate limiter for API protection (M6).

Note: This in-memory limiter operates on single-process sliding window state.
For multi-process or distributed scaling, back with Redis or PostgreSQL.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from src.domain.auth import decode_access_token

_request_history: dict[str, list[float]] = defaultdict(list)
_total_requests_counter = 0


def clear_rate_limiter_state() -> None:
    """Helper for testing to reset rate limit state."""
    global _total_requests_counter
    _request_history.clear()
    _total_requests_counter = 0


def check_rate_limit(max_requests: int = 60, window_seconds: int = 60):
    async def dependency(request: Request):
        global _total_requests_counter
        _total_requests_counter += 1

        now = time.monotonic()

        # Periodic sweep every 1000 requests to prune stale memory
        if _total_requests_counter % 1000 == 0:
            stale_keys = [
                k
                for k, timestamps in _request_history.items()
                if not timestamps or timestamps[-1] < (now - window_seconds)
            ]
            for k in stale_keys:
                _request_history.pop(k, None)

        # 1. Determine key identifier (user_id if authenticated, otherwise client IP)
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            token_data = decode_access_token(token)
            if token_data and token_data.user_id:
                user_id = token_data.user_id

        route_obj = request.scope.get("route")
        route_path = getattr(route_obj, "path", None) or request.url.path

        if user_id:
            key = f"user:{user_id}:{route_path}"
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"
            key = f"ip:{client_ip}:{route_path}"

        # 2. Clean timestamps within window
        history = _request_history[key]
        valid_from = now - window_seconds
        updated_history = [t for t in history if t > valid_from]

        if not updated_history:
            _request_history.pop(key, None)
        else:
            _request_history[key] = updated_history

        if len(_request_history.get(key, [])) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: maximum {max_requests} requests per {window_seconds}s.",
            )

        _request_history[key].append(now)

    return dependency
