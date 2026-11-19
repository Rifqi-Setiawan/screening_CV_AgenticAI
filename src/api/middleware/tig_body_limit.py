"""Bound public TIG request bodies before JSON or multipart parsing."""

from __future__ import annotations

from fastapi import HTTPException
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.infrastructure.config import settings


class TigBodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT"} or not path.startswith("/api/v1/tig/apply/"):
            await self.app(scope, receive, send)
            return

        prefill = path.rstrip("/").endswith(("/prefill", "/cv"))  # CV file uploads
        limit = (settings.MAX_UPLOAD_SIZE_MB * 1024 + 64 if prefill else 512) * 1024
        message = "Berkas CV terlalu besar." if prefill else "Formulir lamaran terlalu besar."
        length = Headers(scope=scope).get("content-length")
        if length and length.isdecimal() and int(length) > limit:
            await JSONResponse({"detail": message}, status_code=413)(scope, receive, send)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            chunk = await receive()
            received += len(chunk.get("body", b""))
            if received > limit:
                raise HTTPException(413, message)
            return chunk

        await self.app(scope, limited_receive, send)
