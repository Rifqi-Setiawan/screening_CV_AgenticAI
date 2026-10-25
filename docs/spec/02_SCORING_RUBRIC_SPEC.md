# 02 — Scoring Rubric & Ranking Algorithm Spec

> Dokumen paling krusial. Implementasi acuan rumus ada di
> `golden_dataset/generator/reference_scorer.py`. Scoring engine produksi **wajib** menghasilkan angka yang
> identik dengan modul itu untuk input status yang sama.

## 1. Prinsip

1. Kandidat dinilai **per kriteria**, bukan "CV ini mirip JD atau tidak" secara keseluruhan.
2. Setiap kriteria mendapat **satu status** dengan **bukti kutipan** dari CV.
3. Skor akhir dihitung **oleh kode** dari bobot × status. **LLM tidak pernah mengeluarkan skor 0–100.**
4. LLM hanya boleh: (a) membuat draf kriteria dari JD, (b) membantu ekstraksi bagian CV yang sulit,
   (c) memilih status untuk kriteria yang ambigu dari pilihan tertutup, dengan kutipan yang dicek kode.
5. Yang tidak tertulis di CV = **tidak tercantum**, bukan "tidak bisa".

## 2. Kategori dan bobot default

Bobot di bawah adalah **template default**. Recruiter bisa mengubahnya per lowongan saat menyetujui kriteria.
Jumlah bobot semua kriteria = 100.

| Kategori | Kode | Bobot default | Isi |
| --- | --- | --- | --- |
| Relevansi Pengalaman Kerja | `EXPERIENCE` | 40 | Lama pengalaman di role family yang relevan, tanggung jawab yang sama, industri/domain |
| Hard Skills & Tech Stack | `HARD_SKILLS` | 30 | Skill wajib dan nilai tambah, tools, bahasa pemrograman |
| Pendidikan & Sertifikasi | `EDUCATION_CERT` | 15 | Jenjang dan jurusan, lisensi, sertifikasi profesional |
| Pencapaian & Kepemimpinan Terbukti | `ACHIEVEMENT` | 15 | Pencapaian terukur, memimpin/membimbing tim, portofolio |

**Perubahan dari rancangan awal:** kategori ke-4 di draf agent bernama "Soft Skills / Prestasi". Soft skill
seperti "komunikatif" atau "disiplin" **tidak dinilai** dari teks CV, karena tidak bisa dibuktikan dari CV dan
rawan bias. Yang dinilai hanya hal yang tertulis sebagai fakta: pencapaian bernomor dan pengalaman memimpin.
Soft skill dipindah ke panduan interview.

Bobot kategori dibagi ke kriteria di dalamnya. Contoh JD-01: `EXPERIENCE` 40 = R1 (25) + R2 (15).

## 3. Kriteria (requirement)

Skema lengkap: `schemas/requirement_set.schema.json`. Field penting:

| Field | Isi |
| --- | --- |
| `requirement_id` | `R1`, `R2`, … unik dalam satu set |
| `description` | Teks yang dibaca recruiter |
| `category` | Salah satu dari 4 kategori |
| `kind` | `EXPERIENCE_DURATION`, `SKILL`, `RESPONSIBILITY`, `EDUCATION`, `CERTIFICATION`, `ACHIEVEMENT`, `LEADERSHIP`, `LANGUAGE`, `LOCATION`, `WORK_AUTHORIZATION` |
| `importance` | `MUST_HAVE`, `STRONG_PREFERENCE`, `NICE_TO_HAVE` |
| `weight` | Angka ≥ 0, total set = 100 |
| `concepts` | ID konsep di taksonomi, mis. `skill:python`, `role_family:backend` |
| `params` | Parameter per kind (mis. `min_months`, `acceptable_alternatives`, `strong_fields`) |
| `source_text` | Kalimat asli di JD |
| `status` | `DRAFT` → `APPROVED` (immutable setelah disetujui) |

**Kriteria yang dilarang** (ditandai policy linter, tidak bisa disetujui): usia/umur maksimal-minimal,
jenis kelamin, agama, suku, status pernikahan, kehamilan, tinggi/berat badan, "berpenampilan menarik",
foto, golongan darah, kondisi kesehatan yang tidak terkait langsung dengan pekerjaan, dan "lulus maksimal X
tahun" sebagai proxy usia.

**Kriteria berisiko** (boleh dipakai, tapi recruiter harus mencentang konfirmasi dan UI menampilkan peringatan
bias): asal kampus tertentu, IPK minimum, domisili (sah hanya untuk kerja on-site). Daftar lengkap:
`reference/prohibited_criteria.yaml`.

## 4. Status per kriteria

| Status | Nilai | Arti |
| --- | --- | --- |
| `STRONG` | 1.0 | Terbukti kuat sesuai aturan kind |
| `PARTIAL` | 0.5 | Ada bukti, tapi lemah (konteks lemah, durasi kurang, atau tidak langsung) |
| `NOT_DEMONSTRATED` | 0.0 | Tidak tercantum di CV |
| `UNKNOWN` | — | Tidak bisa dinilai karena bagian CV gagal dibaca. **Dikeluarkan dari perhitungan** dan kandidat masuk antrian cek manual |

### 4.1 Hierarki konteks bukti

Bukti dinilai lebih kuat kalau muncul di konteks yang lebih "nyata":

| Konteks | Contoh | Untuk skill |
| --- | --- | --- |
| Pekerjaan bertanggal (`full_time`, `contract`, `freelance`, `internship`) | "Backend Engineer, 2019–2022: membangun API dengan Python" | `STRONG` |
| Proyek (pribadi, tugas akhir, bootcamp) | "Proyek: URL shortener dengan Docker" | `PARTIAL` |
| Organisasi / kegiatan kampus | "Ketua Himpunan" | `PARTIAL` |
| Pendidikan (mata kuliah) | "Mata kuliah Basis Data" | `PARTIAL` |
| Hanya di daftar skill atau ringkasan | "Skills: Python, Docker" | `PARTIAL` |
| Tidak ada di mana pun | — | `NOT_DEMONSTRATED` |

Teks yang terdeteksi **tersembunyi** (font < 4 pt, warna sama dengan latar, di luar halaman) **tidak boleh**
dipakai sebagai bukti apa pun.

### 4.2 Aturan per kind

**`EXPERIENCE_DURATION`** (mis. R1 "min 3 tahun backend")

1. Klasifikasikan setiap entri pekerjaan ke `role_family` (lihat 4.3).
2. Ambil entri yang `role_family`-nya ada di `params.accepted_role_families`.
3. Hitung bulan per entri: `(tahun_akhir×12 + bulan_akhir) − (tahun_awal×12 + bulan_awal) + 1`.
   - "Sekarang/Present/Now/Saat ini" = bulan dari tanggal screening (`as_of`).
   - Hanya tahun (`2020 – 2022`): awal = Juli, akhir = Juni (`2020-07` s/d `2022-06`). Tandai sebagai INFERENSI.
   - Rentang yang tumpang tindih **digabung**, tidak dijumlahkan dua kali.
   - Magang (`internship`) dihitung **50%**.
   - Tanggal di masa depan, tanggal akhir sebelum awal, atau tanggal hilang → entri tidak dihitung dan diberi
     flag `DATE_ANOMALY`.
4. Status: bulan ≥ `min_months` → `STRONG`; 0 < bulan < `min_months` → `PARTIAL`; 0 → `NOT_DEMONSTRATED`.
5. Simpan hasil sebagai INFERENSI lengkap dengan rumus dan entri yang dipakai (`metrics.backend_months`).

**`SKILL`**

1. Normalisasi semua penyebutan skill ke konsep taksonomi ("Postgres" → `skill:postgresql`).
2. Cocokkan dengan `concepts` kriteria. Untuk `params.match = "ANY"`, satu konsep cukup.
3. Status = konteks terkuat tempat konsep itu muncul (tabel 4.1).
4. `params.acceptable_alternatives` hanya berlaku kalau recruiter menuliskannya. Contoh: MySQL **bukan**
   alternatif PostgreSQL kecuali ditulis.
5. Skill "terkait" **tidak** memberi nilai: Docker ≠ Kubernetes, Node.js ≠ Python. Skill terkait boleh
   ditampilkan sebagai bahan pertanyaan interview.
6. Kata keterangan level di daftar skill ("Python (basic)") tetap `PARTIAL` karena konteksnya daftar skill.

**`RESPONSIBILITY`** (mis. R2 "membangun REST API/microservices di production")

- `STRONG`: bullet pekerjaan bertanggal yang menyatakan **membangun/mengembangkan/mendesain** hal tersebut.
- `PARTIAL`: hanya di proyek/magang, atau aktivitas yang berdekatan tapi bukan membangun (mis. "API internal
  sederhana"), atau hanya menyebut tanpa kata kerja membangun.
- `NOT_DEMONSTRATED`: tidak ada. **Menguji** API ≠ membangun API.
- Kriteria ini boleh dinilai LLM verifier (lihat bagian 8), karena butuh pemahaman kalimat.

**`EDUCATION`**

- Normalisasi jenjang: SMA/SMK < D3 < D4 = S1 (Sarjana/Bachelor) < S2 (Magister/Master) < S3.
- Jurusan di `params.strong_fields` dan jenjang ≥ `min_level` → `STRONG`.
- Jurusan di `params.partial_fields`, atau jenjang di bawah `min_level` tapi jurusan cocok → `PARTIAL`.
- Lainnya → `NOT_DEMONSTRATED`. Mahasiswa aktif (belum lulus) maksimal `PARTIAL`.
- **Nama kampus, akreditasi, dan IPK tidak dinilai** kecuali recruiter membuat kriteria eksplisit untuk itu,
  dan itu ditampilkan sebagai peringatan bias. Skala IPK berbeda (4,00 vs 10) tidak boleh dibandingkan.

**`CERTIFICATION`**

- Nama sertifikat cocok dengan konsep → `STRONG`. Sertifikat yang tanggal kedaluwarsanya tertulis dan sudah
  lewat → `PARTIAL`. Kursus/pelatihan yang bukan sertifikasi resmi untuk konsep itu → `PARTIAL` hanya kalau
  recruiter mengizinkan di `params`. Tidak ada → `NOT_DEMONSTRATED`.

**`ACHIEVEMENT`** (pencapaian terukur di domain lowongan)

- `STRONG`: bullet **pekerjaan** yang berisi angka hasil (%, ms, x lipat, jumlah pengguna/transaksi, waktu
  dihemat) **dan** relevan dengan domain kriteria.
- `PARTIAL`: angka hasil di proyek/organisasi, atau angka hasil di pekerjaan tapi domainnya tidak sesuai
  (mis. data analyst untuk lowongan backend).
- `NOT_DEMONSTRATED`: tidak ada angka hasil, atau domain sama sekali berbeda (mis. target penjualan untuk
  lowongan backend).

**`LEADERSHIP`** (memimpin/membimbing tim teknis)

- `STRONG`: di pekerjaan, jabatan memuat Lead/Head/Manager/Supervisor/Kepala/Koordinator **atau** bullet
  "memimpin tim N orang", "mentoring", "led a team", **dan** timnya teknis (sesuai domain lowongan).
- `PARTIAL`: kepemimpinan di organisasi/kampus/proyek, atau memimpin tim teknis di domain yang berdekatan
  (mis. tim QA untuk lowongan backend boleh `STRONG` atau `PARTIAL`).
- `NOT_DEMONSTRATED`: tidak ada, atau memimpin tim non-teknis untuk lowongan teknis.

**`LANGUAGE`, `LOCATION`, `WORK_AUTHORIZATION`**: hanya dari pernyataan eksplisit di CV. Boleh dijadikan
**filter keras** kalau recruiter mengaktifkannya; kalau tidak tercantum → `UNKNOWN` (bukan gagal filter),
dan kandidat masuk daftar "perlu konfirmasi".

### 4.3 Role family

Daftar awal (bisa diperluas di taksonomi, setiap perubahan butuh persetujuan admin):

| Role family | Contoh judul (ID/EN) |
| --- | --- |
| `backend` | Backend Engineer/Developer, Software Engineer (backend), API Developer, Programmer (backend) |
| `fullstack` | Fullstack Developer, Full Stack Engineer |
| `frontend` | Frontend Developer, UI Engineer |
| `mobile` | Android/iOS/Flutter Developer |
| `data` | Data Analyst, Data Engineer, Data Scientist, BI Analyst |
| `qa` | QA Engineer, QA Automation, Software Tester |
| `devops` | DevOps, SRE, Platform Engineer |
| `hr` | HR Generalist, Recruiter, Talent Acquisition, Staf SDM |
| `other` | semua yang tidak cocok |

Judul ambigu ("Programmer", "Software Engineer", "IT Staff") ditentukan dari bullet-nya. Kalau tetap ambigu,
LLM verifier memilih dari daftar tertutup di atas, dan pilihan itu disimpan sebagai INFERENSI.

## 5. Rumus skor

Untuk set kriteria yang disetujui, dengan bobot `w_r` dan nilai status `v(m_r)`:

```
raw_score = 100 × Σ(w_r × v(m_r)) / Σ(w_r)        hanya untuk kriteria yang status-nya BUKAN UNKNOWN
v(STRONG) = 1.0, v(PARTIAL) = 0.5, v(NOT_DEMONSTRATED) = 0.0
```

- Dibulatkan 1 desimal.
- Skor per kategori dihitung dengan rumus yang sama, hanya di dalam kategori itu (untuk tampilan bar).
- **Confidence tidak mengalikan skor.** Confidence dipakai untuk menentukan kapan perlu LLM verifier atau
  cek manual (bagian 9). Ini menjaga skor tetap bisa dijelaskan dan diulang.

## 6. Band dan batas skor (cap)

Hitung `n` = jumlah kriteria `MUST_HAVE` yang statusnya **bukan** `STRONG` (tidak termasuk `UNKNOWN`).

| Kondisi | Band | Arti di UI | Skor akhir |
| --- | --- | --- | --- |
| Ada `MUST_HAVE` berstatus `UNKNOWN` | `R` | Perlu cek manual | `raw_score` (ditampilkan abu-abu) |
| `n = 0` | `A` | Semua kriteria wajib terbukti | `raw_score` |
| `n = 1` | `B` | 1 kriteria wajib belum terbukti | `min(raw_score, 74)` |
| `n ≥ 2` | `C` | ≥ 2 kriteria wajib belum terbukti | `min(raw_score, 49)` |

Kalau skor dibatasi, UI menampilkan alasannya, contoh: *"Skor dasar 77, dibatasi 74 karena 'Python' belum
terbukti kuat."*

## 7. Rekomendasi dan warna

| Kondisi | Rekomendasi (kode) | Label UI |
| --- | --- | --- |
| Band `A` dan skor ≥ 70 | `SHORTLIST` | Disarankan shortlist |
| Band `A` dan skor < 70, atau band `B` | `REVIEW` | Perlu ditinjau |
| Band `C` | `LOW_PRIORITY` | Prioritas rendah |
| Band `R` | `MANUAL_CHECK` | Perlu cek manual |

Tidak ada label "Reject". Penolakan hanya bisa dilakukan manusia lewat tombol "Tidak lanjut" dengan alasan.

Warna skor: ≥ 75 hijau, 50–74 kuning, < 50 merah. Band `R` abu-abu.

## 8. Metode matching (pipeline penilaian)

```
Kriteria disetujui ──┐
                     ▼
1. Filter keras (opsional, hanya kriteria objektif yang diaktifkan recruiter)
2. Kandidat masuk penilaian:
     • pool ≤ 5.000 CV  → SEMUA kandidat dinilai (tidak ada yang tersaring oleh pencarian)
     • pool > 5.000     → pencarian hybrid untuk memilih 500 teratas:
                          konsep skill (SQL) + full-text (kata kunci) + embedding (makna), digabung RRF k=60
3. Untuk tiap (kandidat, kriteria):
     a. Aturan deterministik (bagian 4.2) dari profil terstruktur  → status + bukti + confidence
     b. Kalau confidence < 0.85 atau kind = RESPONSIBILITY/ACHIEVEMENT/LEADERSHIP dengan bukti ambigu:
          pilih 3 potongan CV paling relevan (embedding + reranker opsional)
          → LLM verifier memilih status dari pilihan tertutup + menunjuk kutipan
     c. Kode mengecek kutipan benar-benar ada di CV. Kalau tidak → status dari langkah (a), flag GROUNDING_FAIL
4. Skor, band, cap, rekomendasi (bagian 5–7) → oleh kode
5. Urutkan: band (A, B, C, R) → skor turun → jumlah STRONG turun → hash(run_id, candidate_id)
```

**Embedding** dipakai untuk (1) mencari kandidat di pool besar dan (2) memilih potongan CV yang paling relevan
untuk kriteria. Embedding **tidak** langsung menjadi skor. Contoh: embedding membantu menemukan bahwa
"membangun layanan gRPC dengan Go" relevan untuk kriteria "microservices", lalu aturan dan verifier menentukan
statusnya.

**LLM verifier** (format input/output):

```json
// input
{"requirement": "Membangun REST API atau microservices di production",
 "kind": "RESPONSIBILITY",
 "evidence_candidates": [
   {"id": "c1", "context": "experience/full_time", "text": "Membuat API internal sederhana dengan Flask untuk menyuplai data dashboard."}
 ],
 "allowed_states": ["STRONG", "PARTIAL", "NOT_DEMONSTRATED"],
 "rules": "<ringkasan aturan kind dari 4.2>"}
// output (wajib JSON sesuai schema, temperature 0)
{"state": "PARTIAL", "evidence_id": "c1", "quote": "API internal sederhana dengan Flask", "confidence": 0.78}
```

Teks CV selalu masuk sebagai **data** di field `text`, tidak pernah digabung ke instruksi. Model tidak diberi
tool apa pun. Provider verifier bisa diganti lewat model gateway (LLM lokal, API, atau Jev dari TypeSafe
sebagai eksperimen; Jev cocok karena outputnya pilihan tertutup + probabilitas, tapi tidak memberi kutipan,
jadi `evidence_id` dipilih kode dari kandidat bukti teratas).

## 9. Confidence dan eskalasi

| Sumber | Confidence |
| --- | --- |
| Aturan deterministik dengan konsep cocok persis di konteks pekerjaan | 0.95 |
| Aturan dengan fuzzy match alias (rapidfuzz ≥ 92) | 0.85 |
| Ekstraksi dari OCR dengan rata-rata confidence OCR < 0.80 | maks 0.70 |
| LLM verifier | nilai dari model, dibatasi maks 0.90 |

- Confidence < 0.60 setelah verifier → status tetap dipakai, tapi kriteria diberi tanda "perlu dicek" di UI.
- ≥ 3 kriteria dengan confidence < 0.60 → kandidat diberi flag `LOW_CONFIDENCE` dan muncul di filter
  "Perlu cek manual".

## 10. Penjelasan (reasoning) untuk recruiter

Dibuat dari tabel status dan bukti dengan **template**, bukan teks bebas LLM:

- **Kelebihan**: semua kriteria `STRONG`, urut bobot terbesar, masing-masing dengan kutipan.
- **Belum terbukti**: kriteria `NOT_DEMONSTRATED`/`PARTIAL`, urut bobot terbesar. Kalimat wajib: "tidak
  tercantum di CV" atau "hanya tercantum di daftar skill", bukan "tidak menguasai".
- **Saran pertanyaan interview**: satu per kriteria wajib/diutamakan yang belum `STRONG`.
- **Perbandingan A vs B**: tabel per kriteria, sorot kriteria dengan selisih nilai × bobot terbesar.
- Ringkasan 1–2 kalimat boleh dibuat LLM **hanya** dari tabel itu. Kalimat yang menyebut hal di luar tabel
  ditolak dan diganti template.

Dilarang di penjelasan: kepribadian, "culture fit", kecerdasan, kejujuran, loyalitas, penampilan, usia,
gender, agama, asal daerah, gaya bahasa CV, nama kampus sebagai nilai plus.

## 11. Red flags dan edge cases

| Kasus | Deteksi | Perilaku sistem |
| --- | --- | --- |
| CV kosong / teks < 150 karakter setelah OCR | Panjang teks | Status `NEEDS_REVIEW`, alasan `INSUFFICIENT_CONTENT`, tidak diberi skor |
| PDF/gambar tanpa text layer | Teks < 50 karakter per halaman | Deteksi layout + OCR; kalau OCR confidence < 0.60 → `NEEDS_REVIEW` alasan `LOW_OCR_QUALITY` |
| PDF terkunci password | Error parser | Status `REJECTED`, alasan `ENCRYPTED_FILE`, minta file ulang |
| File rusak / format tidak didukung | Error parser / MIME | `REJECTED`, alasan `UNSUPPORTED_OR_CORRUPT` |
| Bukan CV (surat lamaran, transkrip, sertifikat saja) | Tidak ada bagian pengalaman/pendidikan + klasifikasi dokumen | `NEEDS_REVIEW`, alasan `NOT_A_CV` |
| Duplikat persis (hash sama) | SHA-256 | Status `DUPLICATE`, `duplicate_of` = file pertama, dinilai sekali |
| Hampir duplikat / orang sama, CV beda | Hash email/telepon, kemiripan teks | Flag `POSSIBLE_DUPLICATE`, keduanya tetap dinilai, recruiter memutuskan |
| Teks tersembunyi (putih, < 4 pt) | Analisis warna/ukuran font | Dikeluarkan dari penilaian, flag `HIDDEN_TEXT` |
| Instruksi ke AI di CV ("ignore instructions…") | Pola + classifier | Dikeluarkan dari penilaian, flag `PROMPT_INJECTION`; skor tidak berubah dari konten aslinya |
| Keyword stuffing (skill berulang, daftar skill panjang tanpa konteks) | Rasio skill daftar vs skill di pengalaman, pengulangan | Skill hanya di daftar = `PARTIAL`; flag `KEYWORD_STUFFING` |
| Tanggal aneh (masa depan, akhir < awal, overlap ekstrem) | Validasi tanggal | Entri tidak dihitung untuk durasi, flag `DATE_ANOMALY` |
| Celah kerja (gap) | Selisih antar entri | **Tidak dinilai dan tidak ditampilkan sebagai negatif** |
| Salah jurusan total / profesi berbeda | — | **Tidak ada aturan khusus.** Skor rendah muncul alami karena kriteria tidak terbukti |
| Bahasa selain ID/EN | Deteksi bahasa | Diproses sebisanya; flag `LANGUAGE_UNSUPPORTED` kalau ekstraksi gagal |
| CV sangat panjang (> 10 halaman) | Jumlah halaman | Diproses 10 halaman pertama, flag `TRUNCATED` |
| Kandidat keberatan atas penilaian otomatis | Permintaan kandidat | Kandidat dikeluarkan dari ranking AI, status `MANUAL_ONLY` |

## 12. Contoh lengkap (M1 di golden dataset)

Lowongan JD-01. CV: Backend Developer Node.js, 57 bulan, Python hanya "Python (basic)" di daftar skill.

| Kriteria | Bobot | Bukti | Status | Bobot × nilai |
| --- | --- | --- | --- | --- |
| R1 Backend ≥ 3 th (wajib) | 25 | Backend Developer, Feb 2022 – Present (57 bln) | STRONG | 25 |
| R2 REST API production | 15 | "Built REST APIs with Node.js (Express) and PostgreSQL…" | STRONG | 15 |
| R3 Python (wajib) | 10 | Hanya "Python (basic)" di daftar skill | PARTIAL | 5 |
| R4 PostgreSQL (wajib) | 8 | Di bullet pekerjaan | STRONG | 8 |
| R5 Docker | 6 | "Dockerized all services…" | STRONG | 6 |
| R6 Kubernetes/cloud | 6 | — | NOT_DEMONSTRATED | 0 |
| R7 S1 TI | 10 | S1 Teknik Informatika | STRONG | 10 |
| R8 Sertifikasi cloud | 5 | — | NOT_DEMONSTRATED | 0 |
| R9 Pencapaian terukur | 8 | "Improved checkout API response time by 40%…" | STRONG | 8 |
| R10 Memimpin tim | 7 | — | NOT_DEMONSTRATED | 0 |
| **Total** | 100 | | | **77** |

R3 wajib dan bukan `STRONG` → `n = 1` → band B → skor akhir `min(77, 74) = 74`, rekomendasi "Perlu ditinjau".
Saran pertanyaan: "Seberapa jauh pengalaman Python Anda di pekerjaan?".

## 13. Versioning

Setiap screening run menyimpan versi: requirement set, rubrik/aturan (`scoring_version`, mis. `score-1.0.0`),
taksonomi, parser/extractor, model embedding, reranker, LLM verifier + prompt, dan `as_of`. Mengubah salah
satu = run baru. UI bisa menampilkan selisih antar run: *"Kandidat X turun dari #3 ke #8 karena bobot
Kubernetes diubah dari 6 ke 15 dan buktinya PARTIAL."*

## 14. Larangan

- LLM mengeluarkan skor numerik untuk kandidat.
- Memakai nama, foto, umur, gender, agama, status nikah, alamat lengkap, nama kampus, IPK, gap kerja, hobi,
  atau aktivitas media sosial sebagai faktor skor.
- Mengubah bobot otomatis berdasarkan keputusan rekrutmen sebelumnya.
- Menampilkan "Reject" sebagai rekomendasi mesin.
