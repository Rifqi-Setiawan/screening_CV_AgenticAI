"""Generate publication-grade 6-page PDF documentation for Agentic AI CV Screening Platform (v2.1).
Rendered via Playwright with modern executive styling (Plus Jakarta Sans, JetBrains Mono).
"""

from __future__ import annotations

from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path("/srv/hermes-control/services/cv-screening-agentic/docs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PDF = OUTPUT_DIR / "DOKUMENTASI_LENGKAP_AGENTIC_CV_SCREENING_V2.1.pdf"

html_content = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Buku Panduan & Dokumentasi Arsitektur: Agentic AI CV Screening & Candidate Ranking Platform (v2.1)</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    @page {
      size: A4 portrait;
      margin: 12mm 12mm 14mm 12mm;
      @bottom-right {
        content: "Halaman " counter(page) " dari " counter(pages);
        font-family: 'JetBrains Mono', monospace;
        font-size: 7.5pt;
        color: #64748b;
      }
      @bottom-left {
        content: "Agentic AI CV Screening Platform v2.1 • Arsitektur & Panduan Sistem • Muhammad Rifqi Setiawan";
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 7.5pt;
        color: #94a3b8;
      }
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      color: #1e293b;
      background: #ffffff;
      line-height: 1.5;
      font-size: 9pt;
    }

    .page {
      page-break-after: always;
      position: relative;
      height: 270mm;
      overflow: hidden;
    }

    .page:last-child {
      page-break-after: avoid;
    }

    /* Typography */
    h1, h2, h3, h4 {
      color: #0f172a;
      font-weight: 700;
      letter-spacing: -0.02em;
    }

    h1 { font-size: 18pt; line-height: 1.2; }
    h2 { font-size: 12pt; margin-top: 10pt; margin-bottom: 6pt; border-bottom: 1.5pt solid #e2e8f0; padding-bottom: 2pt; color: #1e3a8a; }
    h3 { font-size: 10pt; margin-top: 8pt; margin-bottom: 4pt; color: #0369a1; }
    h4 { font-size: 9pt; margin-top: 4pt; margin-bottom: 2pt; color: #334155; }

    p { margin-bottom: 5pt; text-align: justify; }

    /* Code & Pre */
    code, pre {
      font-family: 'JetBrains Mono', monospace;
    }

    code {
      background: #f1f5f9;
      color: #0f172a;
      padding: 1pt 3pt;
      border-radius: 3pt;
      font-size: 8pt;
      border: 0.5pt solid #cbd5e1;
    }

    pre {
      background: #0f172a;
      color: #f8fafc;
      padding: 7pt 9pt;
      border-radius: 4pt;
      font-size: 7.5pt;
      line-height: 1.35;
      margin: 5pt 0;
      overflow-x: hidden;
      white-space: pre-wrap;
      word-break: break-all;
    }

    pre code {
      background: transparent;
      color: inherit;
      padding: 0;
      border: none;
    }

    /* Badges & Tags */
    .badge {
      display: inline-block;
      font-size: 7pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 1.5pt 4pt;
      border-radius: 3pt;
      vertical-align: middle;
    }
    .badge-primary { background: #dbeafe; color: #1e40af; border: 0.5pt solid #93c5fd; }
    .badge-success { background: #dcfce7; color: #166534; border: 0.5pt solid #86efac; }
    .badge-warning { background: #fef3c7; color: #92400e; border: 0.5pt solid #fde68a; }
    .badge-purple  { background: #f3e8ff; color: #6b21a8; border: 0.5pt solid #d8b4fe; }

    /* Header Banner */
    .hero-banner {
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0369a1 100%);
      color: #ffffff;
      padding: 14pt 14pt;
      border-radius: 6pt;
      margin-bottom: 10pt;
      box-shadow: 0 4pt 8pt rgba(0,0,0,0.06);
    }
    .hero-banner h1 { color: #ffffff; margin-bottom: 3pt; }
    .hero-banner p { color: #cbd5e1; margin-bottom: 0; font-size: 8.5pt; }
    .meta-bar {
      margin-top: 8pt;
      display: flex;
      flex-wrap: wrap;
      gap: 8pt;
      font-size: 7.5pt;
      color: #94a3b8;
      border-top: 0.5pt solid rgba(255,255,255,0.2);
      padding-top: 6pt;
    }
    .meta-bar strong { color: #f8fafc; }

    /* Cards & Grids */
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6pt;
      margin: 4pt 0;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 5pt;
      margin: 4pt 0;
    }

    .card {
      background: #f8fafc;
      border: 0.5pt solid #cbd5e1;
      border-radius: 4pt;
      padding: 6pt 8pt;
      margin-bottom: 4pt;
    }
    .card-accent {
      border-left: 3pt solid #2563eb;
      background: #f0f7ff;
    }
    .card-critic {
      border-left: 3pt solid #9333ea;
      background: #faf5ff;
    }
    .card-success {
      border-left: 3pt solid #16a34a;
      background: #f0fdf4;
    }
    .card h4 { margin-top: 0; }

    /* Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 4pt 0 6pt 0;
      font-size: 8pt;
    }
    th, td {
      border: 0.5pt solid #cbd5e1;
      padding: 3.5pt 5pt;
      text-align: left;
    }
    th {
      background: #f1f5f9;
      color: #0f172a;
      font-weight: 700;
    }
    tr:nth-child(even) {
      background: #f8fafc;
    }

    .callout {
      border-left: 2.5pt solid #0284c7;
      background: #f0f9ff;
      padding: 5pt 7pt;
      border-radius: 0 4pt 4pt 0;
      margin: 5pt 0;
      font-size: 8pt;
    }

    ul, ol {
      margin-left: 12pt;
      margin-bottom: 4pt;
    }
    li {
      margin-bottom: 1.5pt;
    }
  </style>
</head>
<body>

  <!-- ================= HALAMAN 1: EXECUTIVE OVERVIEW & PROBLEM STATEMENT ================= -->
  <div class="page">
    <div class="hero-banner">
      <div style="margin-bottom: 4pt;">
        <span class="badge badge-primary">Blueprint v2.1 Research-Based</span>
        <span class="badge badge-success">Production Ready</span>
        <span class="badge badge-purple">Multi-Model Agentic AI</span>
      </div>
      <h1>Agentic AI CV Screening & Candidate Ranking Platform</h1>
      <p>Buku Panduan Komprehensif Arsitektur Sistem, Logika Penalaran Asimetris, Temporal Calendar Union, dan Protokol Audit Multi-Agent.</p>
      
      <div class="meta-bar">
        <div>Author & Lead Architect: <strong>Muhammad Rifqi Setiawan</strong></div>
        <div>Status Operasional: <strong>Active di Port 8111 (HTTPS Let's Encrypt)</strong></div>
        <div>Public Domain: <strong>agentic-screening.rifqisetiawan.my.id</strong></div>
        <div>GitHub: <strong>github.com/Rifqi-Setiawan/screening_CV_AgenticAI</strong></div>
      </div>
    </div>

    <h2>1. Executive Summary & Latar Belakang Masalah</h2>
    <p>
      Sistem penyaringan lamaran kerja (<em>Applicant Tracking System</em> / ATS) konvensional dan pipeline evaluasi berbasis AI generasi pertama (v1) memiliki kelemahan fundamental yang merugikan baik pelamar berkualitas maupun tim rekrutmen. Pendekatan pencocokan kata kunci mentah (<em>exact keyword matching</em>) dan embedding kosinus simetris langsung antara CV dan Job Description (JD) menghasilkan bias keputusan yang signifikan dan rentan dimanipulasi.
    </p>

    <h3>5 Masalah Utama pada ATS Konvensional:</h3>
    <div class="grid-2">
      <div class="card card-accent">
        <h4>1. Title vs Context Blindness (Bias Judul Jabatan)</h4>
        <p>ATS konvensional menolak kandidat dengan jabatan <em>Software Engineer</em> yang memiliki pengalaman 4 tahun membangun React SPA saat melamar posisi <em>Frontend Developer</em>. Sistem gagal melihat bahwa aktivitas kerjanya secara logis memenuhi seluruh kualifikasi yang dicari.</p>
      </div>
      <div class="card card-accent">
        <h4>2. Halusinasi Durasi & Overlap Error</h4>
        <p>Model AI generatif sangat buruk dalam matematika kalender. LLM sering melakukan <em>double-counting</em> pada dua posisi paralel (misal: pekerjaan tetap + freelance) atau salah menghitung rentang bulan, sehingga estimasi senioritas melenceng jauh dari realita.</p>
      </div>
      <div class="card card-accent">
        <h4>3. Kerentanan Manipulasi Keyword Stuffing</h4>
        <p>Kandidat yang mencantumkan daftar ratusan skill di bagian <em>summary</em> tanpa bukti proyek nyata sering mendapatkan skor lebih tinggi daripada kandidat kompeten yang hanya menuliskan teknologi yang benar-benar mereka gunakan dalam pekerjaan.</p>
      </div>
      <div class="card card-accent">
        <h4>4. Eksploitasi Teks Tersembunyi (Hidden Text)</h4>
        <p>ATS berbasis parser PDF mentah mudah dikelabui oleh teks berukuran mikro (&lt;4pt) atau teks berwarna putih di atas latar putih yang disisipkan oleh kandidat nakal untuk memicu kemiripan embedding 100% secara manipulatif.</p>
      </div>
    </div>

    <div class="card card-critic">
      <h4>5. Halusinasi Sitasi & Keputusan Gelap (Black-Box AI)</h4>
      <p>AI generatif tanpa arsitektur grounding yang ketat kerap mengarang prestasi kandidat (misal: "Kandidat meningkatkan traffic 50%") yang sebenarnya tidak pernah tertulis di berkas asli. Akibatnya, rekruter tidak dapat mempercayai penjelasan evaluasi.</p>
    </div>

    <h2>2. Solusi Paradigma Baru: Blueprint v2.1</h2>
    <p>
      Platform ini dibangun di atas <strong>Blueprint v2.1 (Research-Based)</strong> dengan prinsip <em>Grounding by Construction</em>. Seluruh perhitungan numerik, interval waktu, dan skor diisolasi ke dalam modul Python deterministik, sementara LLM digunakan secara terarah hanya untuk penalaran semantik (<em>semantic entailment</em>) berbasis bukti atom yang terikat koordinat fisik dokumen.
    </p>
  </div>

  <!-- ================= HALAMAN 2: ARSITEKTUR & FILOSOFI ASYMMETRIC REASONING ================= -->
  <div class="page">
    <h2>3. Arsitektur Sistem & Filosofi Asymmetric Reasoning</h2>
    <p>
      Arsitektur v2.1 mengadopsi pemisahan dua graph independen: <strong>Graph A (Profiling Pipeline)</strong> yang dieksekusi 1x per berkas dokumen, dan <strong>Graph B (Screening Pipeline)</strong> yang dieksekusi saat evaluasi pelamar terhadap lowongan kerja tertentu.
    </p>

    <div class="card" style="background: #0f172a; color: #f8fafc; border: none; padding: 10pt;">
      <h4 style="color: #38bdf8; text-align: center; margin-bottom: 6pt;">DIAGRAM ARSITEKTUR DUA GRAPH (GRAPH A & GRAPH B)</h4>
      <pre style="background: transparent; color: #e2e8f0; font-size: 7pt; line-height: 1.3; text-align: center; border: none; margin: 0;">
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GRAPH A: PROFILING PIPELINE (1x per Dokumen CV saat Ingestion)                                  │
│ [Berkas PDF/DOCX] ➔ [Visibility Gate] ➔ [PII Redaction] ➔ [Evidence Atomizer] ➔ [Profiler Agent]│
│                        (Filter &lt;4pt)      (UU PDP 27/2022)   (ID: E1.B1, Tiers)     (Ontology)  │
└────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ DATABASE POSTGRESQL 16 + PGVECTOR 0.8.7 (Storage Vault, Atoms, & Ontology Concepts)             │
└────────────────────────────────────────────────┬────────────────────────────────────────────────┘
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│ GRAPH B: SCREENING PIPELINE (Per Lowongan Kerja / On-Demand)                                    │
│ [Job Description] ➔ [RequirementIR (5 Facets)] ➔ [Calendar Union] ➔ [Matcher Agent (Gemini)]   │
│                                                   (Sweep-Line)         (Asymmetric Entailment)  │
│                                                                                 │ (Eskalasi E1-E6)│
│ [Output Transparan: Band A/B/C/R] ◄── [Scorer v2] ◄── [Dispute Fallback] ◄── [Critic (Claude)] │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
      </pre>
    </div>

    <h3>Prinsip-Prinsip Utama Arsitektur:</h3>

    <div class="card card-accent">
      <h4>A. Directional Asymmetric Entailment (Penalaran Satu Arah)</h4>
      <p>
        Pencocokan antara kandidat dan kualifikasi bukanlah relasi simetris. Hubungan logis yang diuji adalah: <em>"Apakah bukti pengalaman kandidat mengimplikasikan (entails) terpenuhinya kualifikasi pekerjaan?"</em>. Jika seorang kandidat bekerja membangun REST API menggunakan Python FastAPI dan database PostgreSQL di posisi Software Engineer, fakta ini secara terarah memenuhi kualifikasi "Backend Developer". Matcher mengevaluasi fakta per facet, bukan mencocokkan kata perkata.
      </p>
    </div>

    <div class="card card-accent">
      <h4>B. Grounding by Construction & Evidence Atoms</h4>
      <p>
        AI dilarang mengutip teks bebas dari memori model. Dokumen dipecah menjadi unit terkecil bernama <strong>Evidence Atoms</strong>. Setiap atom memiliki ID unik (misal: <code>E1.B1</code>), teks literal asli, koordinat halaman (bounding box), dan tier bobot bukti:
      </p>
      <ul style="font-size: 8pt; margin-left: 10pt;">
        <li><code>Tier T0 (Klaim Lemah):</code> Hanya bullet skill atau kalimat ringkasan profil (dibatasi skornya).</li>
        <li><code>Tier T1 (Klaim Terkait):</code> Disebutkan dalam deskripsi tanggung jawab umum.</li>
        <li><code>Tier T2 (Aktivitas Kerja Langsung):</code> Proyek nyata dengan aksi, metrik, atau teknologi spesifik.</li>
        <li><code>Tier T3/T4 (Karya/Sertifikasi Terverifikasi):</code> URL publik, repositori kode, atau sertifikasi resmi.</li>
      </ul>
    </div>

    <div class="card card-success">
      <h4>C. Kepatuhan Hukum & Perlindungan Data Pribadi (UU PDP No. 27/2022)</h4>
      <p>
        Sesuai amanat UU No. 27 Tahun 2022 Pasal 10 ayat 1 dan SE Menaker 2025: Data pribadi (nama lengkap, kontak, email, alamat fisik, foto) disensor secara otomatis sebelum teks masuk ke LLM. Sistem membuat pemetaan <code>OffsetMap</code> dwiarah sehingga rekruter manusia dapat melihat kembali teks asli setelah keputusan penilaian selesai. Sistem <strong>tidak pernah menolak kandidat secara otomatis</strong> (Zero Auto-Rejection).
      </p>
    </div>
  </div>

  <!-- ================= HALAMAN 3: GRAPH A (INGESTION & PROFILING) ================= -->
  <div class="page">
    <h2>4. Rincian Teknis Graph A: Ingestion & Profiling Pipeline</h2>
    <p>
      Graph A bertanggung jawab mengubah dokumen CV mentah (PDF, DOCX) menjadi representasi terstruktur berdaya uji tinggi yang tersimpan permanen di database:
    </p>

    <div class="card">
      <h4>Tahap 1: Document Intake, Hash Deduplication & Sanitization</h4>
      <p>
        Saat berkas diunggah melalui endpoint <code>/jobs/{job_id}/cvs</code>, worker menghitung hash <code>SHA-256</code> isi dokumen. Jika berkas yang sama diunggah ulang dalam lowongan yang sama, sistem secara cerdas melakukan deduplikasi instan tanpa membuang komputasi ekstra. Sanitizer memvalidasi integritas struktur berkas dan memastikan dokumen bebas dari payload berbahaya.
      </p>
    </div>

    <div class="card card-accent">
      <h4>Tahap 2: Visibility Gate (Pertahanan Anti-Manipulasi Teks Putih)</h4>
      <p>
        Modul <code>visibility.py</code> memanfaatkan engine PyMuPDF untuk memindai koordinat spasial setiap karakter pada halaman PDF:
      </p>
      <ul style="font-size: 8pt; margin-left: 10pt;">
        <li><strong>Ukuran Font Mikro:</strong> Teks dengan ukuran font &lt; 4.0 pt otomatis ditandai sebagai <em>hidden text</em> dan dibuang dari teks yang dikirim ke AI.</li>
        <li><strong>Warna Font Serupa Latar:</strong> Teks putih di atas latar putih (selisih RGB &lt; 0.05) disaring dan dicatat sebagai anomali manipulasi berkas (flag <code>SUSPECT_COLOR</code>).</li>
        <li><strong>Koordinat di Luar Halaman:</strong> Karakter yang sengaja diletakkan di luar batas MediaBox PDF disaring secara tegas.</li>
      </ul>
    </div>

    <div class="card">
      <h4>Tahap 3: PII Redaction & Dual-Path Offset Mapping</h4>
      <p>
        Modul redaksi menyensor nama, nomor telepon, email, dan entitas sensitif lainnya menjadi token anonim (contoh: <code>[REDACTED_EMAIL_1]</code>). Modul <code>OffsetMap</code> mencatat pergeseran indeks karakter asli ke teks teredaksi secara matematis. Hal ini memungkinkan visualisasi penyorotan bukti (<em>evidence highlighting</em>) pada dokumen asli di konsol rekruter tanpa pernah membocorkan identitas pribadi ke server LLM pihak ketiga.
      </p>
    </div>

    <div class="card">
      <h4>Tahap 4: Evidence Atomizer</h4>
      <p>
        Teks teredaksi diurai menjadi atom-atom bukti modular (<code>EvidenceAtom</code>). Setiap pengalaman kerja (<code>exp_1</code>, <code>exp_2</code>) dan butir peluru (bullet point) dipisah menjadi entitas independen yang memiliki hash konten dan referensi posisi. Atom-atom ini menjadi mata uang tunggal dalam proses evaluasi.
      </p>
    </div>

    <div class="card card-critic">
      <h4>Tahap 5: Profiler Agent & Capability Ontology Mapping</h4>
      <p>
        Profiler Agent (didukung oleh model <code>ag/gemini-3.8-flash-high</code>) membaca atom-atom bukti dan memetakannya ke taksonomi ontologi kemampuan:
      </p>
      <ul style="font-size: 8pt; margin-left: 10pt;">
        <li><strong>Alokasi Domain Karir:</strong> Menentukan apakah pengalaman kerja masuk kategori <code>backend_development</code>, <code>frontend_development</code>, <code>data_engineering</code>, dll.</li>
        <li><strong>Konsep Teknis (Ontology Concepts):</strong> Menghubungkan kata kunci ke graf relasi (contoh: <code>FastAPI</code> implies <code>Python</code>; <code>React</code> implies <code>Frontend</code>). Relasi ditelusuri di memori dan diverifikasi via PostgreSQL Recursive CTE.</li>
      </ul>
    </div>
  </div>

  <!-- ================= HALAMAN 4: GRAPH B (MATCHING & MULTI-MODEL CRITIC) ================= -->
  <div class="page">
    <h2>5. Rincian Teknis Graph B: Matching, Temporal Engine & Multi-Model Critic</h2>
    <p>
      Graph B dieksekusi saat proses penyaringan dijalankan. Fase ini mencocokkan kualifikasi lowongan kerja terhadap kandidat yang sudah terprofil:
    </p>

    <div class="card">
      <h4>Tahap 1: RequirementIR & Dekomposisi 5 Facets</h4>
      <p>
        Job Description dikompilasi menjadi representasi terstruktur (<code>RequirementSetIR</code>) yang terdiri dari 5 facet utama:
        1) <em>Role Experience Duration</em>, 2) <em>Core Framework/Language</em>, 3) <em>Architecture & Data</em>, 4) <em>Performance/Optimization</em>, dan 5) <em>Testing/Reliability</em>. Setiap facet memiliki bobot relatif dan kebijakan durasi yang tegas.
      </p>
    </div>

    <div class="card card-accent">
      <h4>Tahap 2: Temporal Engine (Weighted Calendar Union)</h4>
      <p>
        Alih-alih menyuruh AI menebak total tahun pengalaman, modul <code>weighted_union.py</code> menerapkan algoritma <em>sweep-line interval union</em>:
      </p>
      <pre><code># Konsep Algoritma Sweep-Line Calendar Union (Python Deterministik)
# Input: Daftar interval [start_date, end_date] per domain pekerjaan
# Output: Total bulan unik terakumulasi tanpa tumpang-tindih (anti double counting)
timeline = IntervalUnion([('2021-01', '2023-06'), ('2022-06', '2024-01')])
# Rentang tumpang-tindih (2022-06 s/d 2023-06) dihitung tepat 1 kali.
months_lo, months_hi, ledger = timeline.calculate_accumulated_months()</code></pre>
      <p style="font-size: 8pt;">
        Hasilnya adalah <code>month_ledger</code> absolut yang mencatat bulan-bulan aktif kandidat secara transparan.
      </p>
    </div>

    <div class="card">
      <h4>Tahap 3: Hybrid Search Retrieval (Vector HNSW + GIN FTS)</h4>
      <p>
        Untuk menemukan bukti pendukung yang relevan secara cepat, sistem menggabungkan pencarian semantik embedding <strong>microsoft/harrier-oss-v1-270m</strong> (640 dimensi) pada indeks HNSW pgvector dengan pencarian kata kunci teks penuh (GIN FTS) menggunakan formula <strong>Reciprocal Rank Fusion (RRF, k=60)</strong>.
      </p>
    </div>

    <div class="card card-accent">
      <h4>Tahap 4: Matcher Agent (Directional Reasoning dengan Kaidah R1)</h4>
      <p>
        Matcher Agent mengevaluasi kesesuaian atom terhadap kriteria facet. Sistem mewajibkan model mengisi field <code>analysis</code> (maksimal 60 token penalaran logis) SEBELUM menghasilkan keputusan enum <code>verdict</code> (<code>ENTAILED</code>, <code>PARTIAL</code>, <code>CONTRADICTED</code>, <code>ABSENT</code>). Pola ini memaksa model melakukan penalaran terarah dan mencegah <em>hallucinated jumping to conclusion</em>.
      </p>
    </div>

    <div class="card card-critic">
      <h4>Tahap 5: Multi-Model Critic Escalation (Claude Sonnet 5.5)</h4>
      <p>
        Jika salah satu dari 6 kondisi pemicu eskalasi aktif (<strong>E1: Borderline, E2: Kontradiksi, E3: Syarat Mutlak, E4: Keyword Stuffing, E5: Durasi Ambigu, E6: Teks Tersembunyi</strong>), sistem memicu Critic Agent:
      </p>
      <ul style="font-size: 8pt; margin-left: 10pt;">
        <li>Model Critic menggunakan keluarga model yang sepenuhnya berbeda: <strong>Claude Sonnet 5.5</strong> via 9Router.</li>
        <li>Critic mengaudit bukti atom pendukung secara independen tanpa mengetahui identitas kandidat.</li>
        <li><strong>Resolusi Perselisihan Konservatif:</strong> Jika Matcher dan Critic berselisih paham, sistem mengambil putusan yang paling konservatif untuk melindungi kualitas rekrutmen.</li>
      </ul>
    </div>
  </div>

  <!-- ================= HALAMAN 5: SCORER V2 & SPESIFIKASI TECH STACK ================= -->
  <div class="page">
    <h2>6. Scorer v2, Aturan Ranking & Tata Kelola Skor</h2>
    <p>
      Skor akhir kandidat dihitung menggunakan modul matematika deterministik <code>scorer_v2.py</code>, bebas dari intervensi bias model:
    </p>

    <div class="grid-2">
      <div class="card card-accent">
        <h4>A. Rubrik Kedalaman Penguasaan (Depth Rubric L0–L4)</h4>
        <p>Setiap evaluasi facet dinilai tingkat kedalamannya berdasarkan bukti nyata:</p>
        <ul style="font-size: 8pt; margin-left: 8pt;">
          <li><code>L0 (None):</code> Tidak ada bukti sama sekali (pengali: 0.0x).</li>
          <li><code>L1 (Awareness):</code> Hanya mengetahui konsep atau teori dasar (pengali: 0.25x).</li>
          <li><code>L2 (Application):</code> Mampu menggunakan dalam proyek di bawah supervisi (pengali: 0.60x).</li>
          <li><code>L3 (Proficiency):</code> Penguasaan mandiri, memecahkan masalah nyata (pengali: 1.00x).</li>
          <li><code>L4 (Mastery):</code> Merancang arsitektur, optimasi tingkat lanjut, mentoring (pengali: 1.15x).</li>
        </ul>
      </div>

      <div class="card card-critic">
        <h4>B. Pertahanan Anti-Keyword Stuffing (Penalti Tier T0)</h4>
        <p>Sistem memiliki gerbang proteksi bawaan terhadap manipulasi kata kunci:</p>
        <ul style="font-size: 8pt; margin-left: 8pt;">
          <li>Jika klaim kandidat hanya didukung oleh <strong>Atom Tier T0</strong> (hanya daftar keahlian tanpa narasi kontribusi proyek nyata), status verdict <strong>dikunci maksimal PARTIAL</strong>.</li>
          <li>Jumlah atom pendukung yang dihitung dibatasi maksimal 3 atom terkuat untuk mencegah penumpukan teks serupa.</li>
        </ul>
      </div>
    </div>

    <div class="card">
      <h4>C. Klasifikasi Kelulusan Band Deterministik</h4>
      <table style="margin-top: 2pt; font-size: 8pt;">
        <tr>
          <th>Band</th>
          <th>Rentang Skor</th>
          <th>Status Rekomendasi</th>
          <th>Kriteria Kelulusan</th>
        </tr>
        <tr>
          <td><strong style="color: #166534;">Band A</strong></td>
          <td>80.0 – 100.0</td>
          <td>Sangat Direkomendasikan (Top Candidate)</td>
          <td>Semua MUST_HAVE terpenuhi, durasi kerja valid, kedalaman rata-rata L3+.</td>
        </tr>
        <tr>
          <td><strong style="color: #1e40af;">Band B</strong></td>
          <td>65.0 – 79.9</td>
          <td>Memenuhi Syarat (Qualified)</td>
          <td>Semua MUST_HAVE terpenuhi, durasi kerja valid, beberapa aspek pada tingkat L2.</td>
        </tr>
        <tr>
          <td><strong style="color: #92400e;">Band C</strong></td>
          <td>50.0 – 64.9</td>
          <td>Dipertimbangkan (Borderline)</td>
          <td>Ada gap kompetensi minor, memerlukan tinjauan langsung oleh Hiring Manager.</td>
        </tr>
        <tr>
          <td><strong style="color: #991b1b;">Band R</strong></td>
          <td>&lt; 50.0</td>
          <td>Tidak Memenuhi Syarat (Under-Qualified)</td>
          <td>Gagal memenuhi syarat mutlak atau durasi pengalaman jauh di bawah standar.</td>
        </tr>
      </table>
    </div>

    <h2>7. Spesifikasi Lengkap Tech Stack & Ekosistem VPS</h2>
    <div class="grid-3">
      <div class="card">
        <h4>1. Backend Runtime</h4>
        <ul style="font-size: 7.5pt; margin-left: 8pt;">
          <li><strong>Python 3.12.3:</strong> Runtime modern dengan asyncio murni.</li>
          <li><strong>FastAPI 0.115:</strong> REST API dengan OpenAPI docs otomatis.</li>
          <li><strong>Pydantic v2.10:</strong> Validasi data ketat & serialisasi JSON instan.</li>
        </ul>
      </div>
      <div class="card">
        <h4>2. Database & Search</h4>
        <ul style="font-size: 7.5pt; margin-left: 8pt;">
          <li><strong>PostgreSQL 16:</strong> Database relasional ACID.</li>
          <li><strong>pgvector 0.8.7:</strong> HNSW Index (640-dimensi cosine similarity).</li>
          <li><strong>Alembic:</strong> Migrasi skema database versi 0001 s/d 0013.</li>
        </ul>
      </div>
      <div class="card">
        <h4>3. AI & Embedding Gateway</h4>
        <ul style="font-size: 7.5pt; margin-left: 8pt;">
          <li><strong>9Router Gateway:</strong> Gateway lokal port 20128.</li>
          <li><strong>microsoft/harrier-oss-v1-270m:</strong> Model embedding lokal.</li>
          <li><strong>Gemini 3.8 Flash & Claude Sonnet 5.5:</strong> Dual-model reasoning.</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- ================= HALAMAN 6: VERIFIKASI, DEPLOYMENT & PANDUAN API ================= -->
  <div class="page">
    <h2>8. Hasil Audit Kualitas Independen (QA Certification)</h2>
    <p>
      Sistem telah diaudit secara independen oleh agent verifikator (<strong>@sentinel</strong>) pada commit <code>87af2c3</code> dengan hasil pengujian sempurna:
    </p>

    <div class="card card-success">
      <h4>Ringkasan Hasil Verifikasi QA Sentinel:</h4>
      <ul style="font-size: 8pt; margin-left: 10pt;">
        <li>✅ <strong>90 dari 90 Automated Tests Lulus 100%</strong> (Unit tests, integration tests, E2E flow).</li>
        <li>✅ <strong>Problem 1 (Title Bias / Asymmetric Entailment):</strong> Lolos uji verifikasi independen.</li>
        <li>✅ <strong>Problem 2 (Fragmented Duration Accumulator):</strong> Lolos uji verifikasi kalender union.</li>
        <li>✅ <strong>Problem 3 (Hidden Text & Keyword Stuffing Defense):</strong> Lolos uji penetrasi data manipulatif.</li>
        <li>✅ <strong>Kerapihan Kode:</strong> <code>ruff check</code> & <code>ruff format</code> 100% bersih (0 error, 130 files).</li>
      </ul>
    </div>

    <h2>9. Status Deployment Produksi & Aksesibilitas</h2>
    <table style="font-size: 8pt;">
      <tr>
        <th style="width: 25%;">Komponen</th>
        <th>Detail Implementasi & Alamat Akses</th>
      </tr>
      <tr>
        <td><strong>Public HTTPS Endpoint</strong></td>
        <td><code>https://agentic-screening.rifqisetiawan.my.id</code> (Reverse proxy Caddy + Let's Encrypt SSL)</td>
      </tr>
      <tr>
        <td><strong>Internal Service VPS</strong></td>
        <td>Port <code>8111</code> via daemon Linux <code>systemd user service: cv-screening-agentic.service</code></td>
      </tr>
      <tr>
        <td><strong>Public Git Repository</strong></td>
        <td><code>https://github.com/Rifqi-Setiawan/screening_CV_AgenticAI.git</code> (Branch <code>main</code>)</td>
      </tr>
    </table>

    <h2>10. Panduan Penggunaan API (Quickstart cURL)</h2>
    <pre><code># Langkah 1: Login Recruiter dan simpan JWT Access Token
TOKEN=$(curl -s -X POST https://agentic-screening.rifqisetiawan.my.id/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"recruiter@rifqisetiawan.my.id","password":"[REDACTED]"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Langkah 2: Buat Lowongan Kerja Baru
JOB_ID=$(curl -s -X POST https://agentic-screening.rifqisetiawan.my.id/api/v1/jobs \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Senior Backend Engineer","jd_text":"Dibutuhkan Senior Backend Engineer dengan pengalaman Python dan PostgreSQL minimal 3 tahun."}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

# Langkah 3: Kompilasi Kualifikasi menjadi 5 Facets
curl -s -X POST https://agentic-screening.rifqisetiawan.my.id/api/v1/jobs/$JOB_ID/requirements/compile \
  -H "Authorization: Bearer $TOKEN"

# Langkah 4: Setujui (Approve) Requirements
curl -s -X POST https://agentic-screening.rifqisetiawan.my.id/api/v1/jobs/$JOB_ID/requirements/approve \
  -H "Authorization: Bearer $TOKEN"

# Langkah 5: Unggah CV Kandidat (Memicu Graph A: Visibility Gate, Atoms, Profiler)
curl -s -X POST https://agentic-screening.rifqisetiawan.my.id/api/v1/jobs/$JOB_ID/cvs \
  -H "Authorization: Bearer $TOKEN" -F "file=@/path/to/cv_candidate.pdf"

# Langkah 6: Jalankan Screening Run (Memicu Graph B: Matcher Gemini + Critic Claude)
RUN_ID=$(curl -s -X POST https://agentic-screening.rifqisetiawan.my.id/api/v1/jobs/$JOB_ID/screenings \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['screening_run_id'])")

# Langkah 7: Ambil Hasil Rekomendasi Ranking & Bukti Transparansi Evaluasi
curl -s -X GET https://agentic-screening.rifqisetiawan.my.id/api/v1/jobs/$JOB_ID/screenings/$RUN_ID/rankings \
  -H "Authorization: Bearer $TOKEN"</code></pre>

    <div style="margin-top: 8pt; text-align: center; border-top: 0.5pt solid #cbd5e1; padding-top: 6pt; font-size: 7.5pt; color: #64748b;">
      Buku Panduan & Dokumentasi Arsitektur Resmi Platform <strong>Agentic AI CV Screening & Candidate Ranking (v2.1)</strong>.<br>
      Hak Cipta © 2026 <strong>Muhammad Rifqi Setiawan</strong>. Seluruh hak cipta dilindungi undang-undang.
    </div>
  </div>

</body>
</html>
"""

html_path = OUTPUT_DIR / "panduan_agentic_screening.html"
html_path.write_text(html_content, encoding="utf-8")
print(f"HTML written to {html_path}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(f"file://{html_path}")
    page.wait_for_load_state("networkidle")
    page.pdf(
        path=str(OUTPUT_PDF),
        format="A4",
        print_background=True,
        margin={"top": "0mm", "bottom": "0mm", "left": "0mm", "right": "0mm"},
        display_header_footer=False,
    )
    browser.close()

print(f"PDF successfully generated at: {OUTPUT_PDF}")
size_kb = OUTPUT_PDF.stat().st_size / 1024
print(f"File size: {size_kb:.1f} KB")
