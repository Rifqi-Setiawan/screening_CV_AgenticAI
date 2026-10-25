"""Submits comprehensive CV extraction level-up prompt to Gemini 4 Argon (Thinking: High)
and saves the verbatim output to .txt.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

PROFILE_DIR = "/srv/hermes-control/services/video-automation/browser_profiles/account01"
OUTPUT_TXT = "/srv/hermes-control/services/cv-screening/docs/ARGON_EXTRACTION_LEVELUP_PLAN.txt"
OUTPUT_PNG = "/srv/hermes-control/services/cv-screening/docs/gemini_argon_plan_screenshot.png"

PROMPT = """Halo Gemini 4 Argon (Thinking Level: High).

Kami sedang membangun platform AI CV Screening & Candidate Ranking berpresisi tinggi level produksi (Live Demo: https://screening.rifqisetiawan.my.id, GitHub Repositories: https://github.com/Rifqi-Setiawan/ai-cv-screening-ranking dan https://github.com/Rifqi-Setiawan/CV_Extractor).

Saat ini kami ingin me-LEVEL UP secara radikal arsitektur pada fase ekstraksi dokumen ("EXTRACT STEP") agar mampu mencapai akurasi ekstraksi 98%+ pada data dunia nyata yang sangat kotor dan heterogen.

=== HASIL AUDIT EMPIRIS TERAKHIR PADA 59 BERKAS REAL-WORLD (PT Sharing Happiness, ISO, Raga Sport, Pilarcons Abadi) ===
Kami baru saja mengaudit 59 berkas asli pelamar kerja di 4 bidang (Backend Developer, Business Analyst, Civil Engineer, Digital Marketing):
1. Keberhasilan Sanitasi Non-Dokumen: Berkas CSV/metadata tabel ekspor ATS 100% tertolak bersih.
2. Keberhasilan OCR Dasar: Berkas scan murni 0-karakter berhasil di-fallback ke Tesseract OCR.
3. MASALAH UTAMA PADA EKSTRAKSI ENTITAS (Akurasi Nama hanya 74.5% - 14 dari 55 CV salah tangkap):
   - Pola 1: Headline Bias (Pelamar menulis jabatan 'Fullstack Developer', 'Backend Developer', atau 'Digital Marketing' di baris paling atas dengan font besar; parser salah mengiranya sebagai nama orang).
   - Pola 2: Institutional Header (Pelamar menulis nama kampus 'STMIK Dipanegara' atau 'Universitas Muhammadiyah' di pojok atas; parser mengiranya nama orang).
   - Pola 3: Merged Portfolio Bundling (Pelamar menggabungkan CV dengan portofolio, ijazah, transkrip, sertifikat hingga 10-19 halaman! Halaman 1 diawali judul seksi 'Tentang Saya' yang terbaca sebagai nama, dan proyek di halaman 15 terbaca sebagai riwayat pekerjaan purnawaktu).
   - Pola 4: Narrative Opening (Pelamar membuka CV dengan esai cerita: 'Fresh graduate... memiliki semangat belajar tinggi', yang terpotong menjadi nama).
   - Pola 5: Layout Multi-Kolom Canva & Reading Order (Teks kolom kiri dan kanan bertumpuk atau terpotong).
   - Pola 6: Format Tanggal Unstructured & Durasi Kerja (Bulan/tahun acak, singkatan lokal, format tanpa separator).

=== INSTRUKSI & PERMINTAAN TUGAS (TIDAK ADA BATASAN) ===
Kami ingin kamu (Gemini 4 Argon dengan penalaran mendalam) merancang MASTER ARCHITECTURE & ENGINEERING PLAN untuk merombak total modul ekstraksi dokumen ("EXTRACT STEP") kami.
Tidak ada batasan teknologi: kamu bebas mengusulkan Agentic AI multi-agent workflows, Vision-Language Models (VLM/Multimodal), Document Layout Analysis (DLA) mutakhir (seperti LayoutLMv3, Surya, Marker, Docling, ColPali), self-correcting verification loops, atau tech stack apapun yang paling superior.

Mohon berikan output dokumen rencana lengkap dalam format teks terstruktur (.txt) yang mencakup:
1. EXECUTIVE ARCHITECTURE OVERVIEW (Topologi sistem baru, arsitektur multi-tier dari parsing cepat hingga vision-agent).
2. DOCUMENT BOUNDARY ISOLATION & SEGMENTATION (Strategi cerdas memisahkan halaman CV inti [halaman 1-3] dari lampiran portofolio/sertifikat [halaman 4-19] agar tidak mencemari data riwayat kerja).
3. VISUAL & MULTIMODAL EXTRACTION PIPELINE (Penanganan layout 2-kolom Canva, grafik bintang/skill bar, font encoding rusak, dan scan dokumen).
4. ENTITY RESOLUTION & ANTI-BIAS VERIFICATION ENGINE (Mekanisme self-correction untuk mengeliminasi Headline Bias, eliminasi nama kampus di header, validasi silang nama dengan email, link LinkedIn, nomor HP, dan nama file).
5. WORK EXPERIENCE & EDUCATION PARSER (Normalisasi tanggal dinamis, kalkulasi durasi kerja presisi per bulan, ekstraksi tech stack kontekstual dari bullet point).
6. REKOMENDASI TECH STACK & INTEGRASI KODE (Tools open-source/model terbaik, estimasi latensi & biaya per CV, serta cara mengintegrasikannya ke repo FastAPI/Python kami).
7. BENCHMARK & EVALUATION CRITERIA (Cara menguji peningkatan dari 74.5% ke 98%+).

Tolong sajikan seluruh rencana ini secara mendalam, teknis, konkret, dan siap dieksekusi oleh tim engineering.
"""


def main():
    print("=" * 75)
    print("🚀 SUBMITTING MASTER LEVEL-UP PROMPT TO GEMINI 4 ARGON (THINKING: HIGH)")
    print("=" * 75)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR, headless=True, viewport={"width": 1280, "height": 950}
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)

        # Dismiss 'Let's go' modal if present
        lets_go = page.get_by_text("Let's go")
        if lets_go.count() > 0 and lets_go.is_visible():
            print("Dismissing 'Let's go' welcome screen...")
            lets_go.click()
            page.wait_for_timeout(1000)

        mode_btn = page.locator("button[aria-label*='mode picker'], button[aria-label*='pemilih mode']").first
        print("Model Button:", mode_btn.inner_text().strip().replace("\n", " "))

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
            thinking_item.hover()
            page.wait_for_timeout(1000)
            high = page.locator('gem-menu-item:has-text("High"), [role="menuitem"]:has-text("High")').first
            if high.is_visible():
                high.click()
                page.wait_for_timeout(1500)

        print("Active Model Confirmed:", mode_btn.inner_text().strip().replace("\n", " "))

        # Insert prompt
        print("Inserting full architectural prompt...")
        page.evaluate(
            """(text) => {
            const editor = document.querySelector('rich-textarea div[contenteditable="true"], div[role="textbox"]');
            if (editor) {
                editor.focus();
                document.execCommand('insertText', false, text);
            }
        }""",
            PROMPT,
        )
        page.wait_for_timeout(1500)

        send_btn = page.locator(
            'button[aria-label*="Send"], button[aria-label*="Kirim"], button.send-button'
        ).first
        print(f"Send Button: visible={send_btn.is_visible()}, enabled={send_btn.is_enabled()}")

        if not (send_btn.is_visible() and send_btn.is_enabled()):
            print("❌ Cannot send prompt: Send button is disabled or not visible.")
            ctx.close()
            sys.exit(1)

        send_btn.click()
        print("📨 Prompt sent successfully! Waiting for Gemini 4 Argon deep reasoning...")

        # Deep thinking monitor loop
        t0 = time.time()
        max_wait_seconds = 300
        while time.time() - t0 < max_wait_seconds:
            page.wait_for_timeout(5000)
            elapsed = time.time() - t0

            stop_btn = page.locator('button[aria-label*="Stop"], button[aria-label*="Berhenti"]').first
            is_generating = stop_btn.is_visible() if stop_btn.count() > 0 else False

            responses = page.locator(".model-response-text, message-content, .response-container").all()
            print(f"  ⏳ [{elapsed:4.1f}s] Argon Thinking / Generating: {is_generating} (Blocks: {len(responses)})")

            if not is_generating and len(responses) > 0 and elapsed > 20.0:
                print(f"🎉 Gemini 4 Argon generation finished in {elapsed:.1f}s!")
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

        # Save to TXT
        os.makedirs(os.path.dirname(OUTPUT_TXT), exist_ok=True)
        with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
            f.write(full_text)

        print(f"\n✅ Full Plan saved to: {OUTPUT_TXT} ({len(full_text)} characters, {len(full_text.split())} words)")

        # Capture Screenshot
        page.screenshot(path=OUTPUT_PNG, full_page=False)
        print(f"📸 Screenshot saved to: {OUTPUT_PNG}")

        ctx.close()


if __name__ == "__main__":
    main()
