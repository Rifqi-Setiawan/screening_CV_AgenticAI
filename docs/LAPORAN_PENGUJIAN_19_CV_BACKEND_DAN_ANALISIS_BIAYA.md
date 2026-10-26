# Laporan Pengujian Evaluasi 19 CV Riil Backend Developer & Analisis Biaya Token (v2.1)

**Tanggal Pengujian:** 26 Oktober 2026  
**Dataset Pengujian:** `Backend Developer - Sharing Happiness-20261012T052712Z-1-001.zip` (19 CV Pelamar Riil + `cv_index.csv`)  
**ID Lowongan:** `01401abc-3fc8-4d92-a805-6b5cc3790339`  
**Run ID Screening:** `efb2c1c7-efb2-4525-ae13-083fad373101` (Status: `COMPLETED`)  
**Hasil di Web:** Tayang langsung di [https://agentic-screening.rifqisetiawan.my.id/](https://agentic-screening.rifqisetiawan.my.id/) pada menu **3. Leaderboard (19)**.

---

## 1. Ringkasan Hasil Peringkat Leaderboard (19 Kandidat)

Dari 19 berkas pelamar riil yang dievaluasi secara objektif terhadap 6 kriteria lowongan (*Pengalaman Min. 2 Tahun, Bahasa Backend, REST API, Database SQL, Clean Code, Payment Gateway*):

| Rank (#) | ID Samaran | Nama Berkas / Kandidat | Skor Akhir | Band | Syarat Wajib | Rekomendasi Sistem | Status Kelulusan |
| :---: | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **#1** | `C-0001` | `3598_Norma Rosita Damayanthi` | **100.0** | **Band A** | 3/3 Wajib | Disarankan Shortlist | 🟢 **Lolos Wawancara** |
| **#2** | `C-0002` | `3553_Denis Hanif Prasetya` | **100.0** | **Band A** | 3/3 Wajib | Disarankan Shortlist | 🟢 **Lolos Wawancara** |
| **#3** | `C-0003` | `3548_Muhammad Akil` | **92.1** | Band R | 3/3 Wajib | Perlu Cek Manual | 🟡 Cek Manual (Nama Header) |
| **#4** | `C-0004` | `3534_Ihsan Zaky Fadillah` | **57.9** | Band R | 1/3 Wajib | Perlu Cek Manual | 🔴 Review (Klaim Auth L1) |
| **#5** | `C-0005` | `3542_Umar Sabirin` | **50.0** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 T0 Rasio Tinggi (L0 Lock) |
| **#6** | `C-0006` | `4419_Harun Al Rasyid` | **50.0** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 Pengalaman Belum Terbukti |
| **#7** | `C-0007` | `3532_Tiara Rahmania Hadiningrum` | **50.0** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 Dominan Frontend |
| **#8** | `C-0008` | `3868_Fiqri Khoirul Muttaqin` | **50.0** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 Belum Ada REST API Riil |
| **#9** | `C-0009` | `3734_Elsa Noviani Putri` | **50.0** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 Jam Terbang Kurang |
| **#10** | `C-0010` | `3605_Oki Iskandar` | **50.0** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 Teks Tersembunyi (L0 Lock) |
| **#11** | `C-0011` | `3531_Ahmad Habibul Ulum` | **50.0** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 OCR Bleed / Noise Parah |
| **#12** | `C-0012` | `3599_Muhammad Ilham Rafiannandha` | **50.0** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 Skill Tanpa Bukti Kerja |
| **#13** | `C-0013` | `3585_Mauludy Rakhman` | **46.6** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 Kompetensi Tidak Cukup |
| **#14** | `C-0014` | `3554_Yadi Apriyadi` | **4.5** | Band R | 0/3 Wajib | Perlu Cek Manual | 🔴 Berkas Terfragmentasi |
| **#15** | `C-0015` | `3716_Lana Septiana` | **0.0** | Band R | 0/3 Wajib | Perlu Cek Manual | ⛔ Tidak Sesuai Syarat |
| **#16** | `C-0016` | `3998_Natalino Marulitua M. Bryan` | **0.0** | Band R | 0/3 Wajib | Perlu Cek Manual | ⛔ Scan Gambar (CamScanner) |
| **#17** | `C-0017` | `3539_Asep Suratno` | **0.0** | Band R | 0/3 Wajib | Perlu Cek Manual | ⛔ Parser Repetition Flag |
| **#18** | `C-0018` | `3543_Zulfan Nurrahman` | **0.0** | Band R | 0/3 Wajib | Perlu Cek Manual | ⛔ Teks Tersembunyi & Format |
| **#19** | `C-0019` | `4871_Rizal Maulana Yusuf` | **0.0** | Band R | 0/3 Wajib | Perlu Cek Manual | ⛔ File Merged Tanpa Layer |

---

## 2. Durasi Waktu Pemrosesan per Tahap

| Tahapan Sistem | Durasi Waktu Total | Durasi Rata-rata per 1 CV | Keterangan Teknis |
| :--- | :---: | :---: | :--- |
| **Tahap 1: Ekstraksi & Ingestion Berkas** | **~8 Menit 56 Detik** | ~28.2 Detik / CV | Penguraian PDF PyMuPDF, sanitasi biner, sensor PII regex, pemotongan Evidence Atoms, dan embedding vektor Harrier-270m di CPU server. |
| **Tahap 2: Evaluasi Kriteria (Matcher Agent)** | **~38 Menit 10 Detik** | ~120.5 Detik / CV | Panggilan asinkron ke Gemini 3.8 Flash untuk 6 kriteria per pelamar (Total 353 panggilan API). |
| **Tahap 3: Audit Kritis (Claude Critic Agent)** | **~21 Menit 50 Detik** | ~34.8 Detik / kandidat | Evaluasi silang adversarial oleh Claude Sonnet 5.5 untuk kandidat yang memicu pemicu E1–E6 (Total 47 panggilan API). |
| **Tahap 4: Sweep-Line & Scoring Deterministik** | **~0.4 Detik** | ~0.02 Detik / CV | Perhitungan matematika murni Python: penggabungan kalender kerja, normalisasi dua lapis, dan penentuan Band A/B/C/R. |
| **TOTAL WAKTU END-TO-END (19 CV)** | **1 Jam 00 Menit 04 Detik** | **~3 Menit 09 Detik / CV** | **Selesai 100% tanpa crash, tanpa timeout, dan tanpa data loss.** |

---

## 3. Analisis Penggunaan Token & Biaya Riil (Cost Breakdown)

Data diambil langsung dari audit telemetri database 9Router (`data.sqlite`) selama run ID `efb2c1c7-efb2-4525-ae13-083fad373101` berlangsung (13:30:32 WIB s.d. 14:30:36 WIB):

### A. Total Token Seluruh Model (19 CV):
- **Gemini 3.8 Flash (Matcher Agent):**
  - Prompt Tokens (Input): **1.660.911 tokens**
  - Completion Tokens (Output): **188.375 tokens**
  - *Total Token Gemini:* **1.849.286 tokens**
- **Claude Sonnet 5.5 (Critic Agent):**
  - Prompt Tokens (Input): **388.834 tokens**
  - Completion Tokens (Output): **185.804 tokens**
  - *Total Token Claude:* **574.638 tokens**
- **GRAND TOTAL SEMUA TOKEN:** **2.423.924 tokens**

### B. Biaya Finansial Riil (*Pricing Calculation*):
*Harga Standar: Gemini Flash (Input $0.075/1M, Output $0.30/1M); Claude Sonnet (Input $3.00/1M, Output $15.00/1M). Kurs: $1 = Rp 15.800.*

- **Biaya Gemini Flash (353 Panggilan API):**
  - Input: $1.660.911 \times \$0.075 / 1\text{M} = \$0.1246$
  - Output: $188.375 \times \$0.30 / 1\text{M} = \$0.0565$
  - *Subtotal Gemini:* **$0.1811** ($\approx$ **Rp 2.861,-**)
- **Biaya Claude Sonnet 5.5 (47 Panggilan Audit Kritis):**
  - Input: $388.834 \times \$3.00 / 1\text{M} = \$1.1665$
  - Output: $185.804 \times \$15.00 / 1\text{M} = \$2.7871$
  - *Subtotal Claude:* **$3.9536** ($\approx$ **Rp 62.466,-**)
- **TOTAL BIAYA EVALUASI 19 CV:** **$4.1346** ($\approx$ **Rp 65.327,-**)

### C. Rata-rata Biaya per 1 Berkas CV:
- Rata-rata Token per CV: **127.575 tokens**
- Rata-rata Biaya per CV: **$0.217** ($\approx$ **Rp 3.438,- per berkas pelamar**)
*(Catatan: Biaya Gemini per CV hanya Rp 150,-; sebagian besar biaya Rp 3.200,- disumbangkan oleh audit teliti Claude Sonnet 5.5 untuk membongkar manipulasi resume).*

---

## 4. Evaluasi Bukti Kandidat Unggulan (Top 2 Shortlist)

### 🥇 Peringkat #1: Norma Rosita Damayanthi (Skor: 100.0, Band A)
- **Jam Terbang Relevan:** Terbukti 38 bulan sebagai Backend / Fullstack Developer.
- **Teknologi Terverifikasi:** Menguasai NestJS, Express.js, TypeScript, PostgreSQL, TypeORM, Redis, dan Docker.
- **REST API & Integrasi:** Membangun core endpoint API untuk sistem pembayaran dan microservices.
- **Audit Critic:** Tidak ditemukan teks tersembunyi; seluruh klaim kompetensi bersandar pada atom bukti proyek riil.

### 🥈 Peringkat #2: Denis Hanif Prasetya (Skor: 100.0, Band A)
- **Jam Terbang Relevan:** Terbukti **111 bulan kalender murni** (Sweep-line duration) tanpa tumpang tindih palsu.
- **Teknologi Terverifikasi:** Menguasai arsitektur PHP/Laravel performa tinggi, REST API multi-tier, optimasi query database relasional, dan integrasi payment gateway.
- **Sanitasi PII:** Nomor kontak ber-strip (`+62 813-1922-9466`) berhasil disanitasi otomatis oleh Gateway menjadi `[KONTAK_HR]` tanpa menggugurkan berkas.
- **Audit Critic:** Status PASS penuh, dinilai sangat matang untuk posisi Senior/Lead Backend.
