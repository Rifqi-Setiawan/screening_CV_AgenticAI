"""Playwright end-to-end tests for CV Screening Frontend UI Flow (M5)."""

from __future__ import annotations

import http.server
import socketserver
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

DIST_DIR = Path("frontend/dist").resolve()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def log_message(self, format, *args):
        pass  # Quiet logs

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.proxy_request()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.proxy_request()
        else:
            super().do_POST()

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            self.proxy_request()
        else:
            super().do_DELETE()

    def do_OPTIONS(self):
        if self.path.startswith("/api/"):
            self.proxy_request()
        else:
            super().do_OPTIONS()

    def proxy_request(self):
        target_url = f"http://127.0.0.1:8110{self.path}"
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len > 0 else None

        req = urllib.request.Request(target_url, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in ("host", "content-length"):
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for hk, hv in resp.getheaders():
                    self.send_header(hk, hv)
                self.end_headers()
                self.wfile.write(resp.read())
        except urllib.error.HTTPError as err:
            self.send_response(err.code)
            for hk, hv in err.headers.items():
                self.send_header(hk, hv)
            self.end_headers()
            self.wfile.write(err.read())
        except Exception:
            self.send_response(502)
            self.end_headers()


@pytest.fixture(scope="module")
def static_server():
    socketserver.TCPServer.allow_reuse_address = True
    server = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


def test_main_ui_flow_and_text_checks(static_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 768})

        # 1. Open SPA
        page.goto(static_server)
        page.wait_for_selector("text=AI CV Screening & Ranking")
        assert "AI CV Screening" in page.title() or page.is_visible("text=AI CV Screening & Ranking")

        # Text audit requirement: Ensure no "Reject" or "tidak menguasai" in rendered content
        full_page_text = page.inner_text("body")
        assert "tidak menguasai" not in full_page_text.lower(), "Forbidden text 'tidak menguasai' found in UI!"
        assert "reject" not in full_page_text.lower(), "Forbidden word 'Reject' found in UI!"

        # 2. Screen 1: Setup Lowongan
        assert page.is_visible("text=Setup Lowongan Kerja")
        assert page.is_visible("text=Senior Backend Engineer")
        if page.is_visible("text=Ekstrak Kriteria & Lanjut"):
            page.click("text=Ekstrak Kriteria & Lanjut")
        else:
            page.click("text=Lanjut ke Peninjauan Kriteria")

        # 3. Screen 1b: Tinjau & Setujui Kriteria
        page.wait_for_selector("text=Tinjau & Setujui Kriteria Lowongan", timeout=120000)
        assert page.is_visible("text=Distribusi Kategori:")
        assert page.is_visible("text=R1")
        assert page.is_visible("text=R2")

        # Verify add manual requirement
        page.fill("input[placeholder*='Tambah kriteria manual']", "Pengalaman arsitektur CQRS")
        page.click("text=Tambah Kriteria Manual")
        page.wait_for_selector("input[value='Pengalaman arsitektur CQRS']")

        # Approve the criteria to unlock screening gate (FX-03)
        if page.is_visible("text=Setujui Kriteria (Kunci Versi)"):
            page.click("text=Setujui Kriteria (Kunci Versi)")
            page.wait_for_timeout(500)

        # Navigate to Screen 2: Upload CV
        page.click("text=Lanjut ke Upload CV")

        # 4. Screen 2: Upload CV
        page.wait_for_selector("text=Upload CV Pelamar")
        assert page.is_visible("text=Tarik berkas CV ke sini")
        # Load sample golden dataset files if table starts clean
        if page.is_visible("text=Muat 15 Sampel Golden Dataset"):
            page.click("text=Muat 15 Sampel Golden Dataset")
            page.wait_for_timeout(500)
        assert page.is_visible("text=S1_senior_backend_id.pdf")
        assert page.is_visible("text=E1_empty_cv.pdf")
        assert page.is_visible("text=Perlu Cek Manual")

        # Navigate to Screen 3: Leaderboard
        page.click("text=Mulai Screening & Buka Leaderboard")

        # 5. Screen 3: Leaderboard
        page.wait_for_selector("text=Run Selesai", timeout=120000)
        assert page.is_visible("text=Semua Wajib Terbukti (A)")

        # Verify Blind mode display
        assert page.is_visible("text=C-0001")
        assert page.is_visible("text=C-0002")

        # Check candidate ranking #1
        first_row = page.locator("tbody tr").first
        assert "C-0001" in first_row.inner_text()
        assert "S1_senior_backend_id.pdf" in first_row.inner_text()

        # 6. Screen 4: Open Candidate Detail Drawer
        first_row.click()
        page.wait_for_selector("text=Kelebihan Terbukti di CV")
        page.wait_for_selector("text=Belum Terbukti di CV")
        page.wait_for_selector("text=Saran Pertanyaan Wawancara Mendalam")

        # Switch to Kartu Skor Tab
        page.click("text=2. Kartu Skor Kriteria")
        page.wait_for_selector("text=Terbukti")

        # Switch to Berkas CV & Kutipan Tab
        page.click("text=3. Berkas CV & Kutipan")
        page.wait_for_selector("text=Penampil Teks Asli Berkas")

        # Close Drawer
        page.click("button:has-text('✕')")

        # 7. Compare Modal
        checkboxes = page.locator("tbody input[type='checkbox']")
        checkboxes.nth(0).click()
        checkboxes.nth(1).click()

        page.click("button:has-text('Bandingkan (2)')")
        page.wait_for_selector("text=Perbandingan Kandidat Berdampingan")
        assert page.is_visible("text=C-0001")
        assert page.is_visible("text=C-0002")
        page.click("button:has-text('Tutup')")

        # 8. Export Modal
        page.click("button:has-text('Export Laporan')")
        page.wait_for_selector("text=Export Laporan Pemeringkatan")
        assert page.is_visible("text=Excel (.XLSX)")
        page.click("button:has-text('Batal')")

        browser.close()


def test_file_input_and_upload_dropzone(static_server):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 768})

        page.goto(static_server)
        page.wait_for_selector("text=AI CV Screening & Ranking")

        # Navigate to Screen 2
        page.click("text=Ekstrak Kriteria & Lanjut")
        page.wait_for_selector("text=Tinjau & Setujui Kriteria Lowongan", timeout=120000)
        page.click("text=Lanjut ke Upload CV")
        page.wait_for_selector("text=Upload CV Pelamar")

        # Verify input[type='file'] element exists
        file_input = page.locator("input[type='file']")
        assert file_input.count() == 1
        assert ".pdf" in file_input.get_attribute("accept")

        # Set file input with test PDF
        test_pdf = Path("docs/spec/golden_dataset/cvs/core/S1_senior_backend_id.pdf").resolve()
        assert test_pdf.exists()
        file_input.set_input_files(str(test_pdf))

        # Verify dropzone responds to file selection
        page.wait_for_timeout(500)
        assert page.is_visible("text=S1_senior_backend_id.pdf")

        browser.close()
