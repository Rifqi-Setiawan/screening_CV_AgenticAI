#!/usr/bin/env python3
"""Throughput test for batch ingestion of 300 CVs on VPS CPU."""
from __future__ import annotations

import asyncio
import io
import time
import uuid
import zipfile
from pathlib import Path

from src.infrastructure.database import close_db_pool, get_connection
from src.worker.processor import process_document

TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def run_throughput_test():
    core_dir = Path("docs/spec/golden_dataset/cvs/core")
    core_files = sorted(list(core_dir.glob("*.pdf")) + list(core_dir.glob("*.docx")))
    print(f"Base files: {len(core_files)}")

    # Create 300 distinct CVs in memory by duplicating core files with distinct filenames & slight metadata change
    total_target = 300
    test_files = []
    idx = 0
    while len(test_files) < total_target:
        src_f = core_files[idx % len(core_files)]
        ext = src_f.suffix
        content = bytearray(src_f.read_bytes())
        # Append unique comment/byte so sha256 is unique for the test
        unique_tag = f"\n% TEST_CV_{len(test_files):04d}\n".encode("utf-8")
        content.extend(unique_tag)
        fname = f"CV_batch_{len(test_files):04d}_{src_f.stem}{ext}"
        test_files.append((fname, bytes(content)))
        idx += 1

    print(f"Generated {len(test_files)} distinct CVs for throughput test.")

    # Create a test job in database
    job_id = uuid.uuid4()
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, jd_text, external_ref)
            VALUES (%s, %s, 'Throughput 300 CV Benchmark', 'Scale throughput test', 'JD-THROUGHPUT')
            """,
            (job_id, TENANT_ID),
        )
        await conn.commit()

    from src.infrastructure.config import settings
    import hashlib

    vault_dir = Path(settings.STORAGE_VAULT_PATH) / str(TENANT_ID)
    vault_dir.mkdir(parents=True, exist_ok=True)

    doc_ids = []
    t_start = time.time()

    # Step 1: Storage and document registration
    print("Writing files to vault and registering in documents table...")
    async with get_connection() as conn, conn.cursor() as cur:
        for fname, content in test_files:
            sha256 = hashlib.sha256(content).hexdigest()
            ext = Path(fname).suffix.lstrip(".").lower()
            storage_key = f"{sha256}.{ext}"
            file_path = vault_dir / storage_key
            if not file_path.exists():
                file_path.write_bytes(content)
                file_path.chmod(0o600)

            doc_id = uuid.uuid4()
            await cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, job_id, original_filename, size_bytes, mime, sha256, storage_key, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'RECEIVED')
                """,
                (doc_id, TENANT_ID, job_id, fname, len(content), f"application/{ext}", sha256, storage_key),
            )
            doc_ids.append(doc_id)
        await conn.commit()

    t_reg = time.time() - t_start
    print(f"Registered {len(doc_ids)} documents in {t_reg:.2f}s.")

    # Step 2: Ingestion & Extraction & Embedding Pipeline
    print("Processing ingestion, adapter extraction, redaction, and embedding...")
    t_proc_start = time.time()

    processed_count = 0
    errors_count = 0

    for idx, did in enumerate(doc_ids, 1):
        res = await process_document(did)
        if res.get("status") in ("READY", "NEEDS_REVIEW"):
            processed_count += 1
        else:
            errors_count += 1
        if idx % 50 == 0:
            elapsed = time.time() - t_proc_start
            speed = idx / elapsed
            print(f"  Processed {idx}/{len(doc_ids)} ({speed:.2f} CVs/sec)...")

    total_time = time.time() - t_proc_start
    total_pipeline_time = time.time() - t_start
    throughput = len(doc_ids) / total_time

    print("\n==========================================")
    print("=== HASIL UJI THROUGHPUT 300 CV (CPU) ===")
    print("==========================================")
    print(f"Total CV Diproses   : {len(doc_ids)}")
    print(f"Berhasil (READY)    : {processed_count}")
    print(f"Gagal / Ditolak     : {errors_count}")
    print(f"Waktu Pipeline      : {total_pipeline_time:.2f} detik (~{total_pipeline_time/60:.2f} menit)")
    print(f"Kecepatan Rata-rata : {throughput:.2f} CV/detik")
    print(f"Target Spesifikasi  : < 15 menit untuk 300 CV")
    print(f"Status Target       : {'LULUS' if total_pipeline_time < 900 else 'GAGAL'}")
    print("==========================================\n")

    await close_db_pool()


if __name__ == "__main__":
    asyncio.run(run_throughput_test())
