"""One-off script to reprocess candidate_profiles and populate full_text_redacted."""

import asyncio
from pathlib import Path
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.worker.redaction import redact_text
from src.worker.sanitizer import sanitize_file


async def reprocess_profiles():
    vault_dir = Path(settings.STORAGE_VAULT_PATH)
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT cp.id as profile_id, cp.document_id, cp.profile, cp.matching_profile,
                   d.original_filename, d.storage_key,
                   ci.full_name, ci.email, ci.phone
            FROM candidate_profiles cp
            JOIN documents d ON d.id = cp.document_id
            LEFT JOIN candidate_identities ci ON ci.candidate_id = d.candidate_id
            WHERE cp.full_text_redacted IS NULL
            """
        )
        rows = await cur.fetchall()
        print(f"Found {len(rows)} candidate profiles needing full_text_redacted.")

        for r in rows:
            prof_id = r["profile_id"]
            storage_key = r["storage_key"]
            filename = r["original_filename"]
            name = r["full_name"] or ""
            emails = [r["email"]] if r.get("email") else []
            phones = [r["phone"]] if r.get("phone") else []

            raw_text = ""
            if storage_key:
                file_path = vault_dir / storage_key
                if file_path.exists():
                    try:
                        content = file_path.read_bytes()
                        san = sanitize_file(content, filename)
                        raw_text = san.extracted_text
                    except Exception as e:
                        print(f"Error reading vault file {file_path}: {e}")

            if not raw_text:
                # Fallback: synthesize from matching_profile or chunks
                prof_data = r["matching_profile"] or {}
                parts = []
                if prof_data.get("headline"):
                    parts.append(prof_data["headline"])
                if prof_data.get("summary"):
                    parts.append(prof_data["summary"])
                for exp in prof_data.get("experiences", []):
                    parts.append(f"{exp.get('title', '')} {exp.get('organization', '')}")
                    for b in exp.get("bullets", []):
                        parts.append(b.get("text", ""))
                raw_text = "\n".join(parts)

            redacted = redact_text(raw_text, name, emails, phones)
            await cur.execute(
                "UPDATE candidate_profiles SET full_text_redacted = %s WHERE id = %s",
                (redacted, prof_id),
            )
            print(f"Updated profile {prof_id} (chars: {len(redacted)})")

        await conn.commit()
    print("Reprocessing completed successfully.")


if __name__ == "__main__":
    asyncio.run(reprocess_profiles())
