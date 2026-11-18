"""Database connection pool and async session manager using psycopg 3."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.infrastructure.config import settings
from src.infrastructure.logging import logger

_pool: AsyncConnectionPool | None = None
_pool_loop: asyncio.AbstractEventLoop | None = None
_pool_lock: asyncio.Lock | None = None


def _get_pool_lock() -> asyncio.Lock:
    global _pool_lock

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if _pool_lock is None or getattr(_pool_lock, "_loop", None) != loop:
        _pool_lock = asyncio.Lock()
    return _pool_lock


async def get_db_pool() -> AsyncConnectionPool:
    global _pool, _pool_loop

    current_loop = asyncio.get_running_loop()
    lock = _get_pool_lock()

    async with lock:
        if _pool is not None and not _pool.closed and _pool_loop is not None and _pool_loop != current_loop:
            _pool = None

        if _pool is None or _pool.closed:
            _pool_loop = current_loop
            logger.info("Initializing async database connection pool...")

            _pool = AsyncConnectionPool(
                conninfo=settings.DATABASE_URL,
                min_size=settings.DB_POOL_MIN,
                max_size=settings.DB_POOL_MAX,
                open=False,
            )
            await _pool.open()
            logger.info("Async database connection pool opened successfully.")
        return _pool


async def close_db_pool() -> None:
    global _pool, _pool_loop
    if _pool is not None:
        p = _pool
        _pool = None
        _pool_loop = None
        with contextlib.suppress(Exception):
            import asyncio

            await asyncio.wait_for(p.close(timeout=0.1), timeout=0.2)


@contextlib.asynccontextmanager
async def get_connection() -> AsyncGenerator[Any, None]:
    # Only the pool is recreated; errors raised by the caller's body propagate unchanged.
    pool = await get_db_pool()
    if pool.closed:
        await close_db_pool()
        pool = await get_db_pool()
    async with pool.connection() as conn:
        conn.row_factory = dict_row  # type: ignore[assignment]
        yield conn
