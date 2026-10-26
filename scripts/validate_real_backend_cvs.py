"""End-to-End Real CV Testing & Validation Script.
Validates the Agentic AI CV Screening Platform (v2.1) using real applicant CVs
from Google Drive 'Backend Developer - Sharing Happiness'.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx

API_BASE = "http://127.0.0.1:8111"
DATA_DIR = Path("/srv/hermes-control/services/cv-screening-agentic/data/real_cv_test/backend/Backend Developer - Sharing Happiness")

# Selected 5 representative real candidates
TEST_CANDIDATE_FILES = [
    "3605_Oki Iskandar_Oki-Iskandar-Resume.pdf",
    "3542_Umar Sabirin_Umar Sabirin - Resumes.pdf",
    "3534_Ihsan Zaky Fadillah_CV_IHSAN_ZAKY_FADILLAH.pdf",
    "3553_Denis Hanif Prasetya_CV_Denis-Hanif-Prasetya.pdf",
    "3531_Ahmad Habibul Ulum_CV_Ahmad Habibul Ulum_2025.pdf", # Scanned / no text layer test
]

JOB_TITLE = "Backend Developer - Sharing Happiness (Real Validation)"
JOB_DESCRIPTION = """Sharing Happiness adalah platform crowdfunding sosial dan filantropi digital terkemuka di Indonesia. Kami mencari Backend Developer yang bertanggung jawab merancang, mengembangkan, dan memelihara REST API performa tinggi, integrasi sistem pembayaran (payment gateway), manajemen basis data relasional (PostgreSQL/MySQL), serta arsitektur backend yang aman dan terukur.

Persyaratan Kualifikasi:
1. Pengalaman kerja minimal 2 tahun sebagai Backend Developer atau Software Engineer yang berfokus pada backend.
2. Menguasai minimal salah satu bahasa pemrograman backend: Golang, Python, PHP (Laravel), atau Node.js.
3. Mahir dalam perancangan REST API, arsitektur microservices/modular monolith, dan integrasi API pihak ketiga (misalnya payment gateway).
4. Mahir dalam pengelolaan basis data relasional (PostgreSQL atau MySQL), optimasi kueri SQL, dan integritas data transaksi.
5. Memahami prinsip clean code, unit testing, Git version control, dan keamanan aplikasi web (JWT, otorisasi, pencegahan SQL injection)."""


async def main():
    print("=" * 70)
    print("🎯 AGENTIC CV SCREENING v2.1 — REAL-WORLD CV VALIDATION RUN")
    print(f"Target: {JOB_TITLE}")
    print("=" * 70)

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
    async with httpx.AsyncClient(base_url=API_BASE, limits=limits, timeout=120.0) as client:
        # 1. Login Recruiter
        print("\n[Step 1] Authenticating recruiter...")
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"email": "recruiter@rifqisetiawan.my.id", "password": "RecruiterPassword2026!"},
        )
        if login_res.status_code != 200:
            print(f"❌ Login failed: {login_res.status_code} {login_res.text}")
            sys.exit(1)
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✓ Authenticated successfully.")

        # 2. Create Job Post
        print("\n[Step 2] Creating Job Post...")
        job_res = await client.post(
            "/api/v1/jobs",
            headers=headers,
            json={"title": JOB_TITLE, "jd_text": JOB_DESCRIPTION},
        )
        job_id = job_res.json()["id"]
        print(f"✓ Job created: ID = {job_id}")

        # 3. Compile RequirementIR (5 Facets)
        print("\n[Step 3] Compiling Job Description into Facet Decomposition (Graph B)...")
        comp_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/compile", headers=headers)
        if comp_res.status_code != 201:
            print(f"❌ Compile failed: {comp_res.status_code} {comp_res.text}")
            sys.exit(1)
        req_set = comp_res.json()
        print(f"✓ RequirementIR compiled: {len(req_set['requirements'])} facets generated:")
        for r in req_set["requirements"]:
            print(f"   • [{r['requirement_id']}] {r['category']} ({r['weight']}%): {r['description'][:75]}...")

        # 4. Approve Requirements
        appr_res = await client.post(f"/api/v1/jobs/{job_id}/requirements/approve", headers=headers)
        print(f"✓ Requirements approved: HTTP {appr_res.status_code}")

        # 5. Ingest Real Candidate CVs
        print(f"\n[Step 4] Uploading {len(TEST_CANDIDATE_FILES)} real applicant CVs...")
        upload_files = []
        file_handles = []
        for fname in TEST_CANDIDATE_FILES:
            fpath = DATA_DIR / fname
            if not fpath.exists():
                print(f"⚠️ Warning: File {fname} not found on disk, skipping.")
                continue
            fh = open(fpath, "rb")
            file_handles.append(fh)
            upload_files.append(("files", (fname, fh, "application/pdf")))

        try:
            up_res = await client.post(f"/api/v1/jobs/{job_id}/cvs", headers=headers, files=upload_files)
            print(f"✓ Upload accepted: HTTP {up_res.status_code}, total files: {up_res.json().get('total_files')}")
            uploaded_docs = up_res.json().get("files", [])
        finally:
            for fh in file_handles:
                fh.close()

        # 6. Wait for Graph A Ingestion to finish for all documents
        print("\n[Step 5] Processing Graph A (Visibility Gate, Atoms, Profiler Agent & Vector Embeddings)...")
        max_wait = 300  # 5 minutes
        start_wait = time.time()
        ready_docs = []
        rejected_docs = []

        while time.time() - start_wait < max_wait:
            status_res = await client.get(f"/api/v1/jobs/{job_id}/cvs/status", headers=headers)
            docs = status_res.json().get("documents", [])
            ready_docs = [d for d in docs if d["status"] == "READY"]
            rejected_docs = [d for d in docs if d["status"] in ("REJECTED", "NEEDS_REVIEW")]
            processing_docs = [d for d in docs if d["status"] in ("RECEIVED", "PROCESSING")]

            print(
                f"   ⏳ Ingestion Progress: {len(ready_docs)} READY, {len(rejected_docs)} REJECTED/FLAGGED, {len(processing_docs)} IN-PROGRESS...",
                end="\r",
            )

            if len(ready_docs) + len(rejected_docs) >= len(docs) and len(docs) > 0:
                print(f"\n✓ Ingestion completed! {len(ready_docs)} ready, {len(rejected_docs)} flagged/rejected.")
                break

            await asyncio.sleep(4.0)

        # 7. Trigger Graph B Screening Run
        print("\n[Step 6] Triggering Graph B Screening Run (Matcher, Temporal Union, Critic Claude Sonnet)...")
        run_res = await client.post(f"/api/v1/jobs/{job_id}/screenings", headers=headers)
        if run_res.status_code != 202:
            print(f"❌ Trigger screening failed: {run_res.status_code} {run_res.text}")
            sys.exit(1)
        run_id = run_res.json()["screening_run_id"]
        print(f"✓ Screening Run dispatched: ID = {run_id}")

        # 8. Wait for Screening Run to finish
        print("\n[Step 7] Running Multi-Model Reasoning & Scorer v2...")
        start_run = time.time()
        completed = False
        while time.time() - start_run < 360:
            r_res = await client.get(f"/api/v1/jobs/{job_id}/screenings/{run_id}/rankings", headers=headers)
            if r_res.status_code == 200:
                rankings_data = r_res.json()
                print(f"\n✓ Screening Run completed in {time.time() - start_run:.1f}s!")
                completed = True
                break
            elif r_res.status_code in (202, 404):
                print(f"   🧠 Model evaluation in progress ({int(time.time() - start_run)}s)...", end="\r")
            else:
                print(f"\n⚠️ Unexpected status: {r_res.status_code} {r_res.text}")
            await asyncio.sleep(4.0)

        if not completed:
            print("\n❌ Screening run timed out.")
            return

        # 9. Format and Print Validation Report
        print("\n" + "=" * 70)
        print("🏆 FINAL CANDIDATE RANKINGS & EVALUATION BREAKDOWN (v2.1)")
        print("=" * 70)

        candidates_list = rankings_data.get("candidates", [])
        if not candidates_list:
            print("No ranked candidates returned.")
            return

        for idx, c in enumerate(candidates_list, start=1):
            cand_id = c["candidate_id"]
            name = c.get("name", "Unknown")
            score = c.get("score_v2", c.get("score", 0.0))
            band = c.get("band", "N/A")
            headline = c.get("headline", "-")
            must_have = "LULUS" if c.get("must_have_passed", True) else "GAGAL"

            print(f"\n#{idx} {name} (Skor: {score:.1f} | Band: {band} | MUST_HAVE: {must_have})")
            print(f"   Headline: {headline}")

            # Fetch candidate detail for deep facet verification
            d_res = await client.get(f"/api/v1/jobs/{job_id}/screenings/{run_id}/candidates/{cand_id}", headers=headers)
            if d_res.status_code == 200:
                detail = d_res.json()
                facets = detail.get("facet_judgments", [])
                durations = detail.get("domain_durations", [])
                critic_reviews = detail.get("critic_reviews", [])

                if durations:
                    dur_str = ", ".join([f"{d['domain']}: {d.get('months_lo', 0)} bln" for d in durations])
                    print(f"   ⏱️ Calendar Union Tenures: {dur_str}")

                if facets:
                    print("   📋 Facet Evaluations:")
                    for f in facets[:4]:
                        v = f.get("verdict", "ABSENT")
                        dl = f.get("depth_level", "L0")
                        fdesc = f.get("description", f.get("facet_id", ""))[:45]
                        print(f"      • [{v} | {dl}] {fdesc}...")

                if critic_reviews:
                    print(f"   🛡️ Critic Audit Reviews ({len(critic_reviews)} facets checked):")
                    for cr in critic_reviews[:2]:
                        trig = cr.get("escalation_trigger", "-")
                        c_analysis = cr.get("analysis", "")[:60]
                        print(f"      • Trigger: {trig} | Action: {cr.get('action')} | {c_analysis}...")

        print("\n" + "=" * 70)
        print("✅ VALIDATION COMPLETED SUCCESSFULLY")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
