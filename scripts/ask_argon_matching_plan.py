#!/usr/bin/env python3
"""
Submits comprehensive CV-to-Requirement Matching & Retrieval Level-up prompt
to Gemini 4 Argon (Thinking: High) and saves the verbatim output to .txt and .png.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

PROFILE_DIR = "/srv/hermes-control/services/video-automation/browser_profiles/account03"
OUTPUT_TXT = "/srv/hermes-control/services/cv-screening/docs/ARGON_MATCHING_LEVELUP_PLAN.txt"
OUTPUT_PNG = "/srv/hermes-control/services/cv-screening/docs/gemini_argon_matching_plan_screenshot.png"

PROMPT = """Halo Gemini 4 Argon (Thinking Level: High).

Kami sedang mengembangkan platform AI CV Screening & Candidate Ranking level produksi (GitHub: https://github.com/Rifqi-Setiawan/ai-cv-screening-ranking, Web: https://screening.rifqisetiawan.my.id).

Saat ini kami menghadapi masalah mendasar yang sangat krusial pada fase pencocokan bukti kualifikasi ("MATCHING & EVIDENCE RETRIEVAL ENGINE"):
"Banyak pengalaman kerja di CV yang sebenarnya secara nyata memenuhi kualifikasi lowongan kerja (JD), namun sistem mendeteksinya TIDAK ADA / MISS (False Negative), sehingga kandidat yang kompeten mendapat status NOT_DEMONSTRATED dan skornya jatuh ke Band C."

=== ANALISIS ANATOMI MASALAH SAAT INI (GEJALA EMPIRIS DI LAPANGAN) ===
1. Lexical & Vocabulary Mismatch (Kesenjangan Parafrasa Bahasa):
   - Pelamar dan pembuat JD menggunakan kosakata yang berbeda untuk esensi pekerjaan yang sama.
   - Contoh nyata:
     * CV Pelamar menulis: "Mengajar materi tahfidz, fiqih ibadah, dan akidah akhlak untuk kelas 7-9 SMP".
       JD Kualifikasi menulis: "Mampu menyampaikan dan mengimplementasikan kurikulum Pendidikan Agama Islam".
       -> Sistem gagal mencocokkan karena kata "kurikulum pendidikan agama Islam" tidak mengandung kata "tahfidz" atau "fiqih" secara harfiah.
     * CV Pelamar menulis: "Merancang skema tabel, optimasi query relasional, dan migrasi basis data pelanggan".
       JD Kualifikasi menulis: "Database Administration & Architecture".
       -> Sistem mendeteksi NOT_DEMONSTRATED karena tidak menemukan kata "administrator" atau "database administration".
2. Kerapuhan Rule-Based Gating & Keyword Over-Reliance:
   - Mesin evaluasi kami (kind_rules.py: eval_responsibility, eval_skill) memiliki pohon kata kunci statis (skills.yaml) yang awalnya dioptimalkan untuk Software Engineer (misal: "rest api", "microservices", "docker").
   - Ketika lowongan berganti ke bidang lain (Pendidikan/Guru, Bisnis, Legal, Civil Engineer, Digital Marketing, dsb.), aturan regex statis kehilangan daya tangkapnya karena variasinya miliaran di dunia nyata.
3. Granularitas Chunking & Kehilangan Konteks (Context Loss):
   - Pengalaman kerja dipotong per baris bullet terpisah saat dievaluasi. Akibatnya, kalimat pelamar kehilangan konteks jabatan (Job Title) dan konteks industri perusahaan tempat dia bekerja saat di-embed ke vektor pgvector (Harrier-270m 640d).
4. Dual-Tower Semantic Search yang Belum Terkalibrasi Maksimal:
   - Saat ini sistem berada pada SCORING_MODE="rules" dengan threshold kosinus statis. Dense vector search sering kali menghasilkan skor kemiripan 0.55 - 0.64 (di bawah threshold 0.65) karena perbedaan panjang kalimat antara butir kualifikasi JD dengan bullet point CV yang sangat padat.
5. Ketiadaan Natural Language Inference (NLI) / Entailment Verifier:
   - Sistem belum memiliki evaluator inferensi semantik: "Apakah teks bukti E secara logis menyimpulkan/membuktikan (entails) kriteria K?".

=== PERMINTAAN TUGAS UNTUK GEMINI 4 ARGON (DEEP THINKING: HIGH) ===
Kami meminta kamu merancang MASTER ARCHITECTURE & ENGINEERING PLAN untuk merombak total modul MATCHING & EVIDENCE RETRIEVAL ENGINE kami.
Fokus utama: Mengeliminasi False Negatives tanpa membuka celah False Positives (akurasi dan presisi tinggi), tetap transparan, auditable, dan deterministik.

Mohon sajikan rencana arsitektur mendalam dalam format terstruktur yang mencakup:
1. EXECUTIVE DIAGNOSIS (Mengapa sistem ATS modern sering gagal mengenali pengalaman relevan, dan prinsip arsitektur komputasional untuk menyelesaikannya).
2. HIERARCHICAL CONTEXTUAL CHUNKING & DOCUMENT REPRESENTATION (Cara memformat dan meng-chunk pengalaman kerja CV agar jabatan, perusahaan, durasi, dan aksi/tanggung jawab tetap utuh dalam satu konteks semantik yang kaya).
3. MULTI-TIER RETRIEVAL & SEMANTIC EXPANSION PIPELINE:
   - Tier 1: Dynamic Query Expansion & Domain Taxonomy Generation (menjembatani kesenjangan kosakata istilah kerja).
   - Tier 2: Calibrated Hybrid Search (penyelarasan dense vector pgvector Harrier-270m dengan sparse lexical BM25/FTS + Reciprocal Rank Fusion yang optimal).
   - Tier 3: Cross-Encoder / Cross-Attention Re-Ranking untuk penilaian pasangan (Requirement, Experience Candidate).
4. ENTAILMENT-BASED STATE CLASSIFICATION (Mengubah evaluasi kriteria menjadi relasi Natural Language Inference: ENTAILMENT -> STRONG, NEUTRAL/PARTIAL -> PARTIAL, CONTRADICTION/ABSENT -> NOT_DEMONSTRATED).
5. DETERMINISTIC EVIDENCE EXTRACTION & PROVENANCE ANCHORING (Cara mengambil kutipan kalimat asli CV yang paling tepat sebagai bukti transparan yang ditampilkan di dashboard HR, lengkap dengan confidence score).
6. PRODUCTION IMPLEMENTATION ROADMAP & TECH STACK (Model/library Python open-source yang efisien di CPU/GPU VPS, estimasi latensi per kandidat, dan integrasi arsitektur ke pipeline FastAPI kami).
7. BENCHMARKING & VALIDATION PROTOCOL (Dataset sintetis & riil, metrik Precision, Recall, F1, nDCG, dan confusion matrix untuk menguji eliminasi miss).

Sajikan dokumen ini secara sangat teknis, komprehensif, dan matematis/algoritmik agar dapat langsung kami terapkan ke dalam repositori kami.
"""


def main():
    print("=" * 75)
    print("🚀 CONSULTING GEMINI 4 ARGON (THINKING: HIGH) FOR MATCHING ENGINE PLAN")
    print("=" * 75)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR, headless=True, viewport={"width": 1280, "height": 950}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)

        # Dismiss modal if present
        lets_go = page.get_by_text("Let's go")
        if lets_go.count() > 0 and lets_go.is_visible():
            print("Dismissing 'Let's go' welcome screen...")
            lets_go.click()
            page.wait_for_timeout(1000)

        mode_btn = page.locator("button[aria-label*='mode picker'], button[aria-label*='pemilih mode']").first
        if mode_btn.count() > 0:
            print("Current Model Button:", mode_btn.inner_text().strip().replace("\n", " "))

            # Ensure Argon High
            if "Argon" not in mode_btn.inner_text() or "High" not in mode_btn.inner_text():
                mode_btn.click()
                page.wait_for_timeout(1000)
                argon_item = page.locator(
                    'gem-menu-item:has-text("4 Argon"), [role="menuitem"]:has-text("4 Argon")'
                ).first
                if argon_item.is_visible():
                    argon_item.click()
                    page.wait_for_timeout(1500)
                mode_btn.click()
                page.wait_for_timeout(1000)
                thinking_item = page.locator(
                    'gem-menu-item:has-text("Thinking level"), [role="menuitem"]:has-text("Thinking level")'
                ).first
                if thinking_item.is_visible():
                    thinking_item.hover()
                    page.wait_for_timeout(1000)
                    high = page.locator('gem-menu-item:has-text("High"), [role="menuitem"]:has-text("High")').first
                    if high.is_visible():
                        high.click()
                        page.wait_for_timeout(1500)

        # Insert prompt via native keyboard input
        print("Inserting detailed Matching Engine prompt via native keyboard...", flush=True)
        editor = page.locator('div[role="textbox"]').first
        editor.click()
        page.wait_for_timeout(500)
        page.keyboard.insert_text(PROMPT)
        page.wait_for_timeout(1500)

        send_btn = page.locator(
            'button[aria-label*="Send"], button[aria-label*="Kirim"], button.send-button'
        ).first
        print(f"Send Button: visible={send_btn.is_visible()}, enabled={send_btn.is_enabled()}", flush=True)

        if not (send_btn.is_visible() and send_btn.is_enabled()):
            print("❌ Cannot send prompt: Send button is disabled or not visible.", flush=True)
            ctx.close()
            sys.exit(1)

        send_btn.click()
        print("📨 Prompt sent! Waiting for Gemini 4 Argon deep thinking...", flush=True)

        # Monitor loop
        t0 = time.time()
        max_wait_seconds = 300
        while time.time() - t0 < max_wait_seconds:
            page.wait_for_timeout(5000)
            elapsed = time.time() - t0

            stop_btn = page.locator('button[aria-label*="Stop"], button[aria-label*="Berhenti"]').first
            is_generating = stop_btn.is_visible() if stop_btn.count() > 0 else False

            responses = page.locator(".model-response-text, message-content, .response-container").all()
            print(f"  ⏳ [{elapsed:4.1f}s] Argon Thinking: is_generating={is_generating} (Blocks: {len(responses)})")

            if not is_generating and len(responses) > 0 and elapsed > 25.0:
                print(f"🎉 Gemini 4 Argon completed reasoning in {elapsed:.1f}s!")
                break

        page.wait_for_timeout(3000)

        # Extract complete response
        resp_elements = page.locator(".model-response-text, message-content").all()
        if not resp_elements:
            resp_elements = page.locator(".response-container").all()

        full_text = ""
        if resp_elements:
            full_text = resp_elements[-1].inner_text()
        else:
            full_text = "NO_RESPONSE_CAPTURED"

        os.makedirs(os.path.dirname(OUTPUT_TXT), exist_ok=True)
        with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
            f.write(full_text)

        print(f"\n✅ Full Plan saved to: {OUTPUT_TXT} ({len(full_text)} characters, {len(full_text.split())} words)")

        page.screenshot(path=OUTPUT_PNG, full_page=False)
        print(f"📸 Screenshot saved to: {OUTPUT_PNG}")

        ctx.close()


if __name__ == "__main__":
    main()
