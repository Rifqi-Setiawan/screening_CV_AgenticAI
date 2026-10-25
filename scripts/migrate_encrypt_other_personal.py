"""Data migration script: Encrypt legacy plaintext other_personal rows in candidate_identities using pgp_sym_encrypt."""

from __future__ import annotations

import asyncio
import json

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger


async def migrate_encrypt_other_personal() -> int:
    key = settings.PII_ENCRYPTION_KEY
    if not key or len(key) < 32:
        raise RuntimeError("PII_ENCRYPTION_KEY must be configured before running encryption migration.")

    count = 0
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT candidate_id, tenant_id, other_personal
            FROM candidate_identities
            WHERE other_personal IS NOT NULL
            """
        )
        rows = await cur.fetchall()

        for r in rows:
            cid = r["candidate_id"]
            tid = r["tenant_id"]
            raw = r["other_personal"]

            raw_bytes = bytes(raw) if isinstance(raw, (bytes, memoryview)) else str(raw).encode("utf-8")
            # OpenPGP symmetric cipher packet starts with \xc3\r\x04 or \xc3\r
            if raw_bytes.startswith(b"\xc3\r\x04") or raw_bytes.startswith(b"\xc3\r"):
                continue

            # If plaintext bytes or str: parse and encrypt
            try:
                try:
                    parsed_json = json.dumps(json.loads(raw_bytes.decode("utf-8")))
                except Exception:
                    parsed_json = json.dumps({})

                await cur.execute(
                    """
                    UPDATE candidate_identities
                    SET other_personal = pgp_sym_encrypt(%s, %s)
                    WHERE candidate_id = %s AND tenant_id = %s
                    """,
                    (parsed_json, key, cid, tid),
                )
                count += 1
            except Exception as e:
                logger.warning(f"Could not parse or re-encrypt candidate {cid}: {e}")

        await conn.commit()

    logger.info(f"Encrypted {count} legacy plaintext other_personal records.")
    return count


if __name__ == "__main__":
    asyncio.run(migrate_encrypt_other_personal())
