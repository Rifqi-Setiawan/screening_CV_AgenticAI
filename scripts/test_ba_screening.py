"""Comprehensive live evaluation and audit of Business Analyst applicants for PT Integra Sistem Optima."""

import asyncio
import glob
import hashlib
import json
import time
import uuid
from pathlib import Path

from src.domain.jd_compiler import compile_job_requirements
from src.domain.screening_service import execute_screening_run
from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.worker.processor import process_document

TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
ADMIN_USER_ID = uuid.UUID("adbbfe35-43d1-40ef-a02b-10c975110219")

JD_TEXT = """Posisi: Business Analyst - Management & Systems Consulting
Perusahaan: PT Integra Sistem Optima
Lokasi: Bandung, Jawa Barat
Tipe: Full-time

Tentang Pekerjaan:
PT Integra Sistem Optima (ISO Consulting) membuka lowongan untuk posisi Business Analyst yang bertanggung jawab dalam analisis proses bisnis klien, penyusunan SOP dan Way of Working, studi kelayakan, pemodelan keuangan, serta visualisasi data manajemen.

Kualifikasi Wajib:
- Minimal 1 tahun pengalaman kerja sebagai Business Analyst, Management Consultant, Financial Analyst, atau Business Development.
- Pendidikan minimal S1 di bidang Manajemen, Bisnis, Akuntansi, Ekonomi, Teknik Industri, Statistika, Matematika, atau Sistem Informasi.
- Menguasai pemodelan proses bisnis, penyusunan SOP, atau analisis alur kerja sistem.
- Mahir Microsoft Excel atau spreadsheet untuk analisis data dan pelaporan.

Nilai Tambah (Nice to Have):
- Pengalaman dalam studi kelayakan bisnis, financial modeling (DCF, NPV, IRR), valuasi bisnis, atau analisis strategis (SWOT, PESTEL).
- Menguasai tools visualisasi data dan Business Intelligence (Looker Studio, Power BI, Tableau, atau SQL).
- Memiliki pengalaman memimpin tim kerja, koordinasi proyek, atau prestasi kompetisi bisnis.
"""


async def run_pipeline():
    async with get_connection() as conn, conn.cursor() as cur:
        # 1. Create Job
        job_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO jobs (id, tenant_id, title, location, employment_type, jd_text, status, created_by)
            VALUES (%s, %s, 'Business Analyst - ISO Live Audit Test', 'Bandung, Jawa Barat', 'Penuh Waktu (Full-time)', %s, 'OPEN', %s)
            RETURNING id
            """,
            (job_id, TENANT_ID, JD_TEXT, ADMIN_USER_ID),
        )
        print(f"[1] Job created: {job_id}")

        # 2. Compile Requirements
        compiled = await compile_job_requirements(JD_TEXT, tenant_id=TENANT_ID)
        set_id = uuid.uuid4()
        cat_weights = {"EXPERIENCE": 40.0, "HARD_SKILLS": 30.0, "EDUCATION_CERT": 15.0, "ACHIEVEMENT": 15.0}

        await cur.execute(
            """
            INSERT INTO requirement_sets (id, tenant_id, job_id, version, status, category_weights, approved_by, approved_at)
            VALUES (%s, %s, %s, 1, 'APPROVED', %s, %s, now())
            """,
            (set_id, TENANT_ID, job_id, json.dumps(cat_weights), ADMIN_USER_ID),
        )

        for r in compiled["requirements"]:
            r_uuid = uuid.uuid4()
            await cur.execute(
                """
                INSERT INTO requirements (
                    id, tenant_id, requirement_set_id, requirement_id, description, category, kind,
                    importance, weight, concepts, params, source_text, lint_flags
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    r_uuid,
                    TENANT_ID,
                    set_id,
                    r["requirement_id"],
                    r["description"],
                    r["category"],
                    r["kind"],
                    r["importance"],
                    r["weight"],
                    r.get("concepts", []),
                    json.dumps(r.get("params", {})),
                    r.get("source_text", ""),
                    r.get("lint_flags", []),
                ),
            )

        await conn.commit()
        print(f"[2] Approved {len(compiled['requirements'])} requirements.")

        # 3. Ingest 12 CVs
        ba_dir = (
            "/srv/hermes-control/services/cv-screening/data/ba_test/Business Analyst - Integra Sistem Optima (ISO)"
        )
        pdf_files = sorted(glob.glob(f"{ba_dir}/*.pdf"))
        print(f"[3] Ingesting {len(pdf_files)} PDF CVs into storage vault...")

        doc_ids = []
        for p in pdf_files:
            fname = Path(p).name
            with open(p, "rb") as f:
                content = f.read()
            fhash = hashlib.sha256(content).hexdigest()
            doc_id = uuid.uuid4()
            storage_key = f"{fhash}.pdf"
            storage_path = Path(settings.STORAGE_VAULT_PATH) / str(TENANT_ID)
            storage_path.mkdir(parents=True, exist_ok=True)
            with open(storage_path / f"{fhash}.pdf", "wb") as sf:
                sf.write(content)

            await cur.execute(
                """
                INSERT INTO documents (
                    id, tenant_id, job_id, original_filename, size_bytes, mime, sha256, storage_key, status
                )
                VALUES (%s, %s, %s, %s, %s, 'application/pdf', %s, %s, 'RECEIVED')
                """,
                (doc_id, TENANT_ID, job_id, fname, len(content), fhash, storage_key),
            )
            doc_ids.append((doc_id, fname))

        await conn.commit()
        print(f"    Stored {len(doc_ids)} documents.")

        # 4. Process each document through worker pipeline
        print("[4] Processing documents through worker (PDF layout, adapter, encryption, redaction, chunking)...")
        for doc_id, fname in doc_ids:
            t0 = time.time()
            res = await process_document(doc_id)
            print(f"    - {fname[:45]}: status={res.get('status')} ({time.time() - t0:.2f}s)")

        # 5. Create Screening Run
        run_id = uuid.uuid4()
        versions_info = {
            "extractor": f"cv-extractor {settings.EXTRACTOR_VERSION}",
            "embedding": settings.EMBEDDING_MODEL,
            "scoring": settings.SCORING_VERSION,
            "scoring_mode": settings.SCORING_MODE,
        }
        await cur.execute(
            """
            INSERT INTO screening_runs (
                id, tenant_id, job_id, requirement_set_id, status, as_of, versions, params, eligibility_snapshot, progress, started_at
            )
            VALUES (%s, %s, %s, %s, 'QUEUED', '2026-10-14', %s, %s, '[]'::jsonb, '{"done":0,"total":12}'::jsonb, now())
            """,
            (
                run_id,
                TENANT_ID,
                job_id,
                set_id,
                json.dumps(versions_info),
                json.dumps({"use_verifier": False, "as_of": "2026-10-14"}),
            ),
        )
        await conn.commit()
        print(f"[5] Created screening run: {run_id}")

        # 6. Execute screening run
        print("[6] Executing screening run (scoring, banding, ranking)...")
        t_exec = time.time()
        run_res = await execute_screening_run(run_id)
        print(f"    Execution completed in {time.time() - t_exec:.2f}s: {run_res}")

        return job_id, run_id


if __name__ == "__main__":
    asyncio.run(run_pipeline())
