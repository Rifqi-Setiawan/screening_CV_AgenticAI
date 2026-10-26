# 01. Tahap 1: Setup Lowongan & Kompilasi Kriteria (JD Compiler)

Tahap 1 adalah gerbang awal di mana rekruter mendefinisikan posisi pekerjaan dan deskripsi lowongan kerja (*Job Description / JD*). Teks bebas tersebut kemudian diuraikan secara otomatis oleh AI menjadi struktur data kriteria terukur (**RequirementIR**) yang dilengkapi pembobotan bertingkat dan kepatuhan regulasi.

---

## 1. Alur Input Lowongan & Template Posisi Cepat

Pada antarmuka pengguna (`frontend/src/App.tsx`), rekruter dapat memasukkan data lowongan secara manual atau memilih salah satu dari 7 template peran industri (*Role Templates*) yang telah terstandarisasi:
1. **Backend Engineering:** Standar REST API, microservices, basis data relasional, caching, dan queue.
2. **Frontend Engineering:** Standar React/Vue, state management, modern CSS, dan Web Vitals.
3. **Data Engineering:** Standar Medallion lakehouse, DuckDB/Spark, ETL/ELT, dan dbt.
4. **Civil Engineering:** Standar manajemen proyek konstruksi, RAB, AutoCAD, dan K3.
5. **Quality Assurance (QA):** Standar pengujian otomatis Playwright/Selenium, load testing, dan API testing.
6. **Human Resources (HR):** Standar rekrutmen end-to-end, UU Ketenagakerjaan, dan manajemen talenta.
7. **Product Management (PM):** Standar roadmap produk, PRD, metrik analitik, dan sprint delivery.

---

## 2. Penguraian Teks JD ke RequirementIR (5 Facets Decomposition)

Deskripsi pekerjaan yang berbentuk teks bebas diuraikan oleh modul `src/domain/jd_compiler.py` menjadi **5 Facets Penilaian Terstruktur**:

| Facet | Kode | Deskripsi | Contoh Kriteria |
| :--- | :--- | :--- | :--- |
| **Duration Facet** | `F1` | Jam terbang minimal pada domain relevan | "Pengalaman minimal 2 tahun sebagai Backend Developer" |
| **Tech Stack Facet** | `F2` | Penguasaan bahasa pemrograman & tools inti | "Menguasai Golang, Python, atau PHP" |
| **Architecture Facet** | `F3` | Pemahaman rancang bangun dan arsitektur sistem | "Merancang REST API scalable dan integrasi sistem pembayaran" |
| **Database Facet** | `F4` | Pengelolaan data dan optimasi query | "Mahir dalam basis data relasional PostgreSQL/MySQL" |
| **Quality Facet** | `F5` | Standar mutu rekayasa perangkat lunak | "Menerapkan clean code, unit testing, dan Git version control" |

Setiap kriteria hasil dekomposisi memiliki metadata:
- `requirement_id`: Penomoran unik (`R1`, `R2`, `R3`, dst.).
- `category`: Kategori makro (`EXPERIENCE`, `HARD_SKILLS`, `EDUCATION_CERT`, `ACHIEVEMENT`).
- `kind`: Tipe kapabilitas (`EXPERIENCE_DURATION`, `SKILL`, `RESPONSIBILITY`, `EDUCATION`, `CERTIFICATION`).
- `importance`: Tingkat kepentingan (`MUST_HAVE`, `STRONG_PREFERENCE`, `NICE_TO_HAVE`).
- `weight`: Poin bobot relatif (angka 1 s.d. 30 poin).
- `concepts`: Tag konsep ontologi (contoh: `["role:backend", "skill:python", "skill:postgresql"]`).
- `source_text`: Kalimat asli dari deskripsi lowongan tempat kriteria tersebut ditemukan.

---

## 3. Kompilasi AI: Gemini 3.8 Flash dalam Mode JSON Schema

Proses penguraian otomatis menggunakan model **Google Gemini 3.8 Flash** (`ag/gemini-3.8-flash`) dengan konfigurasi khusus:
- **Temperature:** `0.0` (deterministik mutlak, mencegah halusinasi kreatif).
- **Format Keluaran:** Strict JSON Schema (`response_format: {"type": "json_object"}`).

### Struktur Prompt Kompilasi:
```text
Kamu adalah compiler Job Description menjadi kriteria screening terstruktur.
Analisis teks lowongan ini dan hasilkan JSON array 'requirements' dengan field:
- requirement_id (R1, R2, ...)
- description (teks deskripsi)
- category (EXPERIENCE, HARD_SKILLS, EDUCATION_CERT, ACHIEVEMENT)
- kind (EXPERIENCE_DURATION, RESPONSIBILITY, SKILL, EDUCATION, CERTIFICATION, ACHIEVEMENT)
- importance (MUST_HAVE, STRONG_PREFERENCE, NICE_TO_HAVE)
- weight (angka 1-30)
- concepts (array concept_id seperti role_family:backend, skill:python, skill:postgresql)
- source_text (kalimat asli dari JD)
```

### Pagar Pengaman (*Guardrails*) di Backend Python:
1. **Clamping Poin:** Angka bobot dibatasi secara paksa di rentang `max(1.0, min(30.0, raw_weight))` agar tidak ada kriteria tunggal yang mendominasi nilai.
2. **Concept Rule Augmentation:** Regex bawaan Python memindai teks kriteria dan menambahkan konsep ontologi tambahan jika model terlewat mengenali teknologi spesifik.
3. **Fallback Deterministik:** Jika panggilan LLM gagal atau timeout, sistem otomatis beralih ke parser berbasis aturan (*Rule-based Fallback*) menggunakan pemindaian baris bertanda strip (`-` atau `*`).

---

## 4. Arsitektur Scoring Dua Lapis (*Two-Layer Scoring Model*)

Sistem menerapkan model skoring dua lapis untuk mencegah bias rekruter yang sering terjadi di industri:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   LAPIS 1: CARD ATAS (BOBOT MAKRO)                     │
│                Distribusi Persentase Total Wajib 100%                  │
├───────────────────┬───────────────────┬────────────────┬───────────────┤
│  Pengalaman (40%) │  Hard Skill (30%) │ Pendidikan(15%)│Pencapaian(15%)│
└─────────┬─────────┴─────────┬─────────┴────────────────┴───────────────┘
          │                   │
          │                   ▼
          │         ┌────────────────────────────────────────────────────┐
          │         │         LAPIS 2: TABEL BAWAH (BOBOT MIKRO)         │
          │         │               Bobot Poin Relatif                   │
          │         ├────────────────────────────────────────────────────┤
          │         │ • R2: Bahasa Pemrograman Backend ➔ 20 Poin         │
          │         │ • R3: Perancangan REST API       ➔ 20 Poin         │
          │         │ • R4: Basis Data Relasional SQL  ➔ 15 Poin         │
          │         │ • R5: Clean Code & Unit Testing  ➔ 10 Poin         │
          │         │ • R6: Payment Gateway            ➔ 10 Poin         │
          │         │ Total Poin Kategori Hard Skill    = 75 Poin        │
          │         └────────────────────────────────────────────────────┘
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ • R1: Pengalaman Kerja Min. 2 Tahun ➔ 25 Poin                          │
│ Total Poin Kategori Pengalaman      = 25 Poin                          │
└────────────────────────────────────────────────────────────────────────┘
```

### Mengapa Harus Ada Dua Lapis?
Jika hanya menggunakan bobot kriteria biasa, seorang rekruter yang mencantumkan 10 kriteria teknologi tetapi hanya 1 kriteria pengalaman akan secara tidak sengaja menurunkan bobot pengalaman kerja menjadi hanya 9%. Dengan Card Atas, sistem mengunci bahwa **jam terbang kerja nyata tetap menyumbang 40% dari rapor kelulusan akhir**, berapa pun jumlah syarat teknologi yang dicantumkan.

---

## 5. Kepatuhan Kebijakan Rekrutmen (Policy Linter)

Sebelum kriteria disimpan, teks lowongan dipindai oleh `src/domain/policy_linter.py` terhadap aturan regulasi ketenagakerjaan:
1. **Kriteria Terlarang Mutlak (*Prohibited Criteria*):**  
   Diskriminasi berdasarkan suku, ras, etnis, atau status perkawinan otomatis dicegat dan memicu bendera `PROHIBITED_DISCRIMINATION`.
2. **Kriteria Administratif & Demografis (*Bona Fide Occupational Qualification*):**  
   Sesuai konfigurasi sistem (`ALLOW_AGE_CRITERIA=True`, `ALLOW_GENDER_CRITERIA=True`, `ALLOW_RELIGION_CRITERIA=True`), syarat usia, gender, dan agama tidak diblokir jika memang diperlukan untuk posisi tertentu (misal: guru agama, petugas keamanan gender tertentu, atau batas usia program magang fresh graduate).

---

## 6. Alur Verifikasi Manusia (*Human-in-the-Loop*)

1. **Status DRAF:** Hasil ekstraksi awal disimpan di tabel `requirement_sets` dengan status `DRAFT`.
2. **Modal Popup Interaktif:** Rekruter dapat mengklik baris kriteria mana saja untuk membuka popup dialog lega. Di dalam popup, rekruter dapat:
   - Membaca deskripsi utuh tanpa terpotong batas tabel.
   - Mengedit teks kriteria atau mengoreksi kutipan aslinya.
   - Mengubah kategori, tingkat kepentingan (*Wajib/Diutamakan*), dan bobot poin.
3. **Kunci Kriteria (Versi Disetujui):**  
   Ketika rekruter menekan tombol **"Setujui Kriteria (Kunci Versi)"**, status dinaikkan menjadi `APPROVED` dan versi kriteria dinaikkan (misal: Versi 1). Pintu menuju **Step 2 (Upload CV)** pun terbuka secara otomatis.
