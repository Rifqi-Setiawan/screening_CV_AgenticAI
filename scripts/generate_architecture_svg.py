import os
from pathlib import Path
from playwright.sync_api import sync_playwright

SVG_CONTENT = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 1020" width="1600" height="1020" style="background:#090d16; font-family:'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <defs>
    <!-- Gradients -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#090d16"/>
      <stop offset="50%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#070a10"/>
    </linearGradient>

    <linearGradient id="cardGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b" stop-opacity="0.85"/>
      <stop offset="100%" stop-color="#0f172a" stop-opacity="0.95"/>
    </linearGradient>

    <linearGradient id="accentGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#818cf8"/>
    </linearGradient>

    <linearGradient id="emeraldGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#10b981"/>
      <stop offset="100%" stop-color="#059669"/>
    </linearGradient>

    <linearGradient id="amberGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#d97706"/>
    </linearGradient>

    <!-- Filters & Shadows -->
    <filter id="glowCyan" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>

    <filter id="shadowCard" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#000000" flood-opacity="0.45"/>
    </filter>

    <!-- Arrow Marker -->
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
    </marker>
    <marker id="arrowAmber" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#f59e0b" />
    </marker>
    <marker id="arrowEmerald" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1 L 10 5 L 0 9 z" fill="#10b981" />
    </marker>
  </defs>

  <!-- Background Canvas -->
  <rect width="1600" height="1020" fill="url(#bgGrad)"/>

  <!-- Subtle Blueprint Grid Pattern -->
  <g opacity="0.08" stroke="#94a3b8" stroke-width="0.8">
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40"/>
    </pattern>
    <rect width="1600" height="1020" fill="url(#grid)" />
  </g>

  <!-- ============================================================== -->
  <!-- HEADER & SYSTEM TELEMETRY BANNER                               -->
  <!-- ============================================================== -->
  <g id="header" transform="translate(60, 40)">
    <!-- Top Pill Badge -->
    <rect x="0" y="0" width="230" height="26" rx="13" fill="#1e1b4b" stroke="#6366f1" stroke-width="1.2"/>
    <text x="115" y="17" fill="#a5b4fc" font-size="10.5" font-weight="700" letter-spacing="1.2" text-anchor="middle">OFFICIAL ARCHITECTURE FLOW</text>

    <!-- Title -->
    <text x="0" y="62" fill="#ffffff" font-size="26" font-weight="800" letter-spacing="-0.5">High-Precision AI CV Screening &amp; Ranking Pipeline</text>
    <text x="0" y="88" fill="#94a3b8" font-size="13" font-weight="400">Arsitektur Alur Teknologi Deterministik: Dari Unggah CV, Sanitasi, Vektor Semantik, Evaluasi Bukti, hingga Leaderboard Bebas Bias</text>

    <!-- Tech Badges (Top Right) -->
    <g transform="translate(940, 25)">
      <rect x="0" y="0" width="105" height="28" rx="6" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="52" y="18" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle">FastAPI 3.12</text>

      <rect x="115" y="0" width="115" height="28" rx="6" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="172" y="18" fill="#818cf8" font-size="11" font-weight="700" text-anchor="middle">pgvector 0.8.7</text>

      <rect x="240" y="0" width="120" height="28" rx="6" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="300" y="18" fill="#34d399" font-size="11" font-weight="700" text-anchor="middle">Harrier-270m</text>

      <rect x="370" y="0" width="160" height="28" rx="6" fill="#1e293b" stroke="#334155" stroke-width="1"/>
      <text x="450" y="18" fill="#fbcfe8" font-size="11" font-weight="700" text-anchor="middle">SE Menaker &amp; PDP Gate</text>
    </g>
  </g>

  <!-- ============================================================== -->
  <!-- BARIS ATAS: TAHAP 1 s/d TAHAP 4 (INGESTION & FEATURE EXTRACTION)-->
  <!-- ============================================================== -->

  <!-- CARD 1: INPUT & SANITASI -->
  <g id="card-1" transform="translate(60, 160)" filter="url(#shadowCard)">
    <rect width="335" height="340" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1.2"/>
    <rect x="1" y="1" width="333" height="4" rx="2" fill="url(#accentGrad)"/>
    
    <!-- Stage Badge -->
    <rect x="20" y="20" width="70" height="22" rx="4" fill="#0284c7" opacity="0.25"/>
    <text x="55" y="35" fill="#38bdf8" font-size="10.5" font-weight="800" text-anchor="middle">TAHAP 01</text>
    <text x="100" y="35" fill="#e2e8f0" font-size="13" font-weight="700">Ingestion &amp; Sanitasi</text>

    <!-- Content Items -->
    <g transform="translate(20, 60)" font-size="11" fill="#cbd5e1">
      <text x="0" y="18" font-weight="700" fill="#f8fafc">Format Masukan:</text>
      <text x="0" y="36" fill="#94a3b8">PDF, DOCX, atau ZIP Archive</text>

      <text x="0" y="70" font-weight="700" fill="#f8fafc">1. Pemeriksaan Integritas Fisik:</text>
      <text x="0" y="88" fill="#94a3b8">• Tolak berkas kosong (0 Byte / EMPTY)</text>
      <text x="0" y="106" fill="#94a3b8">• Tolak enkripsi password (ENCRYPTED)</text>
      <text x="0" y="124" fill="#94a3b8">• Filter makro VBA &amp; corrupt stream</text>

      <text x="0" y="158" font-weight="700" fill="#f8fafc">2. Deduplikasi Berlapis (FX-25):</text>
      <text x="0" y="176" fill="#94a3b8">• Hash Byte: SHA-256 berkas fisik</text>
      <text x="0" y="194" fill="#94a3b8">• Fingerprint Teks: SHA-256 teks normal</text>
      <text x="0" y="212" fill="#94a3b8">• Berkas identik di job sama → DUPLICATE</text>
    </g>

    <!-- Tech Footer Pill -->
    <rect x="20" y="295" width="295" height="28" rx="6" fill="#0b1329" stroke="#1e293b" stroke-width="1"/>
    <text x="167" y="313" fill="#38bdf8" font-size="10.5" font-weight="600" text-anchor="middle">Tech: PyMuPDF • python-docx • hashlib</text>
  </g>

  <!-- CONNECTOR 1 -> 2 -->
  <path d="M 395 330 L 440 330" fill="none" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)"/>

  <!-- CARD 2: BLIND REDACTION & PII -->
  <g id="card-2" transform="translate(445, 160)" filter="url(#shadowCard)">
    <rect width="335" height="340" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1.2"/>
    <rect x="1" y="1" width="333" height="4" rx="2" fill="url(#accentGrad)"/>

    <rect x="20" y="20" width="70" height="22" rx="4" fill="#6366f1" opacity="0.25"/>
    <text x="55" y="35" fill="#a5b4fc" font-size="10.5" font-weight="800" text-anchor="middle">TAHAP 02</text>
    <text x="100" y="35" fill="#e2e8f0" font-size="13" font-weight="700">Blind Redaction &amp; PII</text>

    <g transform="translate(20, 60)" font-size="11" fill="#cbd5e1">
      <text x="0" y="18" font-weight="700" fill="#f8fafc">1. Sensor Data Identitas (Zero-PII):</text>
      <text x="0" y="36" fill="#94a3b8">• Nama pelamar diganti token <tspan fill="#f43f5e" font-weight="700">[NAMA]</tspan></text>
      <text x="0" y="54" fill="#94a3b8">• Alamat email diganti <tspan fill="#f43f5e" font-weight="700">[EMAIL]</tspan></text>
      <text x="0" y="72" fill="#94a3b8">• Nomor telepon diganti <tspan fill="#f43f5e" font-weight="700">[TELEPON]</tspan></text>

      <text x="0" y="106" font-weight="700" fill="#f8fafc">2. Isolasi Demografis (FX-24):</text>
      <text x="0" y="124" fill="#94a3b8">• DOB, Gender, Agama dipisahkan mutlak</text>
      <text x="0" y="142" fill="#94a3b8">• Disimpan ke tabel <tspan fill="#38bdf8">candidate_identities</tspan></text>
      <text x="0" y="160" fill="#94a3b8">• Kolom <tspan fill="#fbbf24">other_personal</tspan> dienkripsi PGP</text>

      <text x="0" y="194" font-weight="700" fill="#f8fafc">3. Keluaran Blind Profil:</text>
      <text x="0" y="212" fill="#94a3b8">• Diberi kode anonim: <tspan fill="#34d399" font-weight="700">C-0001, C-0002</tspan></text>
    </g>

    <rect x="20" y="295" width="295" height="28" rx="6" fill="#0b1329" stroke="#1e293b" stroke-width="1"/>
    <text x="167" y="313" fill="#818cf8" font-size="10.5" font-weight="600" text-anchor="middle">Tech: Regex Tokenizer • pgcrypto • PII-Vault</text>
  </g>

  <!-- CONNECTOR 2 -> 3 -->
  <path d="M 780 330 L 825 330" fill="none" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)"/>

  <!-- CARD 3: VEKTOR SEMANTIK & CHUNKING -->
  <g id="card-3" transform="translate(830, 160)" filter="url(#shadowCard)">
    <rect width="335" height="340" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1.2"/>
    <rect x="1" y="1" width="333" height="4" rx="2" fill="url(#accentGrad)"/>

    <rect x="20" y="20" width="70" height="22" rx="4" fill="#10b981" opacity="0.25"/>
    <text x="55" y="35" fill="#34d399" font-size="10.5" font-weight="800" text-anchor="middle">TAHAP 03</text>
    <text x="100" y="35" fill="#e2e8f0" font-size="13" font-weight="700">Vektor Semantik (Chunks)</text>

    <g transform="translate(20, 60)" font-size="11" fill="#cbd5e1">
      <text x="0" y="18" font-weight="700" fill="#f8fafc">1. Segmentasi Struktur Profil:</text>
      <text x="0" y="36" fill="#94a3b8">• Chunks riwayat pekerjaan (Experiences)</text>
      <text x="0" y="54" fill="#94a3b8">• Chunks portfolio proyek &amp; open-source</text>
      <text x="0" y="72" fill="#94a3b8">• Chunks pendidikan &amp; sertifikasi resmi</text>

      <text x="0" y="106" font-weight="700" fill="#f8fafc">2. Dense Vector Inference:</text>
      <text x="0" y="124" fill="#94a3b8">• Model: <tspan fill="#38bdf8" font-weight="700">Harrier-OSS-v1-270m</tspan></text>
      <text x="0" y="142" fill="#94a3b8">• Dimensi Vektor: <tspan fill="#38bdf8" font-weight="700">640 dimensi</tspan></text>
      <text x="0" y="160" fill="#94a3b8">• Komputasi lokal cepat (0 ms latency cloud)</text>

      <text x="0" y="194" font-weight="700" fill="#f8fafc">3. Indeksasi Basis Data:</text>
      <text x="0" y="212" fill="#94a3b8">• <tspan fill="#a7f3d0">HNSW Cosine Vector Index</tspan> di pgvector</text>
    </g>

    <rect x="20" y="295" width="295" height="28" rx="6" fill="#0b1329" stroke="#1e293b" stroke-width="1"/>
    <text x="167" y="313" fill="#34d399" font-size="10.5" font-weight="600" text-anchor="middle">Tech: ONNX / PyTorch • pgvector 16 (HNSW)</text>
  </g>

  <!-- CONNECTOR 3 -> 4 -->
  <path d="M 1165 330 L 1210 330" fill="none" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)"/>

  <!-- CARD 4: RULE-BASED MATCHING -->
  <g id="card-4" transform="translate(1215, 160)" filter="url(#shadowCard)">
    <rect width="325" height="340" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1.2"/>
    <rect x="1" y="1" width="323" height="4" rx="2" fill="url(#accentGrad)"/>

    <rect x="20" y="20" width="70" height="22" rx="4" fill="#f59e0b" opacity="0.25"/>
    <text x="55" y="35" fill="#fbbf24" font-size="10.5" font-weight="800" text-anchor="middle">TAHAP 04</text>
    <text x="100" y="35" fill="#e2e8f0" font-size="13" font-weight="700">Rule-Based Kind Matcher</text>

    <g transform="translate(20, 60)" font-size="11" fill="#cbd5e1">
      <text x="0" y="18" font-weight="700" fill="#f8fafc">1. Evaluasi Jenis Kriteria (Kind):</text>
      <text x="0" y="36" fill="#94a3b8">• <tspan fill="#38bdf8">EXPERIENCE_DURATION</tspan>: Total bulan kerja</text>
      <text x="0" y="54" fill="#94a3b8">• <tspan fill="#38bdf8">SKILL</tspan>: Boundaries &amp; filter negasi</text>
      <text x="0" y="72" fill="#94a3b8">• <tspan fill="#38bdf8">EDUCATION</tspan>: Jenjang S1/S2 &amp; rumpun ilmu</text>

      <text x="0" y="106" font-weight="700" fill="#f8fafc">2. Disambiguasi Kata Kunci (FX-20):</text>
      <text x="0" y="124" fill="#94a3b8">• Java ≠ JavaScript • SQL ≠ SQLite</text>
      <text x="0" y="142" fill="#94a3b8">• Deteksi negasi: <tspan fill="#f43f5e">"tidak menguasai"</tspan> ditolak</text>

      <text x="0" y="176" font-weight="700" fill="#f8fafc">3. Keluaran Status Bukti:</text>
      <text x="0" y="194" fill="#34d399">• STRONG (1.0) di pekerjaan riil</text>
      <text x="0" y="212" fill="#fbbf24">• PARTIAL (0.5) di proyek sampingan</text>
    </g>

    <rect x="20" y="295" width="285" height="28" rx="6" fill="#0b1329" stroke="#1e293b" stroke-width="1"/>
    <text x="162" y="313" fill="#fbbf24" font-size="10.5" font-weight="600" text-anchor="middle">Tech: src/domain/kind_rules.py • text_match</text>
  </g>

  <!-- ============================================================== -->
  <!-- CONNECTOR BARIS ATAS KE BARIS BAWAH (MANHATTAN ORTHOGONAL)    -->
  <!-- ============================================================== -->
  <path d="M 1375 500 L 1375 545 L 227 545 L 227 580" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="6,4" marker-end="url(#arrow)"/>
  <rect x="730" y="533" width="160" height="24" rx="4" fill="#090d16" stroke="#38bdf8" stroke-width="1"/>
  <text x="810" y="549" fill="#38bdf8" font-size="10.5" font-weight="700" text-anchor="middle">Alur Evaluasi Lanjutan ▼</text>

  <!-- ============================================================== -->
  <!-- BARIS BAWAH: TAHAP 5 s/d TAHAP 8 (VERIFIKASI, SKOR, & LEADER)  -->
  <!-- ============================================================== -->

  <!-- CARD 5: GROUNDED LLM VERIFIER -->
  <g id="card-5" transform="translate(60, 580)" filter="url(#shadowCard)">
    <rect width="335" height="360" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1.2"/>
    <rect x="1" y="1" width="333" height="4" rx="2" fill="url(#accentGrad)"/>

    <rect x="20" y="20" width="70" height="22" rx="4" fill="#a855f7" opacity="0.25"/>
    <text x="55" y="35" fill="#c084fc" font-size="10.5" font-weight="800" text-anchor="middle">TAHAP 05</text>
    <text x="100" y="35" fill="#e2e8f0" font-size="13" font-weight="700">Grounded LLM Verifier</text>

    <g transform="translate(20, 60)" font-size="11" fill="#cbd5e1">
      <text x="0" y="18" font-weight="700" fill="#f8fafc">1. Verifikasi Bukti Ambigu:</text>
      <text x="0" y="36" fill="#94a3b8">• Hanya aktif jika status PARTIAL &amp; ada bukti</text>
      <text x="0" y="54" fill="#94a3b8">• Asynchronous call dengan timeout 10 detik</text>
      <text x="0" y="72" fill="#94a3b8">• Hasil di-cache ke tabel <tspan fill="#c084fc">llm_cache</tspan> DB</text>

      <text x="0" y="106" font-weight="700" fill="#f8fafc">2. Aturan Keras (Anti-Halusinasi):</text>
      <text x="0" y="124" fill="#f43f5e" font-weight="700">• DILARANG memberi skor angka numerik!</text>
      <text x="0" y="142" fill="#94a3b8">• Hanya status: STRONG, PARTIAL, NOT_DEMON</text>

      <text x="0" y="176" font-weight="700" fill="#f8fafc">3. Code-Level Grounding Check:</text>
      <text x="0" y="194" fill="#94a3b8">• Kutipan kalimat (quote) <tspan fill="#34d399">wajib ada persis</tspan></text>
      <text x="0" y="212" fill="#94a3b8">  kata-demi-kata di dalam full_text CV.</text>
      <text x="0" y="230" fill="#fbbf24">• Jika quote halusinasi → <tspan fill="#f43f5e">GROUNDING_FAIL</tspan></text>
    </g>

    <rect x="20" y="315" width="295" height="28" rx="6" fill="#0b1329" stroke="#1e293b" stroke-width="1"/>
    <text x="167" y="333" fill="#c084fc" font-size="10.5" font-weight="600" text-anchor="middle">Tech: 9Router Container • Gemini 3.8 Flash</text>
  </g>

  <!-- CONNECTOR 5 -> 6 -->
  <path d="M 395 760 L 440 760" fill="none" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)"/>

  <!-- CARD 6: DETERMINISTIC SCORER & BANDING -->
  <g id="card-6" transform="translate(445, 580)" filter="url(#shadowCard)">
    <rect width="335" height="360" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1.2"/>
    <rect x="1" y="1" width="333" height="4" rx="2" fill="url(#accentGrad)"/>

    <rect x="20" y="20" width="70" height="22" rx="4" fill="#0284c7" opacity="0.25"/>
    <text x="55" y="35" fill="#38bdf8" font-size="10.5" font-weight="800" text-anchor="middle">TAHAP 06</text>
    <text x="100" y="35" fill="#e2e8f0" font-size="13" font-weight="700">Scoring Engine &amp; Banding</text>

    <g transform="translate(20, 60)" font-size="11" fill="#cbd5e1">
      <text x="0" y="18" font-weight="700" fill="#f8fafc">1. Rumus Normalisasi 2 Lapis:</text>
      <text x="0" y="36" fill="#38bdf8" font-family="'JetBrains Mono', monospace">Skor_Kat = (Σ W_i * V_i / Σ W_i) * 100</text>
      <text x="0" y="54" fill="#94a3b8">• Re-normalisasi dinamis kategori aktif</text>

      <text x="0" y="88" font-weight="700" fill="#f8fafc">2. Sistem Plafon Band (Score Capping):</text>
      <text x="0" y="106" fill="#34d399">• <tspan font-weight="700">Band A</tspan>: Semua MUST_HAVE = STRONG (Max 100)</text>
      <text x="0" y="124" fill="#fbbf24">• <tspan font-weight="700">Band B</tspan>: Tepat 1 MUST_HAVE kurang (Cap 74.0)</text>
      <text x="0" y="142" fill="#f43f5e">• <tspan font-weight="700">Band C</tspan>: ≥2 MUST_HAVE kurang (Cap 49.0)</text>
      <text x="0" y="160" fill="#c084fc">• <tspan font-weight="700">Band R</tspan>: MUST_HAVE Unknown (Cek Manual)</text>

      <text x="0" y="194" font-weight="700" fill="#f8fafc">3. Penalti Coverage Rendah (FX-26):</text>
      <text x="0" y="212" fill="#94a3b8">• Jika coverage &lt; 0.6 → Flag <tspan fill="#fbbf24">LOW_COVERAGE</tspan></text>
      <text x="0" y="230" fill="#f43f5e">• Rekomendasi SHORTLIST otomatis dibatalkan</text>
    </g>

    <rect x="20" y="315" width="295" height="28" rx="6" fill="#0b1329" stroke="#1e293b" stroke-width="1"/>
    <text x="167" y="333" fill="#38bdf8" font-size="10.5" font-weight="600" text-anchor="middle">Tech: src/domain/scorer.py (Aljabar Murni)</text>
  </g>

  <!-- CONNECTOR 6 -> 7 -->
  <path d="M 780 760 L 825 760" fill="none" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)"/>

  <!-- CARD 7: ADMINISTRATIVE ELIGIBILITY GATE -->
  <g id="card-7" transform="translate(830, 580)" filter="url(#shadowCard)">
    <rect width="335" height="360" rx="12" fill="url(#cardGrad)" stroke="#334155" stroke-width="1.2"/>
    <rect x="1" y="1" width="333" height="4" rx="2" fill="url(#accentGrad)"/>

    <rect x="20" y="20" width="70" height="22" rx="4" fill="#ec4899" opacity="0.25"/>
    <text x="55" y="35" fill="#f472b6" font-size="10.5" font-weight="800" text-anchor="middle">TAHAP 07</text>
    <text x="100" y="35" fill="#e2e8f0" font-size="13" font-weight="700">Administrative Gate (FX-24)</text>

    <g transform="translate(20, 60)" font-size="11" fill="#cbd5e1">
      <text x="0" y="18" font-weight="700" fill="#f8fafc">1. Kepatuhan SE Menaker 2025 &amp; UU PDP:</text>
      <text x="0" y="36" fill="#94a3b8">• Usia &amp; Gender dipisah dari skor kompetensi</text>
      <text x="0" y="54" fill="#94a3b8">• <tspan fill="#f43f5e" font-weight="700">Zero Automated Rejection</tspan> (Human in Loop)</text>

      <text x="0" y="88" font-weight="700" fill="#f8fafc">2. Tiga Status Administratif:</text>
      <text x="0" y="106" fill="#34d399">• ELIGIBLE: Memenuhi rentang usia/gender</text>
      <text x="0" y="124" fill="#fbbf24">• NOT_ELIGIBLE: Di luar batas syarat</text>
      <text x="0" y="142" fill="#94a3b8">• UNKNOWN: Data DOB/gender tidak di CV</text>
      <text x="0" y="160" fill="#a7f3d0">  (CV modern tanpa DOB dilarang digugurkan!)</text>

      <text x="0" y="194" font-weight="700" fill="#f8fafc">3. Tata Kelola &amp; Audit Trail:</text>
      <text x="0" y="212" fill="#94a3b8">• Wajib justifikasi tertulis HR (min 30 char)</text>
      <text x="0" y="230" fill="#94a3b8">• Wajib persetujuan Admin di <tspan fill="#38bdf8">audit_logs</tspan></text>
    </g>

    <rect x="20" y="315" width="295" height="28" rx="6" fill="#0b1329" stroke="#1e293b" stroke-width="1"/>
    <text x="167" y="333" fill="#f472b6" font-size="10.5" font-weight="600" text-anchor="middle">Tech: src/domain/eligibility.py • Alembic 0004</text>
  </g>

  <!-- CONNECTOR 7 -> 8 -->
  <path d="M 1165 760 L 1210 760" fill="none" stroke="#38bdf8" stroke-width="2.5" marker-end="url(#arrow)"/>

  <!-- CARD 8: LEADERBOARD & RANKING -->
  <g id="card-8" transform="translate(1215, 580)" filter="url(#shadowCard)">
    <rect width="325" height="360" rx="12" fill="url(#cardGrad)" stroke="#38bdf8" stroke-width="1.8"/>
    <rect x="1" y="1" width="323" height="4" rx="2" fill="url(#emeraldGrad)"/>

    <rect x="20" y="20" width="70" height="22" rx="4" fill="#10b981" opacity="0.3"/>
    <text x="55" y="35" fill="#34d399" font-size="10.5" font-weight="800" text-anchor="middle">TAHAP 08</text>
    <text x="100" y="35" fill="#e2e8f0" font-size="13" font-weight="700">Leaderboard &amp; Ranking</text>

    <g transform="translate(20, 60)" font-size="11" fill="#cbd5e1">
      <text x="0" y="18" font-weight="700" fill="#f8fafc">1. Algoritma 4-Level Tie-Breaker:</text>
      <text x="0" y="36" fill="#38bdf8">Kunci 1: Urutan Band (A &gt; B &gt; C &gt; R)</text>
      <text x="0" y="54" fill="#38bdf8">Kunci 2: Final Score Tertinggi</text>
      <text x="0" y="72" fill="#38bdf8">Kunci 3: Total Kriteria STRONG (strong_cnt)</text>
      <text x="0" y="90" fill="#38bdf8">Kunci 4: SHA256(run_id + cand_id) stabil</text>

      <text x="0" y="124" font-weight="700" fill="#f8fafc">2. Tampilan Antarmuka (Blind Mode):</text>
      <text x="0" y="142" fill="#94a3b8">• Label C-0001 • Skor 0-100 • Band A/B/C</text>
      <text x="0" y="160" fill="#94a3b8">• Badge Shortlist / Review / Cek Manual</text>
      <text x="0" y="178" fill="#fbbf24">• Badge Peringatan Eligibilitas Administratif</text>

      <text x="0" y="212" font-weight="700" fill="#f8fafc">3. Tindakan Lanjutan HR:</text>
      <text x="0" y="230" fill="#94a3b8">• Inspeksi Bukti &amp; Pertanyaan Interview</text>
      <text x="0" y="248" fill="#34d399">• Reveal Identity ter-audit pasca shortlist</text>
    </g>

    <rect x="20" y="315" width="285" height="28" rx="6" fill="#0b1329" stroke="#10b981" stroke-width="1"/>
    <text x="162" y="333" fill="#34d399" font-size="10.5" font-weight="700" text-anchor="middle">Hasil Akhir: Peringkat 100% Objektif</text>
  </g>

  <!-- ============================================================== -->
  <!-- FOOTER BRANDING                                                -->
  <!-- ============================================================== -->
  <g id="footer" transform="translate(60, 975)">
    <text x="0" y="15" fill="#64748b" font-size="11">© 2026 AI CV Screening &amp; Ranking Platform • Production System Design &amp; Architectural Flow</text>
    <text x="1480" y="15" fill="#38bdf8" font-size="11" font-weight="600" text-anchor="end">Muhammad Rifqi Setiawan</text>
  </g>
</svg>'''

def main():
    svg_path = "/srv/hermes-control/services/cv-screening/docs/cv_screening_flow_architecture.svg"
    png_path = "/srv/hermes-control/services/cv-screening/docs/cv_screening_flow_architecture.png"

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(SVG_CONTENT)
    print(f"SVG saved to {svg_path}")

    # Render PNG using Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1020}, device_scale_factor=2)
        page.set_content(SVG_CONTENT)
        page.screenshot(path=png_path)
        browser.close()
    print(f"High-res PNG rendered to {png_path}")

if __name__ == "__main__":
    main()
