# Evaluasi Objektif & Analisis Forensik Hasil Screening 19 CV Backend Developer (v2.1)

**Tanggal Evaluasi:** 26 Oktober 2026  
**Objek Pengujian:** 19 Berkas CV Riil (`Backend Developer - Sharing Happiness-20261012T052712Z-1-001.zip`)  
**ID Lowongan:** `01401abc-3fc8-4d92-a805-6b5cc3790339`  
**Run ID Screening:** `efb2c1c7-efb2-4525-ae13-083fad373101`  
**Tujuan Audit:** Mengevaluasi kesesuaian putusan sistem terhadap realitas berkas pelamar secara objektif, mengidentifikasi putusan yang akurat, serta membongkar kasus-kasus yang kurang tepat (*false penalties / edge cases*).

---

## 1. Ringkasan Eksekutif Hasil Evaluasi

Dari 19 berkas pelamar yang diuji:
- **Akurasi Putusan Keseluruhan:** **~84.2% (16 dari 19 kandidat dinilai dengan sangat tepat)**.
- **Kekuatan Utama Terbukti:**
  1. Sukses mengidentifikasi **Top 2 Kandidat Terbaik** (Norma Rosita & Denis Hanif) dengan skor sempurna 100.0 (Band A Shortlist).
  2. Sukses menolak 100% berkas yang rusak, salah kamar, hasil scan murni foto (CamScanner), dan teks manipulatif (Peringkat #14 s.d. #19).
  3. Berhasil mendeteksi kandidat yang salah posisi (seperti Tiara Rahmania yang dominan Frontend).
- **Kelemahan & Anomali Teridentifikasi:**
  1. **Hukuman Terlalu Keras (*Overly Punitive*):** Muhammad Akil meraih skor **92.1**, namun dijatuhkan ke **Band R (Perlu Cek Manual)** hanya karena pemicu `AGENT_DISAGREEMENT` minor antara Gemini dan Claude.
  2. **Jebakan Kata Kunci Harfiah (*Literal Keyword Trap*):** Oki Iskandar (engineer Indodax & BRILink) dijatuhkan ke skor **50.0 Band R** karena peluru riwayat kerjanya tidak menyebutkan kata "PostgreSQL/MySQL" secara harfiah, meskipun portofolionya menangani sistem transaksi finansial bervolume jutaan pengguna.
  3. **Efek Domino Poin Rata (*Flat 50 Cluster*):** Sebanyak 8 kandidat (Rank #5 s.d. #12) mendapatkan nilai yang sama persis (**50.0**) karena salah satu facet pokok (*core facet*) di-downgrade menjadi `PARTIAL`, yang otomatis menyeret seluruh kriteria turunan menjadi `PARTIAL`.

---

## 2. Analisis Rinci per Berkas Kandidat (19 CV)

### Kelompok 1: Juara Shortlist (Rank #1 & #2) — Sangat Sesuai ✅

#### #1. Norma Rosita Damayanthi (`C-0001`) — Skor: 100.0 | Band A | SHORTLIST
* **Kenyataan di CV:** 38 bulan pengalaman kerja backend. Menguasai arsitektur backend modern: NestJS, Express.js, TypeScript, PostgreSQL, TypeORM, Redis, Docker, dan arsitektur microservices di 3 perusahaan berbeda (PT Inovasi Dinamika Solusi, CBA Digitechno, Todis Karya Bangsa).
* **Putusan Sistem:** Seluruh 6 kriteria (`R1 s.d. R6`) dinilai `STRONG` pada level kedalaman L2–L3 dengan kutipan bukti proyek konkret.
* **Kesimpulan Audit:** **100% TEPAT.** Kandidat paling siap pakai dan relevan dengan stack backend modern.

#### #2. Denis Hanif Prasetya (`C-0002`) — Skor: 100.0 | Band A | SHORTLIST
* **Kenyataan di CV:** Memiliki **111 bulan kalender murni** (9+ tahun jam terbang). Sangat matang di ekosistem PHP/Laravel, REST API performa tinggi, optimasi query database relasional, dan integrasi payment gateway.
* **Putusan Sistem:** Seluruh 6 kriteria `STRONG`. Fitur auto-redaction berhasil menyensor nomor HP tanpa merusak berkas.
* **Kesimpulan Audit:** **100% TEPAT.** Profil Senior/Lead Backend yang sangat berpengalaman di industri.

---

### Kelompok 2: Kasus Anomali / Kurang Tepat (Rank #3 & #10) — Butuh Penyesuaian ⚠️

#### #3. Muhammad Akil (`C-0003`) — Skor: 92.1 | Band R | MANUAL_CHECK
* **Kenyataan di CV:**
  - Jabatan: *Lead Fullstack & Backend Developer* di PT Satustop Finansial Solusi (crowdfunding fintech) dan PT Rumah Logic Teknologi.
  - Keahlian: Golang (Gin, GORM), PHP (Laravel, CI), PostgreSQL, MySQL, REST API, RBAC otentikasi.
  - Pengalaman: Memimpin arsitektur sistem backend fintech dan transaksi finansial.
* **Putusan Sistem:**
  - Poin murni: **92.1** (R1, R2, R3, R5 berstatus `STRONG`; R4 dan R6 berstatus `PARTIAL`).
  - Band: **Band R** (Rekomendasi: `MANUAL_CHECK`).
* **Mengapa Jatuh ke Band R?**
  1. Claude Critic mendowngrade Facet B2 (database) dari ENTAILED ke PARTIAL (alasan: bukti database dianggap kurang spesifik di teknik optimasi).
  2. Perbedaan antara Gemini (lolos) dan Claude (sebagian) memicu bendera `AGENT_DISAGREEMENT`.
  3. Parser gagal mengekstrak nama di baris paling atas sehingga memicu bendera `Nama tidak ditemukan`.
  4. Di kode `scorer_v2.py`: `if must_unknown or has_agent_disagreement: band = "R"`.
* **Kesimpulan Audit:** **KURANG TEPAT (Terlalu Kaku).**  
  Akil jelas merupakan kandidat nomor 3 terbaik di seluruh berkas. Menjatuhkan kandidat berskor 92.1 ke Band R (setara dengan berkas bernilai 0) adalah penalti yang berlebihan. Akil seharusnya masuk ke **Band B (Dipertimbangkan)**.

#### #10. Oki Iskandar (`C-0010`) — Skor: 50.0 | Band R | MANUAL_CHECK
* **Kenyataan di CV:**
  - Bekerja di **PT Indodax Nasional Indonesia** (Software Engineer backend platform trading crypto jutaan user).
  - Menangani proyek **BRILink** di PT Lawencon Internasional (layanan branchless banking BRI berbasis microservices).
  - Mengembangkan sistem order matching, deposit/withdrawal, Deadman switch, dan fee components.
* **Putusan Sistem:**
  - Seluruh 6 kriteria dinilai `PARTIAL`, menghasilkan skor datar **50.0 (Band R)**.
* **Mengapa Cuma Dapat 50.0?**
  - Oki menulis fitur bisnis (*trading engine, fee components, BRILink microservices*), tetapi di peluru uraian kerjanya **dia tidak menuliskan kata "PostgreSQL" atau "MySQL" secara harfiah** (kata "Database" hanya ditulis di daftar skill atas / T0).
  - Critic Agent mengunci kriteria database di level **L0 (Unproven)** karena menganggap database hanya klaim T0 tanpa implementasi di deskripsi proyek.
  - Karena database adalah *core facet*, seluruh kriteria turunan ikut terkunci di level `PARTIAL`.
* **Kesimpulan Audit:** **KURANG TEPAT (Jebakan Kata Kunci Harfiah).**  
  Sistem gagal menyimpulkan (*infer*) bahwa seorang backend engineer platform trading Indodax dan perbankan BRILink secara mutlak pasti mengelola basis data relasional transaksional ACID. Oki seharusnya memperoleh skor di kisaran **70–80 (Band B)**.

---

### Kelompok 3: Klaster Skor Datar 50.0 (Rank #4 s.d. #13) — Cukup Tepat 🟡

Kandidat-kandidat pada kelompok ini mendapatkan skor datar di kisaran **46.6 s.d. 57.9**:

#### #4. Ihsan Zaky Fadillah (`C-0004`) — Skor: 57.9 | Band R
* **Kenyataan:** Bagus di REST API Laravel dan clean code, tetapi jam terbang backend-nya baru 1 tahunan dan banyak mengerjakan tugas hybrid frontend Ionic/Vue. Putusan: **Cukup Tepat.**

#### #5. Umar Sabirin (`C-0005`) — Skor: 50.0 | Band R
* **Kenyataan:** Terlalu banyak mencantumkan keahlian di bio (*High T0 Ratio*), bukti kerja nyata di backend berskala besar masih terbatas. Putusan: **Tepat.**

#### #6. Harun Al Rasyid (`C-0006`) — Skor: 50.0 | Band R
* **Kenyataan:** Pengalaman backend belum mencapai 2 tahun penuh; portofolio lebih dominan ke web internal sederhana. Putusan: **Tepat.**

#### #7. Tiara Rahmania Hadiningrum (`C-0007`) — Skor: 50.0 | Band R
* **Kenyataan:** Profil aslinya adalah **Frontend Developer** (React, Tailwind CSS, UI/UX). Pengetahuan backend hanya bersifat incidental/dasar. Putusan: **Sangat Tepat (Bukan Spesialis Backend).**

#### #8. Fiqri Khoirul Muttaqin (`C-0008`) — Skor: 50.0 | Band R
* **Kenyataan:** Terbiasa dengan MVC dasar, tetapi belum terbukti menangani arsitektur REST API berkinerja tinggi atau payment gateway. Putusan: **Tepat.**

#### #9. Elsa Noviani Putri (`C-0009`) — Skor: 50.0 | Band R
* **Kenyataan:** Mencantumkan jabatan *Technical Leader*, tetapi bukti atom di dalamnya menunjukkan tugas backend PHP/Laravel biasa tanpa bukti kepemimpinan teknis yang kokoh. Sistem berhasil mencegah *Title Inflation*. Putusan: **Tepat.**

#### #11. Ahmad Habibul Ulum (`C-0011`) — Skor: 50.0 | Band R
* **Kenyataan:** Banyak memegang peran QA Automation, testing, dan IT support. Hasil scan dokumen memiliki banyak derau (*OCR noise*). Putusan: **Tepat.**

#### #12. Muhammad Ilham Rafiannandha (`C-0012`) — Skor: 50.0 | Band R
* **Kenyataan:** Menumpuk daftar 150 skill di bagian resume, tetapi jam terbang kerjanya masih di level magang/junior. Aturan anti-stuffing berhasil mengunci skornya. Putusan: **Tepat.**

#### #13. Mauludy Rakhman (`C-0013`) — Skor: 46.6 | Band R
* **Kenyataan:** Pengalaman terpecah antara frontend dan backend, kriteria payment gateway dan arsitektur aman dinyatakan `NOT_DEMONSTRATED`. Putusan: **Tepat.**

---

### Kelompok 4: Ditolak / Nilai Nol (Rank #14 s.d. #19) — 100% Sangat Tepat ⛔

Kelompok ini berisi berkas yang tidak memenuhi kualifikasi mendasar, salah format, atau bukan dokumen CV:

* **#14. Yadi Apriyadi (Skor: 4.5):** Teks sangat minim, sebagian besar klaim terfragmentasi dan terdeteksi teks tersembunyi.
* **#15. Lana Septiana (Skor: 0.0):** Pengalaman di bidang *Product Strategy, UI/UX, dan Prototyping*, bukan pengembang kode backend.
* **#16. Natalino Marulitua Manuel Bryan (Skor: 0.0):** Berkas hasil scan CamScanner di mana 9 dari 10 halaman adalah foto gambar ijazah/KTP/sertifikat tanpa layer teks; pengalaman kerjanya admin gudang/logistik.
* **#17. Asep Suratno (Skor: 0.0):** Format tabel CV berulang dan rusak (*parser repetition detected*), tidak ada bukti REST API terstruktur.
* **#18. Zulfan Nurrahman (Skor: 0.0):** Dokumen mengandung teks sembunyi dan anomali header.
* **#19. Rizal Maulana Yusuf (Skor: 0.0):** Berkas gabungan (*merged PDF*) yang didominasi scan gambar tanpa teks mesin.

---

## 3. Evaluasi Masalah Sistemik: "Klaster Datar 50.0"

Mengapa ada **8 kandidat berbeda** yang memperoleh skor yang sama persis (**50.0**)?

### Penyebab Teknis di Kode (`screening_pipeline.py` & `aggregator.py`):
1. **Pewarisan Facet Global:** Saat ini, lowongan kerja menetapkan 5 facet kesetaraan peran (*Role Equivalence Facets* `B1` s.d. `B5`) ke seluruh kriteria `R1` sampai `R6`.
2. **Ketergantungan Core Facet:** Tiga facet (`B1: REST API`, `B2: Database`, `B3: Logika Bisnis`) ditetapkan sebagai `core = True`.
3. **Logika All-or-Nothing:** Di `aggregator.py`:
   - Jika salah satu core facet (misal B2 database) turun menjadi `PARTIAL` karena kritik Claude Critic, maka syarat `all_core_entailed = True` langsung **gugur**.
   - Akibatnya, status kriteria turun dari `STRONG` menjadi **`PARTIAL`**.
   - Karena kriteria R1 sampai R6 semuanya mengacu pada kombinasi facet yang sama, **seluruh 6 kriteria serentak berubah menjadi `PARTIAL`**.
   - Di Scorer v2: $\text{Poin} = 0.5 \times 100\% = \mathbf{50.0}$.

### Dampak:
Hal ini menyebabkan sistem kehilangan daya beda (*granularity*) untuk kandidat di tingkat menengah. Kandidat yang memiliki pengalaman 3 tahun di Indodax (Oki Iskandar) mendapatkan nilai yang persis sama dengan kandidat junior yang baru magang (Harun Al Rasyid).

---

## 4. Rekomendasi Solusi Teknis untuk Versi 2.2

Untuk menyempurnakan kelemahan di atas tanpa mengorbankan keamanan sistem:

### 1. Pelunakan Aturan `AGENT_DISAGREEMENT` di `scorer_v2.py`:
- **Saat ini:** Setiap kali ada bendera `AGENT_DISAGREEMENT`, kandidat otomatis dikunci ke `Band R` (Skor berapa pun).
- **Perbaikan:**  
  Jika kandidat memiliki skor akhir $\ge 75.0$ dan hanya memiliki 1 downgrade dari Critic, tetapkan ke **`Band B (Dipertimbangkan)`**, bukan `Band R`. Dengan demikian, kandidat hebat seperti **Muhammad Akil (92.1)** akan otomatis masuk ke radar rekruter.

### 2. Inferensi Domain untuk Basis Data (*Domain-Context Implication*):
- Tambahkan aturan logika di ontologi: jika pelamar terbukti mengimplementasikan arsitektur berkinerja tinggi (*fintech, trading platform, banking microservices, payment processing*), sistem otomatis memberikan kredit dasar database relasional pada level **L2**, sehingga tidak dihukum L0 hanya karena tidak menuliskan kata "PostgreSQL".

### 3. Pemisahan Facet Spesifik per Kriteria:
- Jangan memasang 5 facet generik ke semua kriteria. Kriteria database (`R4`) seharusnya hanya diuji oleh facet database (`B2`), kriteria bahasa backend (`R2`) hanya diuji oleh facet bahasa (`B1`), sehingga kegagalan satu facet tidak merembet menjatuhkan nilai kriteria lainnya menjadi datar 50.
