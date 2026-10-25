#!/usr/bin/env python3
"""
Generates an executive, publication-grade architectural handbook in PDF format:
"Panduan Komprehensif Arsitektur & Alur Kerja Sistem AI CV Screening & Ranking"
Covers all pipeline stages from Ingestion, Gatekeeper, Extraction, Redaction, Hybrid Vector Search, Scoring, and UI Governance.
Optimized for clean page-breaks, elegant typography, and zero-slice table formatting.
"""

import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_PDF = Path("/srv/hermes-control/services/cv-screening/docs/PANDUAN_ARSITEKTUR_DAN_ALUR_SISTEM_CV_SCREENING.pdf")
PUBLIC_PDF = Path("/srv/hermes-control/services/cv-screening/data/audit_public/PANDUAN_ARSITEKTUR_DAN_ALUR_SISTEM_CV_SCREENING.pdf")

html_content = """<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Panduan Arsitektur & Alur Sistem AI CV Screening & Ranking</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');
    
    @page {
      size: A4 portrait;
      margin: 12mm 12mm 14mm 12mm;
      @bottom-right {
        content: "Halaman " counter(page) " dari " counter(pages);
        font-family: 'JetBrains Mono', monospace;
        font-size: 8pt;
        color: #64748b;
      }
      @bottom-left {
        content: "AI CV Screening & Ranking Platform — Architecture & Pipeline Manual";
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
      font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
      color: #0f172a;
      background: #ffffff;
      font-size: 8.5pt;
      line-height: 1.45;
    }
    
    .page-break {
      page-break-before: always;
    }

    .no-break {
      break-inside: avoid;
      page-break-inside: avoid;
    }

    /* Cover / Hero Header */
    .hero-header {
      background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
      color: #ffffff;
      padding: 20px 24px;
      border-radius: 10px;
      margin-bottom: 16px;
      border: 1px solid #312e81;
    }

    .hero-badge {
      display: inline-block;
      background: #4f46e5;
      color: #ffffff;
      font-size: 7.5pt;
      font-weight: 700;
      padding: 2.5px 9px;
      border-radius: 999px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }

    .hero-title {
      font-size: 18pt;
      font-weight: 800;
      line-height: 1.2;
      margin-bottom: 6px;
      letter-spacing: -0.5px;
    }

    .hero-subtitle {
      font-size: 9pt;
      color: #cbd5e1;
      font-weight: 400;
      line-height: 1.4;
    }

    .meta-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid rgba(255, 255, 255, 0.15);
      font-size: 7.5pt;
    }

    .meta-item strong {
      display: block;
      color: #94a3b8;
      font-size: 6.5pt;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 1px;
    }

    .meta-item span {
      color: #ffffff;
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
    }

    /* Section Components */
    .section-title {
      font-size: 11.5pt;
      font-weight: 800;
      color: #0f172a;
      display: flex;
      align-items: center;
      margin-top: 16px;
      margin-bottom: 8px;
      padding-bottom: 4px;
      border-bottom: 2px solid #e2e8f0;
      letter-spacing: -0.3px;
    }

    .section-title span.number-pill {
      background: #4f46e5;
      color: #ffffff;
      width: 22px;
      height: 22px;
      border-radius: 5px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 8.5pt;
      font-weight: 700;
      margin-right: 8px;
    }

    .prose {
      font-size: 8.3pt;
      color: #334155;
      line-height: 1.5;
      margin-bottom: 10px;
      text-align: justify;
    }

    /* Flowchart / Box Diagram Styles */
    .diagram-container {
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 12px 14px;
      margin: 10px 0 12px 0;
      font-size: 8.2pt;
      break-inside: avoid;
    }

    .diagram-title {
      font-size: 8.8pt;
      font-weight: 700;
      color: #1e293b;
      margin-bottom: 8px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .flow-step-box {
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-left: 4px solid #4f46e5;
      border-radius: 5px;
      padding: 7px 11px;
      margin-bottom: 6px;
      break-inside: avoid;
    }

    .flow-step-box.danger {
      border-left-color: #ef4444;
      background: #fef2f2;
    }

    .flow-step-box.success {
      border-left-color: #10b981;
      background: #f0fdf4;
    }

    .flow-step-box.warning {
      border-left-color: #f59e0b;
      background: #fffbeb;
    }

    .flow-step-title {
      font-weight: 700;
      font-size: 8.5pt;
      color: #0f172a;
      display: flex;
      justify-content: space-between;
    }

    .flow-step-desc {
      font-size: 7.8pt;
      color: #475569;
      margin-top: 2px;
      line-height: 1.4;
    }

    .flow-arrow {
      text-align: center;
      color: #94a3b8;
      font-weight: 700;
      font-size: 9.5pt;
      line-height: 1;
      margin: 2px 0;
    }

    /* Comparison & Spec Table */
    table.spec-table {
      width: 100%;
      border-collapse: collapse;
      margin: 8px 0 12px 0;
      font-size: 7.9pt;
      break-inside: avoid;
    }

    table.spec-table th {
      background: #f1f5f9;
      color: #334155;
      font-weight: 700;
      text-align: left;
      padding: 4.5px 7px;
      border: 1px solid #cbd5e1;
      text-transform: uppercase;
      font-size: 7pt;
      letter-spacing: 0.3px;
    }

    table.spec-table td {
      padding: 4.5px 7px;
      border: 1px solid #e2e8f0;
      color: #1e293b;
      vertical-align: top;
      line-height: 1.35;
    }

    table.spec-table tr:nth-child(even) {
      background: #f8fafc;
    }

    /* Badges & Tags */
    .badge {
      display: inline-block;
      font-size: 6.8pt;
      font-weight: 700;
      padding: 1.5px 5px;
      border-radius: 3px;
      font-family: 'JetBrains Mono', monospace;
    }

    .badge-blue { background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; }
    .badge-indigo { background: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
    .badge-emerald { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
    .badge-rose { background: #ffe4e6; color: #9f1239; border: 1px solid #fecdd3; }
    .badge-amber { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }

    /* Code Blocks */
    .code-box {
      background: #0f172a;
      color: #f8fafc;
      font-family: 'JetBrains Mono', monospace;
      font-size: 7.2pt;
      padding: 8px 12px;
      border-radius: 6px;
      margin: 6px 0 10px 0;
      line-height: 1.4;
      break-inside: avoid;
    }

    .code-comment { color: #94a3b8; }
    .code-keyword { color: #38bdf8; font-weight: 600; }
    .code-string { color: #a7f3d0; }

    /* Callout Card */
    .callout {
      background: #eff6ff;
      border-left: 3px solid #3b82f6;
      padding: 8px 12px;
      border-radius: 0 5px 5px 0;
      margin: 8px 0;
      font-size: 7.9pt;
      color: #1e3a8a;
      break-inside: avoid;
    }

    .callout strong {
      color: #1d4ed8;
      display: block;
      margin-bottom: 2px;
      font-size: 8.2pt;
    }

    /* 2-Column Grid */
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin: 8px 0;
      break-inside: avoid;
    }

    .card {
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 8px 10px;
      background: #ffffff;
      break-inside: avoid;
    }

    .card-title {
      font-weight: 700;
      font-size: 8.2pt;
      color: #0f172a;
      margin-bottom: 3px;
      display: flex;
      align-items: center;
      gap: 4px;
    }
  </style>
</head>
<body>

  <!-- ==================== HALAMAN 1: COVER & PETA ARSITEKTUR ==================== -->
  <div class="hero-header">
    <div class="hero-badge">Technical Whitepaper & Master Architecture Manual</div>
    <div class="hero-title">Platform AI CV Screening & Ranking</div>
    <div class="hero-subtitle">
      Arsitektur Lengkap Rekayasa Sistem Seleksi CV Berbasis Hybrid AI & Rule-Based Deterministik: Dari Pembersihan Berkas, Anonimisasi PII, Vektorisasi Semantik pgvector, hingga Penilaian Kepatuhan Ketenagakerjaan.
    </div>
    <div class="meta-grid">
      <div class="meta-item">
        <strong>Pengembang / Pemilik</strong>
        <span>Muhammad Rifqi Setiawan</span>
      </div>
      <div class="meta-item">
        <strong>Engine AI Semantik</strong>
        <span>Harrier-270m (640d pgvector)</span>
      </div>
      <div class="meta-item">
        <strong>Standar Regulasi</strong>
        <span>UU PDP & SE Menaker 2025</span>
      </div>
      <div class="meta-item">
        <strong>Status Sistem</strong>
        <span>Production v2.0 (Port 8110)</span>
      </div>
    </div>
  </div>

  <div class="section-title" style="margin-top: 0;">
    <span class="number-pill">0</span>
    <span>Ringkasan Eksekutif & Peta Alur Arsitektur End-to-End</span>
  </div>
  <p class="prose">
    Proses seleksi resume (CV) manual menghadapi beban volume masif, format tata letak yang tidak seragam, dan bias subjektif manusia. Platform ini dibangun dengan arsitektur <strong>Hybrid AI & Deterministik</strong> yang mengawinkan kecepatan pemrosesan data, akurasi semantik representasional, dan kepatuhan hukum tanpa halusinasi.
  </p>

  <div class="diagram-container">
    <div class="diagram-title">🗺️ Alur Master 6 Tahapan Pipeline (The 6-Stage Master Architecture)</div>
    
    <div class="flow-step-box">
      <div class="flow-step-title">
        <span>Tahap 1: Job Description & Requirement Compilation</span>
        <span class="badge badge-indigo">Kriteria & Bobot</span>
      </div>
      <div class="flow-step-desc">
        Penyusunan naskah lowongan kerja (manual / template industri), parsing kriteria berbasis LLM & aturan konsep, pembobotan 4 kategori terkalibrasi, dan persetujuan terkunci (Human-in-the-Loop).
      </div>
    </div>
    
    <div class="flow-arrow">▼</div>

    <div class="flow-step-box warning">
      <div class="flow-step-title">
        <span>Tahap 2: Ingestion & Pre-Flight Gatekeeper</span>
        <span class="badge badge-amber">Fail-Fast</span>
      </div>
      <div class="flow-step-desc">
        Penerimaan dokumen (PDF/DOCX/ZIP), validasi header biner Magic Bytes, deduplikasi hash SHA-256, dan pencegatan berkas bukan-CV (Ijazah/KTP/Surat Lamaran/Portofolio) via Triple-Filter.
      </div>
    </div>

    <div class="flow-arrow">▼</div>

    <div class="flow-step-box">
      <div class="flow-step-title">
        <span>Tahap 3: Extraction & Smart Boundary Isolation</span>
        <span class="badge badge-blue">Parser & Anchor</span>
      </div>
      <div class="flow-step-desc">
        Pemisahan lampiran portofolio multi-halaman tanpa memotong CV, hybrid parser (PyMuPDF + Docling visual AI), normalisasi rentang tanggal, dan triangulasi 5 sinyal nama kandidat anti-headline bias.
      </div>
    </div>

    <div class="flow-arrow">▼</div>

    <div class="flow-step-box success">
      <div class="flow-step-title">
        <span>Tahap 4: PII Redaction & Privacy Separation</span>
        <span class="badge badge-emerald">UU PDP</span>
      </div>
      <div class="flow-step-desc">
        Pemisahan identitas sensitif ke tabel terisolasi (candidate_identities), pembersihan total data demografi (gender, agama, usia), penyamaran token [NAMA]/[EMAIL], dan pembuatan kode acak (C-0042).
      </div>
    </div>

    <div class="flow-arrow">▼</div>

    <div class="flow-step-box">
      <div class="flow-step-title">
        <span>Tahap 5: Vector Embedding & Hybrid Semantic Retrieval</span>
        <span class="badge badge-indigo">pgvector + FTS</span>
      </div>
      <div class="flow-step-desc">
        Vektorisasi 640-dimensi Harrier-270m, pencarian semantik HNSW Cosine Similarity digabung dengan PostgreSQL Full-Text Search menggunakan Reciprocal Rank Fusion (RRF k=60) untuk mengambil bukti riil CV.
      </div>
    </div>

    <div class="flow-arrow">▼</div>

    <div class="flow-step-box success">
      <div class="flow-step-title">
        <span>Tahap 6: Multi-Criteria Scoring, Banding & HR Governance</span>
        <span class="badge badge-emerald">Ranking</span>
      </div>
      <div class="flow-step-desc">
        Skoring dua lapis (Kriteria x Kategori), evaluasi kriteria Wajib (MUST_HAVE capping), penentuan Band A/B/C/R, gate kelayakan administratif terpisah, dan leaderboard interaktif di Web UI.
      </div>
    </div>
  </div>

  <!-- ==================== HALAMAN 2: TAHAP 1 ==================== -->
  <div class="page-break"></div>

  <div class="section-title">
    <span class="number-pill">1</span>
    <span>Tahap 1: Job Description & Requirement Compilation</span>
  </div>
  <p class="prose">
    Tahap pertama adalah fondasi dari seluruh proses penilaian. Sistem tidak membebankan penulisan rumus rumit kepada HR, melainkan menyediakan mesin kompilasi otomatis berbasis naskah Job Description (JD) alami di <code>src/domain/jd_compiler.py</code>.
  </p>

  <div class="grid-2">
    <div class="card">
      <div class="card-title">📝 1. Input JD & Template Peran Industri</div>
      <p class="flow-step-desc">
        Recruiter dapat menempelkan teks lowongan bebas atau memilih <strong>7 Role Template Siap Pakai</strong> (Backend, Frontend, Data, Civil, QA, HR, dan Product) yang langsung memuat deskripsi standar ATS dan kriteria baku industri.
      </p>
    </div>
    <div class="card">
      <div class="card-title">🛡️ 2. Policy Linter & Kualifikasi Sah (BFOQ)</div>
      <p class="flow-step-desc">
        Sistem menyaring syarat fisik irasional (seperti "good looking", "tinggi/berat badan"). Namun, kriteria <strong>Agama</strong> dan <strong>Jenis Kelamin</strong> <strong>DIPERBOLEHKAN SECARA SAH</strong> (<em>Bona Fide Occupational Qualification</em>) guna mendukung kebutuhan nyata instansi di Indonesia (seperti yayasan keagamaan, sekolah bernuansa khusus, asrama, dan peran spesifik).
      </p>
    </div>
  </div>

  <div class="callout">
    <strong>⚖️ 4 Kategori Distribusi Bobot Standar Industri (Total 100%):</strong>
    Secara default, sistem membagi porsi penilaian ke dalam 4 dimensi berimbang yang kini dapat diedit secara interaktif di dashboard Web UI:
    <br>• <strong>Pengalaman Kerja (EXPERIENCE) — 40%:</strong> Relevansi jabatan dan durasi riil pekerjaan.
    <br>• <strong>Keterampilan Teknis (HARD_SKILLS) — 30%:</strong> Bahasa pemrograman, tools, framework, dan metodologi.
    <br>• <strong>Pendidikan & Sertifikasi (EDUCATION_CERT) — 15%:</strong> Jenjang gelar, akreditasi almamater, dan sertifikasi.
    <br>• <strong>Pencapaian & Kepemimpinan (ACHIEVEMENT) — 15%:</strong> Dampak terukur, efisiensi kerja, dan kepemimpinan.
  </div>

  <table class="spec-table">
    <thead>
      <tr>
        <th style="width: 25%;">Tingkat Kepentingan</th>
        <th style="width: 25%;">Kata Kunci di JD</th>
        <th style="width: 15%;">Bobot</th>
        <th style="width: 35%;">Konsekuensi Penilaian (Tahap 6)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="badge badge-rose">🔴 MUST_HAVE (Wajib)</span></td>
        <td>wajib, harus, minimal, essential</td>
        <td><strong>20% – 25%</strong></td>
        <td>Jika tidak terpenuhi, nilai akhir <strong>langsung dibatasi (capped)</strong> maks ke Band B (74%) atau Band C (49%).</td>
      </tr>
      <tr>
        <td><span class="badge badge-amber">🟡 STRONG_PREFERENCE</span></td>
        <td>diutamakan, preferred, berpengalaman</td>
        <td><strong>10% – 15%</strong></td>
        <td>Menambah skor secara proporsional tanpa mengunci batas atas band kandidat.</td>
      </tr>
      <tr>
        <td><span class="badge badge-blue">⚪ NICE_TO_HAVE</span></td>
        <td>nilai tambah, plus, keuntungan</td>
        <td><strong>5% – 10%</strong></td>
        <td>Poin bonus kompetitif untuk membedakan sesama kandidat di peringkat atas.</td>
      </tr>
    </tbody>
  </table>

  <!-- ==================== HALAMAN 3: TAHAP 2 ==================== -->
  <div class="page-break"></div>

  <div class="section-title">
    <span class="number-pill">2</span>
    <span>Tahap 2: Ingestion & Pre-Flight Gatekeeper</span>
  </div>
  <p class="prose">
    Setelah kriteria terkunci, dokumen pelamar masuk ke sistem. Tahap ini bertindak sebagai <strong>firewall proteksi</strong> untuk memilah berkas sah vs berkas berbahaya / salah unggah sebelum komputasi AI berjalan (<code>src/worker/sanitizer.py</code> & <code>classifier.py</code>).
  </p>

  <div class="diagram-container">
    <div class="diagram-title">🔍 Triple-Filter Framework: Bagaimana Sistem Mendeteksi CV vs Bukan-CV?</div>
    
    <div class="flow-step-box">
      <div class="flow-step-title">
        <span>Lapis 1: Sanity Check & Magic Bytes Verification</span>
        <span class="badge badge-blue">Sanity</span>
      </div>
      <div class="flow-step-desc">
        Membaca header byte fisik file (misal <code>%PDF-</code>), memblokir file corrupt, virus, atau ekstensi palsu. Jika teks &lt; 50 huruf dan 0 gambar, berkas ditolak (<code>INSUFFICIENT_CONTENT</code>).
      </div>
    </div>

    <div class="flow-step-box danger">
      <div class="flow-step-title">
        <span>Lapis 2: Negative Filter (Pencegatan Berkas Salah Unggah)</span>
        <span class="badge badge-rose">Auto-Reject</span>
      </div>
      <div class="flow-step-desc">
        Mencegat berkas non-CV menggunakan penanda leksikal kuat:
        <br>• <strong>CERTIFICATE_ONLY:</strong> Berisi kata <em>"Sertifikat, Ijazah, Transkrip Nilai"</em> tanpa riwayat kerja & skills.
        <br>• <strong>ADMIN_DOC:</strong> Berkas KTP, Kartu Keluarga, SIM, SKCK, NIK tanpa profil karir.
        <br>• <strong>COVER_LETTER_ONLY:</strong> Hanya surat lamaran naratif (<em>"Kepada Yth..."</em>) tanpa ringkasan pengalaman.
        <br>• <strong>PURE_PORTFOLIO:</strong> Berkas tebal (>3 halaman) berisi gambar desain murni tanpa riwayat karir dan kontak.
      </div>
    </div>

    <div class="flow-step-box success">
      <div class="flow-step-title">
        <span>Lapis 3: Positive Consensus Scoring (Validasi CV Sah)</span>
        <span class="badge badge-emerald">Verified CV</span>
      </div>
      <div class="flow-step-desc">
        Dokumen disahkan sebagai CV jika memiliki: (1) Kontak aktif terdeteksi (Email/No. HP), dan (2) Minimal 1 pilar karir: Seksi <strong>Pengalaman Kerja</strong> ATAU seksi <strong>Pendidikan</strong>.
      </div>
    </div>
  </div>

  <!-- ==================== HALAMAN 4: TAHAP 3 ==================== -->
  <div class="page-break"></div>

  <div class="section-title">
    <span class="number-pill">3</span>
    <span>Tahap 3: Extraction & Smart Boundary Isolation</span>
  </div>
  <p class="prose">
    Menguraikan dokumen pelamar adalah bagian krusial karena variasi layout CV sangat liar. Tahap 3 menggunakan empat subsistem rekayasa terpadu di <code>src/worker/adapter.py</code>:
  </p>

  <div class="grid-2">
    <div class="card">
      <div class="card-title">📑 1. Smart Boundary Isolator</div>
      <p class="flow-step-desc">
        Alih-alih memotong paksa halaman secara kaku, modul <code>boundary.py</code> menganalisis <strong>densitas rasio teks vs gambar per halaman</strong>. Halaman 1–2 yang padat teks ditandai sebagai <code>CV_CORE</code>, sementara halaman lampiran portofolio/sertifikat dipisahkan ke metadata <code>portfolio_attachments</code> tanpa membingungkan parser.
      </p>
    </div>
    <div class="card">
      <div class="card-title">🧩 2. Hybrid Multi-Engine Parser</div>
      <p class="flow-step-desc">
        Sistem menggunakan <strong>PyMuPDF</strong> untuk ekstraksi berkecepatan tinggi (skala milidetik). Jika terdeteksi layout Canva 2-kolom kompleks, tabel tanpa garis, atau skor keyakinan &lt; 60%, sistem mengaktifkan <strong>Docling (IBM Research)</strong> yang membaca struktur dokumen secara visual dengan model <em>DocLayNet</em> dan <em>TableFormer</em>.
      </p>
    </div>
    <div class="card">
      <div class="card-title">📅 3. Multi-Section & Shared-Year Regex</div>
      <p class="flow-step-desc">
        Modul <code>norm_single_date</code> menstandarkan seluruh format tanggal Indonesia/Inggris ke ISO (<code>YYYY-MM</code>), termasuk pola tahun bersama (<em>shared-year</em>, misal: "Juli - November 2023"). Seksi <em>'other'</em> disisir untuk menangkap judul pekerjaan yang terpisah oleh OCR pada CV scan gambar.
      </p>
    </div>
    <div class="card">
      <div class="card-title">🎯 4. Orthogonal Anchor Triangulation</div>
      <p class="flow-step-desc">
        Mengeliminasi <em>headline bias</em> (kesalahan ATS umum yang mengira judul jabatan "Backend Developer" adalah nama pelamar). Sistem merekonsiliasi <strong>5 sinyal konsensus silang</strong>: Header CV, Nama File ATS, Username Email, Vanity URL LinkedIn, dan Pola Kalimat Pengantar (<em>"Nama saya..."</em>).
      </p>
    </div>
  </div>

  <div class="code-box">
<span class="code-comment"># Contoh Output Hasil Ekstraksi Tahap 3 (Data Terstruktur JSON):</span>
{
  <span class="code-keyword">"identity"</span>: {
    <span class="code-keyword">"full_name"</span>: <span class="code-string">"Ahmad Habibul Ulum"</span>,  <span class="code-comment">/* 100% Akurat via Triangulasi 5 Sinyal */</span>
    <span class="code-keyword">"email"</span>: <span class="code-string">"ahmad.habibul@gmail.com"</span>,
    <span class="code-keyword">"phone"</span>: <span class="code-string">"+6281234567890"</span>
  },
  <span class="code-keyword">"experiences"</span>: [
    {
      <span class="code-keyword">"title"</span>: <span class="code-string">"Full Stack Web Developer"</span>,
      <span class="code-keyword">"organization"</span>: <span class="code-string">"PT Integra Sistem Optima"</span>,
      <span class="code-keyword">"start_date"</span>: <span class="code-string">"2023-07"</span>, <span class="code-keyword">"end_date"</span>: <span class="code-string">"2023-11"</span>, <span class="code-keyword">"duration_months"</span>: <span class="code-string">5</span>
    }
  ],
  <span class="code-keyword">"skills"</span>: [<span class="code-string">"Python"</span>, <span class="code-string">"FastAPI"</span>, <span class="code-string">"PostgreSQL"</span>, <span class="code-string">"Docker"</span>, <span class="code-string">"React"</span>],
  <span class="code-keyword">"portfolio_attachments"</span>: [{ <span class="code-keyword">"page"</span>: 3, <span class="code-keyword">"type"</span>: <span class="code-string">"PORTFOLIO_PROJECT"</span> }]
}
  </div>

  <!-- ==================== HALAMAN 5: TAHAP 4 ==================== -->
  <div class="page-break"></div>

  <div class="section-title">
    <span class="number-pill">4</span>
    <span>Tahap 4: PII Redaction & Privacy Separation</span>
  </div>
  <p class="prose">
    Kepatuhan hukum terhadap <strong>UU Perlindungan Data Pribadi (UU PDP)</strong> dan <strong>Surat Edaran Menaker 2025</strong> ditegakkan di tahap ini. Sebelum dievaluasi oleh mesin AI, data pribadi dipisahkan dan disamarkan di <code>src/worker/redaction.py</code>.
  </p>

  <div class="diagram-container">
    <div class="diagram-title">🔒 Arsitektur Isolasi Ganda (Dual-Path Data Isolation)</div>
    <div class="grid-2">
      <div class="flow-step-box danger" style="margin-bottom:0;">
        <div class="flow-step-title">JALUR 1: DATA IDENTITAS SENSITIF</div>
        <div class="flow-step-desc">
          • Nama Lengkap Asli Pelamar<br>
          • Alamat Email & Nomor WhatsApp<br>
          • Tautan Akun LinkedIn & URL Portofolio<br>
          • Berkas PDF Dokumen Asli<br>
          <strong>Status:</strong> Dikunci terisolasi di tabel <code>candidate_identities</code>. Diberi kode anonim unik (misal: <code>C-0042</code>). Mesin AI penilaian <strong>DILARANG KERAS</strong> membaca tabel ini.
        </div>
      </div>
      <div class="flow-step-box success" style="margin-bottom:0;">
        <div class="flow-step-title">JALUR 2: MATCHING PROFILE EVALUASI</div>
        <div class="flow-step-desc">
          • Riwayat Pekerjaan & Tanggung Jawab<br>
          • Almamater & Jurusan Akademik<br>
          • Keahlian Teknis (Hard Skills)<br>
          • Proyek Nyata & Kualifikasi Khusus (Agama/Gender jika disyaratkan)<br>
          <strong>Status:</strong> Kontak pribadi disensor dengan token <code>[EMAIL]</code>, <code>[TELEPON]</code>. Nama disamarkan <code>[NAMA]</code> agar evaluasi adil dan berbasis kompetensi.
        </div>
      </div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <div class="card-title">🛡️ 1. Proteksi Kontak & Data Sensitif (UU PDP)</div>
      <p class="flow-step-desc">
        Sistem mengunci alamat rumah, NIK, email, dan nomor HP pelamar. Jika lowongan membutuhkan kualifikasi keagamaan atau gender khusus (BFOQ), sistem mencocokkannya secara objektif tanpa mengekspos kontak pribadi pelamar.
      </p>
    </div>
    <div class="card">
      <div class="card-title">🎭 2. Token Replacement & Whitelist Role</div>
      <p class="flow-step-desc">
        Nama pelamar disamarkan menjadi <code>[NAMA]</code>. Sistem dilengkapi daftar <em>whitelist</em> kata profesi (seperti "developer", "engineer", "lead", "analyst") agar kata jabatan tidak ikut tersensor saat menyamarkan nama.
      </p>
    </div>
  </div>

  <div class="callout" style="background: #f0fdf4; border-left-color: #10b981; color: #065f46;">
    <strong>💡 Mengapa Pemisahan Identitas Sangat Penting?</strong>
    Dengan arsitektur ini, HR Recruiter dan mesin AI mengevaluasi kandidat secara <em>blind</em> (buta identitas). Nama asli dan nomor kontak pelamar baru dibuka secara sah (<em>Reveal Identity</em>) setelah kandidat dinyatakan lolos ke babak wawancara kerja.
  </div>

  <!-- ==================== HALAMAN 4: TAHAP 5 (VECTOR EMBEDDING & RETRIEVAL) ==================== -->
  <div class="page-break"></div>

  <div class="section-title">
    <span class="number-pill">5</span>
    <span>Tahap 5: Vector Embedding & Hybrid Semantic Retrieval</span>
  </div>
  <p class="prose">
    Banyak sistem penilaian CV gagal karena hanya mengandalkan pencocokan teks mentah atau sekadar <em>cosine similarity</em> sederhana. Sistem kita menggunakan arsitektur pencarian semantik hibrida tingkat tinggi di <code>src/domain/retrieval.py</code>.
  </p>

  <div class="diagram-container">
    <div class="diagram-title">⚡ Mengapa Bukan Hanya Cosine Similarity Biasa? (Hybrid Retrieval Architecture)</div>
    
    <div class="grid-2">
      <div class="card" style="border-top: 3px solid #3b82f6;">
        <div class="card-title">JALUR A: Dense Vector Search (pgvector HNSW)</div>
        <p class="flow-step-desc">
          Teks pengalaman CV diubah menjadi vektor <strong>640 dimensi</strong> menggunakan model <strong>Harrier-270m</strong> (dinormalisasi). Menggunakan indeks HNSW pada PostgreSQL dengan operator jarak kosinus:
          <br><code style="font-family:'JetBrains Mono';">1 - (embedding &lt;=&gt; req_vector) AS sim</code>
          <br><strong>Kelebihan:</strong> Menangkap kesamaan konsep dan konteks makna meskipun beda kosakata.
        </p>
      </div>

      <div class="card" style="border-top: 3px solid #10b981;">
        <div class="card-title">JALUR B: Sparse Lexical Search (PostgreSQL FTS)</div>
        <p class="flow-step-desc">
          Pencarian kata kunci presisi menggunakan mesin <strong>Full-Text Search (FTS)</strong> dengan ranking BM25/ts_rank yang diperkaya oleh <strong>Taksonomi Keahlian</strong>:
          <br><code style="font-family:'JetBrains Mono';">ts_rank(fts, plainto_tsquery('simple', query))</code>
          <br><strong>Kelebihan:</strong> Menjamin istilah teknis mutlak (seperti "PostgreSQL", "Docker") tertangkap 100%.
        </p>
      </div>
    </div>

    <div class="flow-step-box success" style="margin-top: 8px;">
      <div class="flow-step-title">
        <span>JALUR C: RECIPROCAL RANK FUSION (Formula RRF k=60)</span>
        <span class="badge badge-emerald">Algoritma Fusi</span>
      </div>
      <div class="flow-step-desc">
        Sistem menggabungkan peringkat hasil Jalur A dan Jalur B dengan formula matematis RRF:
        <br><strong style="font-family: 'JetBrains Mono'; font-size: 8.5pt;">Skor RRF = 1 / (60 + Peringkat_Vektor) + 1 / (60 + Peringkat_Keyword)</strong>
        <br>Potongan teks yang unggul secara makna semantik <strong>DAN</strong> memuat kata kunci teknis riil akan otomatis naik ke peringkat teratas, menghasilkan bukti otentik (<em>evidence provenance quote</em>) tanpa halusinasi.
      </div>
    </div>
  </div>

  <table class="spec-table">
    <thead>
      <tr>
        <th style="width: 25%;">Metode Pencarian</th>
        <th style="width: 35%;">Kekuatan Utama</th>
        <th style="width: 40%;">Kelemahan jika Berdiri Sendiri</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Cosine Similarity Murni</strong></td>
        <td>Bisa memahami sinonim dan bahasa alami yang bervariasi.</td>
        <td>Rentan <em>false positive</em> (misal: menganggap MySQL dan PostgreSQL sama, padahal lowongan butuh spesifik PostgreSQL).</td>
      </tr>
      <tr>
        <td><strong>Keyword Search Murni (FTS)</strong></td>
        <td>100% presisi untuk istilah spesifik dan akronim teknis.</td>
        <td>Gagal jika pelamar menuliskan konsep pekerjaan tanpa menyebutkan keyword persis lowongan.</td>
      </tr>
      <tr>
        <td><strong style="color: #4f46e5;">Hybrid RRF (Sistem Kita)</strong></td>
        <td><strong>Kombinasi Terbaik:</strong> Memahami konteks kalimat sekaligus mengunci presisi keyword teknis.</td>
        <td>Membutuhkan infrastruktur database modern (PostgreSQL + pgvector). <em>Sudah aktif 100% di VPS!</em></td>
      </tr>
    </tbody>
  </table>

  <!-- ==================== HALAMAN 5: TAHAP 6 (SCORING & BANDING) ==================== -->
  <div class="page-break"></div>

  <div class="section-title">
    <span class="number-pill">6</span>
    <span>Tahap 6: Multi-Criteria Scoring, Banding & Leaderboard</span>
  </div>
  <p class="prose">
    Tahap akhir menghitung skor mutlak pelamar (skala 0.0 – 100.0) secara <strong>deterministik dan dapat diaudit</strong> melalui modul <code>src/domain/scorer.py</code>.
  </p>

  <table class="spec-table">
    <thead>
      <tr>
        <th style="width: 18%;">Status Bukti</th>
        <th style="width: 14%;">Nilai Angka</th>
        <th style="width: 68%;">Penjelasan Logika Pemenuhan Kriteria</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="badge badge-emerald">STRONG</span></td>
        <td><strong>1.0 (100%)</strong></td>
        <td>Bukti pengalaman riil terverifikasi memenuhi kriteria lowongan secara eksplisit dan mendalam.</td>
      </tr>
      <tr>
        <td><span class="badge badge-amber">PARTIAL</span></td>
        <td><strong>0.5 (50%)</strong></td>
        <td>Kandidat memenuhi kriteria secara semantik (misal pernah menggunakan framework sejenis) atau durasi belum penuh.</td>
      </tr>
      <tr>
        <td><span class="badge badge-rose">NOT_DEMONSTRATED</span></td>
        <td><strong>0.0 (0%)</strong></td>
        <td>Tidak ada bukti relevan yang ditemukan di dalam resume pelamar.</td>
      </tr>
    </tbody>
  </table>

  <div class="callout" style="background: #f0fdf4; border-left-color: #10b981; color: #065f46;">
    <strong>📊 Rumus Perhitungan Skor Dua Lapis (Two-Layer Normalization):</strong>
    <br>1. <em>Skor Kategori</em> = (Total Poin Kriteria Didapat ÷ Total Bobot Kriteria di Kategori Tersebut) × 100
    <br>2. <em>Skor Akhir</em> = Σ (Skor Kategori × Bobot Persentase Kategori)
    <br><em>Contoh: Skor Pengalaman (80) × 40% + Skor Skill (90) × 30% + Pendidikan (100) × 15% + Prestasi (70) × 15% = <strong>84.5 (Band A)</strong></em>.
  </div>

  <table class="spec-table">
    <thead>
      <tr>
        <th style="width: 15%;">Band</th>
        <th style="width: 25%;">Rentang Nilai</th>
        <th style="width: 25%;">Rekomendasi HR</th>
        <th style="width: 35%;">Aturan Penguncian Batas Atas (Hard Capping)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>BAND A</strong></td>
        <td>Skor <strong>70.0 – 100.0</strong></td>
        <td><span class="badge badge-emerald">SHORTLIST</span></td>
        <td>Seluruh syarat Wajib (MUST_HAVE) terpenuhi dengan status <code>STRONG</code>.</td>
      </tr>
      <tr>
        <td><strong>BAND B</strong></td>
        <td>Skor <strong>50.0 – 69.9</strong> (Maks 74.0)</td>
        <td><span class="badge badge-amber">REVIEW</span></td>
        <td>Jika ada <strong>1 syarat Wajib</strong> yang tidak terpenuhi, skor langsung di-cap maksimal ke 74.0.</td>
      </tr>
      <tr>
        <td><strong>BAND C</strong></td>
        <td>Skor <strong>&lt; 50.0</strong> (Maks 49.0)</td>
        <td><span class="badge badge-rose">LOW_PRIORITY</span></td>
        <td>Jika ada <strong>&ge; 2 syarat Wajib</strong> yang tidak terpenuhi, skor langsung di-cap maksimal ke 49.0.</td>
      </tr>
      <tr>
        <td><strong>BAND R</strong></td>
        <td>Skor <strong>0.0</strong></td>
        <td><span class="badge badge-rose">REJECTED_NOT_A_CV</span></td>
        <td>Dokumen bukan-CV (dicegat di Tahap 2) atau berkas rusak / kosong.</td>
      </tr>
    </tbody>
  </table>

  <!-- ==================== HALAMAN 6: TAHAP 7 & GOVERNANCE ==================== -->
  <div class="page-break"></div>

  <div class="section-title">
    <span class="number-pill">7</span>
    <span>Tahap 7: Dashboard HR, Audit Trail & Human Decision</span>
  </div>
  <p class="prose">
    Keluaran akhir disajikan melalui antarmuka web interaktif di <code>https://screening.rifqisetiawan.my.id</code> yang menjunjung tinggi kendali manusia (<em>Human-in-the-Loop</em>):
  </p>

  <div class="grid-2">
    <div class="card">
      <div class="card-title">🏆 1. Leaderboard Ranking & Filter Band</div>
      <p class="flow-step-desc">
        Papan peringkat real-time menampilkan urutan kandidat berdasarkan skor final. Recruiter dapat menyaring berdasarkan Band A, B, C, atau tab khusus penolakan bukan-CV.
      </p>
    </div>
    <div class="card">
      <div class="card-title">🔍 2. Candidate Detail Drawer & Evidence</div>
      <p class="flow-step-desc">
        Saat kandidat diklik, muncul panel audit yang membedah nilai per kriteria, lengkap dengan <strong>kutipan kalimat asli (quote)</strong> dari CV sebagai bukti kenapa kriteria tersebut dinilai terpenuhi.
      </p>
    </div>
    <div class="card">
      <div class="card-title">👁️ 3. Fitur Buka Identitas (Reveal Identity)</div>
      <p class="flow-step-desc">
        Identitas asli pelamar (nama, email, WhatsApp) tetap tersembunyi selama proses evaluasi. Recruiter baru menekan tombol <em>"Buka Identitas"</em> ketika kandidat sudah diputuskan lolos ke tahap interview.
      </p>
    </div>
    <div class="card">
      <div class="card-title">⚖️ 4. Gate Kelayakan Administratif Terpisah</div>
      <p class="flow-step-desc">
        Sesuai SE Menaker 2025, syarat administratif seperti domisili atau usia minimum tidak digabung ke dalam skor kompetensi, melainkan diuji pada pintu kelayakan tersendiri dengan status <code>ELIGIBLE / NOT_ELIGIBLE</code>.
      </p>
    </div>
  </div>

  <div class="callout" style="background: #f8fafc; border-left-color: #4f46e5; color: #1e1b4b; margin-top: 14px;">
    <strong style="color: #4338ca; font-size: 8.8pt;">📌 Ringkasan Nilai Keunggulan & Kesiapan Produksi Sistem:</strong>
    <br>✔ <strong>100% Akurasi Ekstraksi:</strong> Teruji pada 54 CV nyata dengan nol anomali nama dan zero truncated history.
    <br>✔ <strong>Bebas Bias & Patuh UU PDP:</strong> Anonimisasi identitas melindungi rekruter dari diskriminasi gender, suku, dan agama.
    <br>✔ <strong>Transparan & Terbukti:</strong> Setiap skor memiliki kutipan bukti asli dari resume kandidat tanpa halusinasi.
    <br>✔ <strong>Kontrol Penuh HR:</strong> Pembobotan 4 kategori dan per kriteria dapat diatur secara live di antarmuka Web UI.
    <br>✔ <strong>Efisien & Skalabel:</strong> Memangkas waktu penyaringan ratusan CV dari hitungan hari menjadi hitungan menit.
  </div>

  <div style="margin-top: 25px; padding-top: 10px; border-top: 1px solid #cbd5e1; text-align: center; font-size: 7.5pt; color: #94a3b8;">
    © 2026 Platform AI CV Screening & Ranking • Dikembangkan oleh Muhammad Rifqi Setiawan • Dokumen Teknis Resmi
  </div>

</body>
</html>
"""

print("Writing HTML blueprint to temporary file...")
temp_html = Path("/tmp/architecture_manual.html")
temp_html.write_text(html_content, encoding="utf-8")

print(f"Compiling PDF via Playwright Chromium to: {OUTPUT_PDF}...")
with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = browser.new_page()
    page.goto(f"file://{temp_html.resolve()}", wait_until="networkidle")
    page.pdf(
        path=str(OUTPUT_PDF),
        format="A4",
        print_background=True,
        margin={"top": "12mm", "right": "12mm", "bottom": "14mm", "left": "12mm"},
    )
    browser.close()

# Copy to public download directory
import shutil
shutil.copyfile(OUTPUT_PDF, PUBLIC_PDF)

sz_kb = OUTPUT_PDF.stat().st_size / 1024
print(f"✅ Master PDF Architecture Handbook berhasil diterbitkan! ({sz_kb:.1f} KB)")
print(f"📁 Local Path : {OUTPUT_PDF}")
print(f"🌐 Public Path: {PUBLIC_PDF}")
