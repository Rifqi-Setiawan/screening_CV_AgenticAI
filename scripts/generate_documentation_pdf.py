import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML_CONTENT = """<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<title>Buku Panduan Arsitektur & Penggunaan: AI CV Screening & Ranking Platform</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

  :root {
    --primary: #0284c7;
    --primary-dark: #0369a1;
    --primary-light: #e0f2fe;
    --slate-900: #0f172a;
    --slate-800: #1e293b;
    --slate-700: #334155;
    --slate-600: #475569;
    --slate-500: #64748b;
    --slate-300: #cbd5e1;
    --slate-200: #e2e8f0;
    --slate-100: #f1f5f9;
    --slate-50: #f8fafc;
    --emerald-600: #059669;
    --emerald-50: #ecfdf5;
    --amber-600: #d97706;
    --amber-50: #fffbeb;
    --rose-600: #e11d48;
    --rose-50: #fff1f2;
    --indigo-600: #4f46e5;
    --indigo-50: #eef2ff;
  }

  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: var(--slate-800);
    background: #ffffff;
    line-height: 1.6;
    font-size: 9.5pt;
  }

  /* Page Setup for Print */
  @page {
    size: A4;
    margin: 20mm 15mm 20mm 15mm;
  }

  .page-break {
    page-break-before: always;
  }

  .avoid-break {
    page-break-inside: avoid;
  }

  /* Typography */
  h1, h2, h3, h4 {
    color: var(--slate-900);
    font-weight: 700;
    line-height: 1.25;
  }

  h1 { font-size: 20pt; margin-bottom: 8pt; }
  h2 { font-size: 13.5pt; margin-top: 16pt; margin-bottom: 8pt; padding-bottom: 4pt; border-bottom: 1.5pt solid var(--slate-200); }
  h3 { font-size: 11pt; margin-top: 12pt; margin-bottom: 6pt; color: var(--primary-dark); }
  h4 { font-size: 9.5pt; margin-top: 8pt; margin-bottom: 4pt; color: var(--slate-700); }
  p { margin-bottom: 7pt; text-align: justify; }

  /* Cover Page */
  .cover {
    min-height: 88vh;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 35pt 20pt 20pt 20pt;
    border: 1pt solid var(--slate-200);
    border-radius: 8pt;
    background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  }

  .cover-badge {
    display: inline-block;
    padding: 4pt 12pt;
    background: var(--indigo-50);
    color: var(--indigo-600);
    font-size: 8pt;
    font-weight: 700;
    border-radius: 9999px;
    border: 1pt solid #c7d2fe;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 14pt;
  }

  .cover-title {
    font-size: 25pt;
    font-weight: 800;
    color: var(--slate-900);
    line-height: 1.15;
    margin-bottom: 10pt;
  }

  .cover-subtitle {
    font-size: 11pt;
    color: var(--slate-600);
    font-weight: 400;
    max-width: 90%;
    margin-bottom: 20pt;
    line-height: 1.5;
  }

  .cover-meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10pt;
    padding: 14pt;
    background: #ffffff;
    border: 1pt solid var(--slate-200);
    border-radius: 6pt;
  }

  .meta-item {
    font-size: 8pt;
  }
  .meta-label {
    color: var(--slate-500);
    font-weight: 500;
    text-transform: uppercase;
    font-size: 7pt;
    letter-spacing: 0.05em;
  }
  .meta-value {
    color: var(--slate-900);
    font-weight: 700;
    margin-top: 2pt;
  }

  /* Content Elements */
  .callout {
    padding: 9pt 12pt;
    border-radius: 6pt;
    margin: 8pt 0;
    font-size: 8.5pt;
  }
  .callout-info {
    background: var(--indigo-50);
    border-left: 3pt solid var(--indigo-600);
    color: #1e1b4b;
  }
  .callout-success {
    background: var(--emerald-50);
    border-left: 3pt solid var(--emerald-600);
    color: #064e3b;
  }
  .callout-warning {
    background: var(--amber-50);
    border-left: 3pt solid var(--amber-600);
    color: #78350f;
  }

  /* Tables */
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 8pt 0;
    font-size: 8pt;
  }
  th, td {
    padding: 5.5pt 7pt;
    border: 1pt solid var(--slate-200);
    text-align: left;
    vertical-align: top;
  }
  th {
    background: var(--slate-100);
    color: var(--slate-900);
    font-weight: 700;
  }
  tr:nth-child(even) td {
    background: var(--slate-50);
  }

  /* Code Blocks */
  code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 7.5pt;
    background: var(--slate-100);
    padding: 1.5pt 3pt;
    border-radius: 3pt;
    color: #0f172a;
    border: 0.5pt solid var(--slate-200);
  }

  pre {
    background: #0f172a;
    color: #f8fafc;
    padding: 8pt 10pt;
    border-radius: 6pt;
    font-family: 'JetBrains Mono', monospace;
    font-size: 7pt;
    line-height: 1.4;
    margin: 6pt 0;
    overflow-x: auto;
  }
  pre code {
    background: transparent;
    padding: 0;
    border: none;
    color: #f8fafc;
  }

  /* Badges */
  .badge {
    display: inline-block;
    padding: 1.5pt 5pt;
    font-size: 6.5pt;
    font-weight: 700;
    border-radius: 3pt;
    text-transform: uppercase;
  }
  .badge-emerald { background: #d1fae5; color: #065f46; border: 0.5pt solid #a7f3d0; }
  .badge-amber { background: #fef3c7; color: #92400e; border: 0.5pt solid #fde68a; }
  .badge-purple { background: #f3e8ff; color: #6b21a8; border: 0.5pt solid #e9d5ff; }
  .badge-slate { background: #f1f5f9; color: #334155; border: 0.5pt solid #cbd5e1; }

  /* Structured Visual Architecture Diagram */
  .arch-container {
    background: #0f172a;
    border: 1pt solid var(--slate-700);
    border-radius: 8pt;
    padding: 12pt;
    margin: 10pt 0;
    color: #f8fafc;
  }

  .arch-layer {
    background: #1e293b;
    border: 1pt solid #334155;
    border-radius: 6pt;
    padding: 8pt 10pt;
    margin-bottom: 8pt;
  }

  .arch-layer-title {
    font-size: 8pt;
    font-weight: 700;
    color: #38bdf8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4pt;
    display: flex;
    justify-content: space-between;
  }

  .arch-layer-desc {
    font-size: 7pt;
    color: #cbd5e1;
    line-height: 1.4;
  }

  .arch-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8pt;
  }

  .arch-arrow {
    text-align: center;
    color: #94a3b8;
    font-size: 9pt;
    margin: -3pt 0 4pt 0;
  }

  ul, ol {
    margin-left: 14pt;
    margin-bottom: 6pt;
  }
  li {
    margin-bottom: 2pt;
  }

  .step-card {
    border: 1pt solid var(--slate-200);
    border-radius: 6pt;
    padding: 8pt 10pt;
    margin-bottom: 6pt;
    background: #ffffff;
  }
  .step-num {
    display: inline-block;
    width: 16pt;
    height: 16pt;
    line-height: 16pt;
    text-align: center;
    background: var(--primary);
    color: #ffffff;
    font-weight: 800;
    border-radius: 50%;
    font-size: 7.5pt;
    margin-right: 5pt;
  }
</style>
</head>
<body>

<!-- ============================================================== -->
<!-- COVER PAGE                                                     -->
<!-- ============================================================== -->
<div class="cover avoid-break">
  <div>
    <span class="cover-badge">Buku Panduan Teknis & Penggunaan Resmi</span>
    <h1 class="cover-title">AI CV Screening &<br>Ranking Platform</h1>
    <p class="cover-subtitle">
      Arsitektur Sistem, Engine Penilaian Deterministik, Tata Kelola Privasi Blind-Mode, dan Petunjuk Operasional Rekrutmen Berpresisi Tinggi.
    </p>

    <div style="margin: 16pt 0; border-top: 2.5pt solid var(--primary); width: 50pt;"></div>

    <p style="font-size: 8.5pt; color: var(--slate-600); max-width: 90%;">
      Dokumen ini dirancang sebagai panduan komprehensif bagi Software Engineer, HR Specialist, Compliance Officer, dan System Administrator untuk memahami arsitektur internal, mekanisme penilaian bebas bias, serta alur pengoperasian platform dari awal hingga akhir.
    </p>
  </div>

  <div class="cover-meta-grid">
    <div class="meta-item">
      <div class="meta-label">Versi Dokumen</div>
      <div class="meta-value">v2.1 (Production Release)</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Basis Status Audit</div>
      <div class="meta-value">Fase 1 s/d 5 Selesai (Ronde 1 Remidiasi)</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Domain Publik</div>
      <div class="meta-value">screening.rifqisetiawan.my.id</div>
    </div>
    <div class="meta-item">
      <div class="meta-label">Arsitek & Pengembang</div>
      <div class="meta-value">Muhammad Rifqi Setiawan</div>
    </div>
  </div>
</div>

<div class="page-break"></div>

<!-- ============================================================== -->
<!-- BAB 1: RINGKASAN EKSEKUTIF & FILOSOFI DESAIN                   -->
<!-- ============================================================== -->
<h2>1. Ringkasan Eksekutif & Filosofi Desain</h2>

<p>
  <strong>AI CV Screening & Ranking Platform</strong> adalah sistem rekrutmen generasi modern berpresisi tinggi yang mengotomatisasi penyaringan berkas Curriculum Vitae (CV) dalam skala ratusan hingga ribuan secara objektif, akuntabel, dan bebas bias subjektif. Platform ini dikembangkan untuk mengatasi kegagalan struktural pada sistem Applicant Tracking System (ATS) konvensional dan platform berbasis LLM generatif murni.
</p>

<div class="callout callout-warning avoid-break">
  <strong>Kegagalan Struktural Solusi Rekrutmen Tradisional:</strong>
  <ul style="margin-top: 3pt; margin-bottom: 0;">
    <li><strong>ATS Keyword-Matching:</strong> Rentan terhadap manipulasi (seperti <em>white-font keyword stuffing</em>) dan gagal menangkap makna semantik atau kedalaman pengalaman kerja riil.</li>
    <li><strong>LLM Scoring Halusinasi:</strong> Sistem yang meminta AI generatif mengeluarkan angka langsung ("Beri skor CV ini 1-100") menghasilkan skor acak yang tidak deterministik, tidak dapat direproduksi, dan melanggar prinsip transparansi audit.</li>
    <li><strong>Bias Demografis & Diskriminasi Otomatis:</strong> Seringkali kandidat berkompetensi tinggi tersingkir secara otomatis di awal karena filter usia, gender, almamater, atau foto diri.</li>
  </ul>
</div>

<h3>Tiga Pilar Fondasi Arsitektur</h3>
<ol>
  <li>
    <strong>Deterministic Code-Level Scoring:</strong>
    Skor kelulusan (0–100) dan penentuan peringkat (Ranking) <em>100% dihitung oleh kode program matematis deterministik</em> (bukan tebakan probabilitas LLM). Rumus, bobot kategori, dan batas capping bersifat deterministik dan dapat diaudit hingga tingkat persamaan aljabar.
  </li>
  <li>
    <strong>Zero-PII Blind Screening:</strong>
    Seluruh data identitas pribadi (Nama, Kontak, Alamat, Foto, Usia, Gender, Agama) diredaksikan sebelum masuk ke pipeline evaluasi. Sistem menyajikan identitas kandidat dalam kode acak (misal: <code>C-0001</code>) demi mencegah <em>unconscious bias</em> reviewer.
  </li>
  <li>
    <strong>Administrative Eligibility Gate (Human-in-the-Loop):</strong>
    Kriteria administratif seperti batasan usia atau gender dipisahkan mutlak dari skor kompetensi sesuai amanat <strong>SE Menaker M/6/HK.04/V/2025</strong> dan <strong>UU Perlindungan Data Pribadi (UU PDP)</strong>. Tidak ada penolakan otomatis oleh sistem; status hanya ditampilkan sebagai badge transparansi bagi HR.
  </li>
</ol>

<h3>Matriks Komparasi Pendekatan Rekrutmen</h3>
<table class="avoid-break">
  <thead>
    <tr>
      <th style="width: 22%;">Dimensi Evaluasi</th>
      <th style="width: 26%;">ATS Konvensional</th>
      <th style="width: 26%;">Platform LLM Murni</th>
      <th style="width: 26%;">Platform Ini (Deterministik)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Metode Penilaian</strong></td>
      <td>Pencocokan kata kunci mentah (exact keyword frequency)</td>
      <td>Probabilitas token LLM ("Beri skor 1-100")</td>
      <td><strong>Perhitungan Aljabar Kode Deterministik</strong></td>
    </tr>
    <tr>
      <td><strong>Verifikasi Bukti</strong></td>
      <td>Tidak ada (hanya frekuensi kata)</td>
      <td>Bisa berhalusinasi mengarang kutipan</td>
      <td><strong>Code-Grounded: Kutipan wajib ada kata-demi-kata</strong></td>
    </tr>
    <tr>
      <td><strong>Perlindungan Privasi</strong></td>
      <td>Data PII terlihat penuh oleh reviewer</td>
      <td>Risiko kebocoran CV utuh ke API pihak ketiga</td>
      <td><strong>Blind Mode & Enkripsi Database (pgcrypto)</strong></td>
    </tr>
    <tr>
      <td><strong>Filter Usia & Gender</strong></td>
      <td>Gugur otomatis tanpa audit trail</td>
      <td>Bias implisit dari pelatihan model LLM</td>
      <td><strong>Eligibility Gate Terpisah (Human-in-the-Loop)</strong></td>
    </tr>
    <tr>
      <td><strong>Kepatuhan Hukum</strong></td>
      <td>Rentan pelanggaran SE Menaker 2025</td>
      <td>Melanggar UU PDP (Automated Decision)</td>
      <td><strong>Kontrol Kepatuhan SE Menaker M/6/2025 & UU PDP No. 27/2022</strong></td>
    </tr>
  </tbody>
</table>

<div class="page-break"></div>

<!-- ============================================================== -->
<!-- BAB 2: TECH STACK & ARSITEKTUR TEKNIS                          -->
<!-- ============================================================== -->
<h2>2. Tech Stack & Arsitektur Sistem</h2>

<p>
  Platform ini dirancang dengan standar arsitektur monolitik modular berperforma tinggi, mengombinasikan kecepatan komputasi vektor lokal, isolasi multi-tenant, serta konsumsi sumber daya RAM/CPU yang sangat efisien.
</p>

<table>
  <thead>
    <tr>
      <th style="width: 22%;">Lapisan</th>
      <th style="width: 38%;">Komponen & Teknologi</th>
      <th style="width: 40%;">Peran & Karakteristik</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Frontend Web</strong></td>
      <td>React 18, TypeScript, Vite, Tailwind CSS, Lucide Icons</td>
      <td>SPA reaktif, visualisasi leaderboard real-time, linter kriteria JD, drawer detail kandidat, dan kartu skor.</td>
    </tr>
    <tr>
      <td><strong>Backend API</strong></td>
      <td>Python 3.12, FastAPI, Uvicorn (2 workers)</td>
      <td>REST API asinkron non-blocking, proxy-headers support, RBAC token JWT, dan validasi fail-fast Pydantic v2.</td>
    </tr>
    <tr>
      <td><strong>Database & Vector</strong></td>
      <td>PostgreSQL 16, <code>pgvector</code> 0.8.7, <code>pgcrypto</code></td>
      <td>Penyimpanan relasional ACID, embedding vektor 640-dimensi dengan indeks HNSW cosine, dan enkripsi PII identitas.</td>
    </tr>
    <tr>
      <td><strong>Database Migrations</strong></td>
      <td>Alembic (SQLAlchemy driver psycopg)</td>
      <td>Manajemen evolusi skema database terkontrol dan aman tanpa downtime (menggantikan skrip destruktif <code>migrate.sh</code>).</td>
    </tr>
    <tr>
      <td><strong>Background Worker</strong></td>
      <td>Python Async Worker, Systemd Service</td>
      <td>Pemrosesan dokumen asinkron lewat antrean database <code>jobs_queue</code> dengan recovery tugas macet dan auto-retry.</td>
    </tr>
    <tr>
      <td><strong>Vector Embedding</strong></td>
      <td><code>microsoft/harrier-oss-v1-270m</code> (640-dim)</td>
      <td>Ekstraksi representasi semantik kalimat pengalaman dan proyek kerja secara lokal di VPS tanpa latensi external cloud.</td>
    </tr>
    <tr>
      <td><strong>LLM Inference Gateway</strong></td>
      <td>9Router Loopback Container (Gemini 3.8 Flash High)</td>
      <td>Gateway inferensi AI lokal dengan pre-flight PII verification filter dan penulisan cache database <code>llm_cache</code>.</td>
    </tr>
    <tr>
      <td><strong>Web Server & SSL</strong></td>
      <td>Caddy v2 (Docker Container)</td>
      <td>Reverse proxy otomatis dengan HTTP/2, auto-SSL Cloudflare/Let's Encrypt, dan kompresi Gzip/Brotli.</td>
    </tr>
  </tbody>
</table>

<h3>Diagram Arsitektur Sistem Terdistribusi</h3>
<div class="arch-container avoid-break">
  <div class="arch-layer">
    <div class="arch-layer-title">
      <span>1. Klient Web / Browser Pengguna</span>
      <span style="color: #94a3b8; font-weight: normal;">HTTPS (Port 443)</span>
    </div>
    <div class="arch-layer-desc">
      React 18 TypeScript SPA (<code>screening.rifqisetiawan.my.id</code>) • State Management Reaktif • Blind-mode Leaderboard • Drawer Inspeksi Bukti
    </div>
  </div>

  <div class="arch-arrow">▼ Reverse Proxy & SSL Termination</div>

  <div class="arch-layer">
    <div class="arch-layer-title">
      <span>2. Caddy v2 Ingress Reverse Proxy (Docker Container)</span>
      <span style="color: #94a3b8; font-weight: normal;">Loopback 127.0.0.1:8110</span>
    </div>
    <div class="arch-layer-desc">
      Otomasi Sertifikat SSL/TLS • Injeksi Header Keamanan • Pemetaan Header Klien (Forwarded-For) • Penanganan Berkas Statis
    </div>
  </div>

  <div class="arch-arrow">▼ REST API Calls & WebSocket</div>

  <div class="arch-layer">
    <div class="arch-layer-title">
      <span>3. FastAPI Backend Core Application (Port 8110)</span>
      <span style="color: #94a3b8; font-weight: normal;">Python 3.12 Multi-Worker</span>
    </div>
    <div class="arch-layer-desc">
      • <strong>Middleware:</strong> Sliding-window Rate Limiter (User/IP) & CORS Strict Whitelist.<br>
      • <strong>Security:</strong> RBAC JWT Guard (Admin/Recruiter/HM) & Isolasi Multi-Tenant Mutlak (Anti-IDOR).<br>
      • <strong>Routing:</strong> <code>/jobs</code>, <code>/cvs</code>, <code>/requirements</code>, <code>/screenings</code>, <code>/eligibility-rules</code>, <code>/candidates</code>, <code>/metrics</code>.
    </div>
  </div>

  <div class="arch-arrow">▼ Query & Enqueue</div>

  <div class="arch-grid">
    <div class="arch-layer" style="margin-bottom: 0;">
      <div class="arch-layer-title"><span>4. Basis Data PostgreSQL 16</span></div>
      <div class="arch-layer-desc">
        • <strong>pgvector:</strong> HNSW Cosine Index (640d)<br>
        • <strong>pgcrypto:</strong> Enkripsi Data Pribadi<br>
        • <strong>Alembic:</strong> Migrasi Skema Terkelola<br>
        • <strong>Append-Only:</strong> <code>audit_logs</code> & <code>llm_cache</code>
      </div>
    </div>

    <div class="arch-layer" style="margin-bottom: 0;">
      <div class="arch-layer-title"><span>5. Asynchronous Worker & AI</span></div>
      <div class="arch-layer-desc">
        • <strong>Antrean:</strong> <code>jobs_queue</code> Polling Loop (SKIP LOCKED)<br>
        • <strong>Pipeline:</strong> Sanitizer → Redactor → Harrier Embedding<br>
        • <strong>9Router AI:</strong> Pre-flight PII Leak Filter → LLM Verifier (Timeout 10s)
      </div>
    </div>
  </div>
</div>

<div class="page-break"></div>

<!-- ============================================================== -->
<!-- BAB 3: PIPELINE PEMROSESAN CV (ALUR END-TO-END)                -->
<!-- ============================================================== -->
<h2>3. Pipeline Pemrosesan Dokumen CV</h2>

<p>
  Setiap dokumen CV yang diunggah melewati 9 tahapan pemrosesan berurutan yang ketat dan saling mengunci guna memastikan integritas data, anonimitas kandidat, dan akurasi skor akhir.
</p>

<div class="step-card avoid-break">
  <h4><span class="step-num">1</span> Sanitasi & Inspeksi Berkas (Ingestion Gate)</h4>
  <p>
    Berkas PDF atau DOCX yang masuk diperiksa integritas fisiknya: deteksi file kosong (0 byte / <code>EMPTY_DOCUMENT</code>), proteksi kata sandi (<code>ENCRYPTED_FILE</code>), berkas arsip berbahaya, serta infeksi makro script. Berkas yang tidak valid langsung ditandai dengan status <code>REJECTED</code> atau <code>NEEDS_REVIEW</code> dan tidak membebani proses selanjutnya.
  </p>
</div>

<div class="step-card avoid-break">
  <h4><span class="step-num">2</span> Deteksi Duplikasi Cerdas (Multi-Layer Dedup)</h4>
  <p>
    Sistem menjalankan deduplikasi pada dua lapisan:
  </p>
  <ul>
    <li><strong>Lapisan Byte (SHA-256):</strong> Jika hash berkas identik dengan dokumen yang sudah ada di lowongan yang sama, berkas kedua otomatis berstatus <code>DUPLICATE</code>.</li>
    <li><strong>Lapisan Teks (Text Fingerprint):</strong> Hash SHA-256 dihitung dari <code>full_text_redacted</code> yang dinormalisasi (huruf kecil dan spasi dirapikan). Jika ada berkas lain dengan isi teks identik (meski diekspor ulang dalam format berbeda), dokumen ditandai <code>DUPLICATE</code>.</li>
    <li><strong>Kandidat Sama Multi-CV:</strong> Jika kandidat yang sama mengunggah CV versi revisi dengan isi berbeda, berkas kedua tetap diproses tetapi disematkan flag <code>POSSIBLE_DUPLICATE_OF:&lt;candidate_code&gt;</code>.</li>
  </ul>
</div>

<div class="step-card avoid-break">
  <h4><span class="step-num">3</span> Pemisahan Identitas & Redaksi PII (Blind-Mode)</h4>
  <p>
    Modul <code>src/worker/redaction.py</code> memisahkan data identitas secara permanen:
  </p>
  <ul>
    <li>Nama lengkap disensor menjadi token <code>[NAMA]</code>.</li>
    <li>Alamat email disensor menjadi token <code>[EMAIL]</code> dan nomor telepon menjadi <code>[TELEPON]</code>.</li>
    <li>Baris demografis (Agama, Status Pernikahan, Tanggal Lahir, Jenis Kelamin) dipotong dari profil evaluasi dan disimpan secara aman ke dalam kolom terenkripsi <code>candidate_identities.other_personal</code>.</li>
    <li>Menghasilkan <code>matching_profile</code> dan <code>full_text_redacted</code> yang telah melalui pembersihan PII dan demografis secara menyeluruh untuk digunakan oleh engine evaluasi.</li>
  </ul>
</div>

<div class="step-card avoid-break">
  <h4><span class="step-num">4</span> Chunking & Representasi Vektor Semantik (Embedding)</h4>
  <p>
    Setiap entri pengalaman kerja, proyek, pendidikan, dan sertifikasi dipecah menjadi potongan teks terstruktur (<em>chunks</em>). Model <code>microsoft/harrier-oss-v1-270m</code> menghasilkan representasi vektor 640 dimensi untuk setiap chunk, yang diindeks ke dalam PostgreSQL menggunakan algoritma <strong>HNSW (Hierarchical Navigable Small World)</strong> berjarak kosinus.
  </p>
</div>

<div class="step-card avoid-break">
  <h4><span class="step-num">5</span> Kompilasi Kriteria Lowongan & Persetujuan (Requirements Lock)</h4>
  <p>
    Teks Job Description (JD) dikompilasi menjadi kriteria terstruktur dengan taksonomi konsep:
  </p>
  <ul>
    <li>Kategori: <code>EXPERIENCE</code>, <code>HARD_SKILLS</code>, <code>EDUCATION_CERT</code>, <code>ACHIEVEMENT</code>.</li>
    <li>Tingkat Kepentingan: <code>MUST_HAVE</code>, <code>STRONG_PREFERENCE</code>, <code>NICE_TO_HAVE</code>.</li>
    <li><strong>Gerbang Persetujuan (FX-03):</strong> Kriteria yang dihasilkan berstatus <code>DRAFT</code>. Screening dilarang berjalan (HTTP 409) sebelum HR atau Admin melakukan review dan menekan tombol <strong>Setujui Kriteria (Lock Version)</strong>.</li>
  </ul>
</div>

<div class="page-break"></div>

<div class="step-card avoid-break">
  <h4><span class="step-num">6</span> Evaluasi Multi-Kind Rules (Rule-Based Matching)</h4>
  <p>
    Setiap kriteria dievaluasi terhadap <code>matching_profile</code> kandidat menggunakan aturan jenis (<em>kind rules</em>) yang deterministik:
  </p>
  <table>
    <thead>
      <tr>
        <th style="width: 25%;">Jenis Kriteria</th>
        <th style="width: 45%;">Metode Evaluasi</th>
        <th style="width: 30%;">Keluaran Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><code>EXPERIENCE_DURATION</code></td>
        <td>Menghitung akumulasi interval bulan kerja pada rumpun peran yang relevan (misal: Backend Engineer). Mendukung parameter tanggal dinamis (<code>as_of</code>).</td>
        <td><code>STRONG</code> (≥ batas min), <code>PARTIAL</code> (≥50%), <code>NOT_DEMONSTRATED</code> (&lt;50%).</td>
      </tr>
      <tr>
        <td><code>SKILL</code></td>
        <td>Pencocokan kata kunci dengan batas kata ketat (<code>\b</code>), deteksi kalimat negasi (*"tidak menguasai"*, *"belum pernah"*), dan disambiguasi bahasa (Java ≠ JavaScript, SQL ≠ SQLite).</td>
        <td><code>STRONG</code> (pada riwayat kerja), <code>PARTIAL</code> (pada proyek/skills list), <code>NOT_DEMONSTRATED</code>.</td>
      </tr>
      <tr>
        <td><code>RESPONSIBILITY</code></td>
        <td>Pencocokan tanggung jawab spesifik (misal: merancang REST API, memimpin tim, pengelolaan anggaran).</td>
        <td><code>STRONG</code>, <code>PARTIAL</code>, <code>NOT_DEMONSTRATED</code>.</td>
      </tr>
      <tr>
        <td><code>EDUCATION</code></td>
        <td>Verifikasi jenjang pendidikan formal (S1, S2, D3, SMK) dan rumpun ilmu (Teknik Informatika, Sistem Informasi, dsb).</td>
        <td><code>STRONG</code> (jenjang & jurusan cocok), <code>PARTIAL</code> (jurusan serumpun).</td>
      </tr>
      <tr>
        <td><code>CERTIFICATION</code></td>
        <td>Pencocokan sertifikasi profesional resmi (AWS Certified, BNSP, dsb).</td>
        <td><code>STRONG</code>, <code>NOT_DEMONSTRATED</code>.</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="step-card avoid-break">
  <h4><span class="step-num">7</span> Grounded LLM Verifier (Pemeriksaan Bukti Ambigu)</h4>
  <p>
    Jika sebuah kriteria berstatus <code>PARTIAL</code> atau ambigu dan memiliki potongan bukti teks (snippets), LLM Verifier dipanggil secara asinkron (timeout 10 detik):
  </p>
  <ul>
    <li>LLM <strong>dilarang keras mengeluarkan skor numerik</strong>; hanya memilih dari 3 status diskret: <code>STRONG</code>, <code>PARTIAL</code>, atau <code>NOT_DEMONSTRATED</code>.</li>
    <li><strong>Verifikasi Grounding Berbasis Kode:</strong> Kutipan kalimat pembuktian (<em>quote</em>) yang diberikan LLM wajib ada secara persis kata-demi-kata (<em>exact substring</em>) di dalam <code>full_text_redacted</code>.</li>
    <li>Jika kutipan dihalusinasi oleh LLM, sistem otomatis membatalkan saran LLM, mengembalikan status ke aturan dasar, dan menyematkan flag <code>GROUNDING_FAIL</code>.</li>
  </ul>
</div>

<div class="step-card avoid-break">
  <h4><span class="step-num">8</span> Deterministic Scoring Engine & Banding</h4>
  <p>
    Skor akhir dihitung menggunakan <strong>Scoring Rubric Spec</strong>:
  </p>
  <pre><code># Bobot status kriteria
STATE_VALUE = {"STRONG": 1.0, "PARTIAL": 0.5, "NOT_DEMONSTRATED": 0.0}

# Pembagian Band & Skor Maksimal (Capping)
Band A: Semua kriteria MUST_HAVE berstatus STRONG (Maksimal 100.0) -> Disarankan SHORTLIST
Band B: Tepat 1 kriteria MUST_HAVE belum STRONG  (Dibatasi maks 74.0) -> Perlu REVIEW
Band C: ≥ 2 kriteria MUST_HAVE belum STRONG      (Dibatasi maks 49.0) -> Prioritas Rendah
Band R: Ada kriteria MUST_HAVE berstatus UNKNOWN (Dibatasi untuk CEK MANUAL)

# Penalti Coverage Rendah (FX-26)
Jika coverage (bobot kriteria terjawab / total bobot) < 0.6:
  -> Sematkan flag 'LOW_COVERAGE'
  -> Rekomendasi otomatis diturunkan menjadi MANUAL_CHECK (dilarang SHORTLIST)</code></pre>
</div>

<div class="step-card avoid-break">
  <h4><span class="step-num">9</span> Administrative Eligibility Gate (FX-24 Revisi 2)</h4>
  <p>
    Memproses batasan usia dan preferensi jenis kelamin secara terpisah dari skor kompetensi:
  </p>
  <ul>
    <li>Kandidat diklasifikasikan ke dalam 3 badge status: <strong><code>ELIGIBLE</code></strong>, <strong><code>NOT_ELIGIBLE</code></strong>, atau <strong><code>UNKNOWN</code></strong>.</li>
    <li>CV modern yang tidak mencantumkan tanggal lahir atau jenis kelamin otomatis mendapat status <code>UNKNOWN</code> dan <strong>tidak boleh digugurkan</strong>.</li>
    <li>Usia dihitung secara matematis pada tanggal acuan lowongan (<code>reference_date</code>). Tidak ada perkiraan dari tahun kelulusan kuliah atau tebakan jenis kelamin dari foto/nama.</li>
  </ul>
</div>

<div class="page-break"></div>

<!-- ============================================================== -->
<!-- BAB 4: TATA KELOLA HUKUM, PRIVASI, & KEAMANAN                  -->
<!-- ============================================================== -->
<h2>4. Tata Kelola Hukum, Privasi, & Keamanan Data</h2>

<p>
  Sistem dirancang dengan kepatuhan tingkat tinggi terhadap regulasi ketenagakerjaan dan privasi data di Indonesia serta standar rekayasa perangkat lunak internasional.
</p>

<h3>Kepatuhan SE Menaker M/6/HK.04/V/2025 & UU PDP</h3>
<div class="callout callout-info avoid-break">
  <p style="margin-bottom: 4pt;">
    <strong>Surat Edaran Menaker RI No. M/6/HK.04/V/2025</strong> menegaskan larangan diskriminasi dalam proses rekrutmen tenaga kerja, khususnya pembatasan usia dan jenis kelamin yang tidak relevan dengan karakteristik pekerjaan. Sementara itu, <strong>Undang-Undang Pelindungan Data Pribadi (UU No. 27 Tahun 2022)</strong> memberikan hak bagi subjek data untuk menolak keputusan yang diambil murni secara otomatis (<em>fully automated decision-making</em>).
  </p>
  <p style="margin-bottom: 0;">
    Platform ini mengimplementasikan prinsip <strong>Human-in-the-Loop</strong> secara penuh: sistem tidak memiliki tombol atau logika untuk melakukan auto-rejection berbasis demografi. Seluruh keputusan penerimaan atau penolakan tetap berada di tangan recruiter manusia yang terverifikasi.
  </p>
</div>

<table>
  <thead>
    <tr>
      <th style="width: 30%;">Aspek Keamanan</th>
      <th style="width: 70%;">Implementasi Proteksi</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Isolasi Multi-Tenant (Anti-IDOR)</strong></td>
      <td>Seluruh tabel relational dan query database memuat klausa <code>tenant_id</code> wajib yang diekstrak langsung dari token JWT terotentikasi. Rekruter Perusahaan A mustahil melihat kandidat, lowongan, atau hasil ranking milik Perusahaan B.</td>
    </tr>
    <tr>
      <td><strong>Enkripsi Data Sensitif (Vault)</strong></td>
      <td>Data demografis pribadi pada tabel <code>candidate_identities</code> dienkripsi di level basis data menggunakan <code>pgp_sym_encrypt</code>. File fisik PDF/DOCX disimpan di direktori vault terisolasi dengan permission <code>0700</code>.</td>
    </tr>
    <tr>
      <td><strong>Audit Trail Permanen (Immutable)</strong></td>
      <td>Setiap tindakan sensitif (seperti pengungkapan identitas asli pelamar / <em>reveal identity</em>, persetujuan aturan eligibilitas, dan penetapan status kriteria) dicatat secara permanen di tabel <code>audit_logs</code> tanpa izin UPDATE atau DELETE bagi user aplikasi.</td>
    </tr>
    <tr>
      <td><strong>Proteksi Penetrasi & Rate Limit</strong></td>
      <td>Rate limiter sliding-window per-user token dan per-IP membatasi flood request. Pengaturan CORS ketat memblokir domain penyerang tanpa wildcard credentials. Endpoint metrik <code>/metrics</code> dilindungi token autentikasi rahasia.</td>
    </tr>
  </tbody>
</table>

<div class="page-break"></div>

<!-- ============================================================== -->
<!-- BAB 5: PANDUAN PENGGUNAAN LENGKAP (RECRUITER / HR)             -->
<!-- ============================================================== -->
<h2>5. Panduan Penggunaan Lengkap (Panduan HR & Recruiter)</h2>

<p>
  Bab ini memandu tim rekruter dan HR dalam mengoperasikan platform melalui antarmuka web modern di <code>https://screening.rifqisetiawan.my.id</code>.
</p>

<div class="step-card avoid-break">
  <h4>Langkah 1: Setup Lowongan Kerja & Ekstraksi Kriteria</h4>
  <p>
    1. Buka aplikasi web dan pilih menu <strong>Setup Lowongan Kerja</strong>.<br>
    2. Masukkan judul posisi kerja (misal: <em>Senior Backend Engineer</em>) dan tempel teks Job Description (JD) lengkap pada area input.<br>
    3. Klik tombol <strong>Ekstrak Kriteria & Lanjut</strong>. Sistem akan membaca JD dan membedah kriteria ke dalam format terstruktur secara otomatis.
  </p>
</div>

<div class="step-card avoid-break">
  <h4>Langkah 2: Tinjau, Edit, & Kunci Kriteria Lowongan</h4>
  <p>
    1. Sistem menampilkan daftar kriteria hasil ekstraksi lengkap dengan kategori (Pengalaman, Hard Skills, Pendidikan, Prestasi) dan bobotnya.<br>
    2. <strong>Deteksi Pelanggaran:</strong> Jika teks lowongan memuat unsur diskriminatif (misal: "berpenampilan menarik", "wajib lajang", "suku tertentu"), sistem menampilkan peringatan merah dan memblokir penguncian kriteria.<br>
    3. HR dapat mengubah tingkat kepentingan (Wajib / Nilai Tambah) atau menambah kriteria manual.<br>
    4. Klik <strong>Setujui Kriteria (Kunci Versi)</strong> untuk mengunci kriteria menjadi versi resmi sebelum beralih ke tahap unggah CV.
  </p>
</div>

<div class="step-card avoid-break">
  <h4>Langkah 3: Unggah Berkas CV Pelamar</h4>
  <p>
    1. Pada layar <strong>Upload CV Pelamar</strong>, tarik dan letakkan berkas CV kandidat (format PDF atau DOCX) ke area dropzone. Pengguna juga dapat mengunggah arsip <code>.ZIP</code> berisi ratusan CV sekaligus.<br>
    2. Untuk keperluan pengujian cepat atau demonstrasi, HR dapat menekan tombol <strong>Muat 15 Sampel Golden Dataset</strong>.<br>
    3. Sistem memproses sanitasi berkas, melakukan redaksi identitas, dan menampilkan status kesiapan berkas pada tabel.
  </p>
</div>

<div class="step-card avoid-break">
  <h4>Langkah 4: Jalankan Screening & Analisis Leaderboard</h4>
  <p>
    1. Klik tombol hijau <strong>Mulai Screening & Buka Leaderboard</strong>.<br>
    2. Sistem mengevaluasi seluruh CV terhadap kriteria yang terkunci dalam hitungan detik.<br>
    3. Layar Leaderboard menampilkan peringkat pelamar secara <strong>Blind Mode</strong>:
  </p>
  <ul>
    <li>Kolom Kandidat hanya menampilkan kode blind (<code>C-0001</code>, <code>C-0002</code>) dan nama berkas dokumen.</li>
    <li>Badge Rekomendasi: <span class="badge badge-emerald">Disarankan Shortlist</span> (Band A), <span class="badge badge-amber">Perlu Ditinjau</span> (Band B), atau <span class="badge badge-purple">Perlu Cek Manual</span> (Band R).</li>
    <li>Badge Eligibility: Jika lowongan memiliki aturan usia/gender, badge <span class="badge badge-amber">⚠️ Di luar kriteria administratif</span> atau <span class="badge badge-slate">ℹ️ Data administratif tidak tersedia</span> ditampilkan secara transparan di bawah rekomendasi.</li>
  </ul>
</div>

<div class="step-card avoid-break">
  <h4>Langkah 5: Inspeksi Bukti Kualifikasi & Pertanyaan Interview</h4>
  <p>
    1. Klik pada baris kandidat di leaderboard untuk membuka <strong>Drawer Detail Kandidat</strong>.<br>
    2. <strong>Tab 1 (Ringkasan):</strong> Menampilkan ringkasan kualifikasi, kekuatan terbukti di CV, kriteria yang belum terbukti, serta <em>daftar pertanyaan wawancara mendalam yang dihasilkan otomatis</em> untuk memverifikasi kelemahan pelamar.<br>
    3. <strong>Tab 2 (Kartu Skor):</strong> Menampilkan bukti kutipan kalimat riil dari CV untuk setiap kriteria kualifikasi.<br>
    4. <strong>Keputusan HR:</strong> Rekruter dapat langsung menetapkan status: <em>Shortlist</em>, <em>Tahan</em>, atau <em>Tidak Lanjut</em> beserta catatan review internal.
  </p>
</div>

<div class="step-card avoid-break">
  <h4>Langkah 6: Pengungkapan Identitas Asli (Reveal Identity)</h4>
  <p>
    1. Setelah seleksi blind mode selesai dan shortlist final ditentukan, HR dapat menekan tombol <strong>Buka Identitas Kandidat</strong>.<br>
    2. Sistem meminta konfirmasi formal dan mencatat aksi ini ke dalam <code>audit_logs</code> (siapa yang membuka, kapan, dan untuk kandidat mana).<br>
    3. Nama asli, kontak telepon, email, dan tautan LinkedIn kandidat ditampilkan untuk proses penjadwalan wawancara.
  </p>
</div>

<div class="page-break"></div>

<!-- ============================================================== -->
<!-- BAB 6: PANDUAN PENGEMBANG & OPERASIONAL SERVER (RUNBOOK)       -->
<!-- ============================================================== -->
<h2>6. Panduan Pengembang & Operasional Server (DevOps Runbook)</h2>

<p>
  Petunjuk teknis bagi tim pengembang dan System Administrator untuk mengelola, menguji, dan memelihara platform di server VPS Ubuntu.
</p>

<h3>Struktur Direktori Proyek</h3>
<pre><code>/srv/hermes-control/services/cv-screening/
├── src/
│   ├── api/                  # FastAPI router (/jobs, /cvs, /screenings, /eligibility, dsb)
│   │   ├── dependencies.py   # RBAC gate, tenant isolation, DB session dependency
│   │   └── middleware/       # Sliding-window rate limiter & CORS
│   ├── domain/               # Core business logic & deterministic math
│   │   ├── scorer.py         # Scoring engine, rubric spec, band capping, coverage penalty
│   │   ├── eligibility.py    # Administrative eligibility gate (FX-24)
│   │   ├── kind_rules.py     # Experience, skill, education, & cert rule matchers
│   │   ├── text_match.py     # Regex boundary matcher with negation filters
│   │   ├── jd_compiler.py    # JD compilation & importance validator
│   │   └── verifier.py       # Grounded LLM verifier with exact quote verification
│   ├── infrastructure/       # Config, DB connection pool, & 9router gateway client
│   └── worker/               # Ingestion processor, sanitizer, redaction, & embedding
├── migrations/               # Alembic database migration scripts (versions 0001 - 0005)
├── frontend/                 # React 18 TypeScript Vite application
├── scripts/                  # Backup, restore, dev DB reset, & evaluation scripts
├── docs/spec/                # Spesifikasi scoring, skema database, & golden dataset
└── tests/                    # Pytest unit & integration suite (84 automated tests)</code></pre>

<h3>Perintah Operasional Harian</h3>
<table>
  <thead>
    <tr>
      <th style="width: 35%;">Kebutuhan Operasional</th>
      <th style="width: 65%;">Perintah Shell</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Jalankan Seluruh Tes Unit</strong></td>
      <td><code>make test</code> atau <code>PYTHONPATH=. .venv/bin/pytest tests/ -v</code></td>
    </tr>
    <tr>
      <td><strong>Evaluasi Golden Dataset</strong></td>
      <td><code>make eval</code> (menjalankan self-test 15 CV inti dan assertion scoring)</td>
    </tr>
    <tr>
      <td><strong>Linting & Code Formatting</strong></td>
      <td><code>make lint</code> dan <code>make format</code> (menggunakan Ruff & Mypy)</td>
    </tr>
    <tr>
      <td><strong>Migrasi Skema Basis Data</strong></td>
      <td><code>make migrate</code> atau <code>.venv/bin/alembic upgrade head</code></td>
    </tr>
    <tr>
      <td><strong>Restart Layanan API & Worker</strong></td>
      <td><code>sudo systemctl restart cv-screening-api cv-screening-worker</code></td>
    </tr>
    <tr>
      <td><strong>Melihat Log API Real-Time</strong></td>
      <td><code>sudo journalctl -u cv-screening-api.service -f</code></td>
    </tr>
    <tr>
      <td><strong>Pencadangan Database & Dokumen</strong></td>
      <td><code>./scripts/backup.sh</code> (menghasilkan dump SQL & arsip vault di folder backups)</td>
    </tr>
    <tr>
      <td><strong>Kompilasi Frontend SPA</strong></td>
      <td><code>cd frontend && npm run build</code> (output static ke <code>dist/</code>)</td>
    </tr>
  </tbody>
</table>

<h3>Ringkasan Endpoint REST API Utama</h3>
<table>
  <thead>
    <tr>
      <th style="width: 32%;">Method & Path</th>
      <th style="width: 20%;">Role Akses</th>
      <th style="width: 48%;">Deskripsi Fungsi</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>POST /api/v1/auth/login</code></td>
      <td>Publik</td>
      <td>Autentikasi kredensial email & password, mengembalikan token akses JWT.</td>
    </tr>
    <tr>
      <td><code>POST /api/v1/jobs</code></td>
      <td>Admin, Recruiter</td>
      <td>Membuat lowongan baru dengan deskripsi pekerjaan (Job Description).</td>
    </tr>
    <tr>
      <td><code>POST /api/v1/jobs/{id}/requirements/approve</code></td>
      <td>Admin, Recruiter</td>
      <td><strong>Gerbang Approval (FX-03):</strong> Menyetujui dan mengunci versi kriteria.</td>
    </tr>
    <tr>
      <td><code>POST /api/v1/jobs/{id}/cvs</code></td>
      <td>Admin, Recruiter</td>
      <td>Mengunggah berkas CV pelamar (PDF, DOCX, ZIP) untuk diproses asinkron.</td>
    </tr>
    <tr>
      <td><code>POST /api/v1/jobs/{id}/screenings</code></td>
      <td>Admin, Recruiter</td>
      <td>Menjalankan pipeline evaluasi & scoring deterministik terhadap seluruh CV siap uji.</td>
    </tr>
    <tr>
      <td><code>GET /api/v1/jobs/{id}/screenings/latest</code></td>
      <td>Semua Role</td>
      <td>Mengambil hasil leaderboard ranking, skor, band, dan status eligibilitas terbaru.</td>
    </tr>
    <tr>
      <td><code>POST /api/v1/jobs/{id}/eligibility-rules</code></td>
      <td>Recruiter</td>
      <td>Menambahkan aturan kriteria usia/gender dengan justifikasi tertulis (min 30 char).</td>
    </tr>
    <tr>
      <td><code>POST /api/v1/jobs/{id}/eligibility-rules/{r_id}/approve</code></td>
      <td><strong>Admin Saja</strong></td>
      <td>Menyetujui dan mengaktifkan aturan eligibilitas administratif (tercatat di audit log).</td>
    </tr>
    <tr>
      <td><code>POST /api/v1/candidates/{id}/reveal-identity</code></td>
      <td>Admin, Recruiter</td>
      <td>Membuka identitas asli pelamar dari mode blind (tercatat di audit log anti-IDOR).</td>
    </tr>
    <tr>
      <td><code>GET /metrics</code></td>
      <td>Bearer Token</td>
      <td>Telemetri format standar Prometheus untuk pemantauan kesehatan & performa sistem.</td>
    </tr>
  </tbody>
</table>

<div style="margin-top: 25pt; padding-top: 12pt; border-top: 1pt solid var(--slate-200); text-align: center; font-size: 8pt; color: var(--slate-500);">
  © 2026 AI CV Screening & Ranking Platform • Dokumen Spesifikasi Arsitektur Sistem & Manual Pengoperasian
</div>

</body>
</html>
"""

def generate_pdf(output_path: str):
    print("Mempersiapkan browser Chromium headless via Playwright...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(HTML_CONTENT, wait_until="networkidle")
        
        # Print to PDF with precise formatting
        page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"},
            display_header_footer=True,
            header_template='<div style="font-size: 8pt; font-family: sans-serif; width: 100%; text-align: right; padding-right: 15mm; color: #94a3b8;">AI CV Screening & Ranking Platform — Buku Panduan Arsitektur & Penggunaan</div>',
            footer_template='<div style="font-size: 8pt; font-family: sans-serif; width: 100%; text-align: center; color: #94a3b8;">Halaman <span class="pageNumber"></span> dari <span class="totalPages"></span></div>',
        )
        browser.close()
    print(f"Dokumen PDF berhasil dibuat di: {output_path}")

if __name__ == "__main__":
    target_path = "/srv/hermes-control/services/cv-screening/docs/Buku_Panduan_Arsitektur_dan_Penggunaan_AI_CV_Screening.pdf"
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    generate_pdf(target_path)
