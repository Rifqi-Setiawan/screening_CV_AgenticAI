# 08. Tahap 8: Scorer v2 — Komputasi Matematika & Sistem Band Leaderboard

Dokumen ini menjelaskan implementasi mesin penghitung skor akhir (*Scorer v2*) pada `src/domain/scoring/scorer_v2.py`, logika normalisasi dua lapis, aturan penguncian kriteria wajib (*Hard Gate MUST_HAVE*), sistem penentuan Band kelulusan (Band A, B, C, R), serta penyajian hasil pada antarmuka pengguna (*HR Leaderboard & Candidate Drawer*).

---

## 1. Rumus Komputasi Matematika Scorer v2

Seluruh angka skor akhir dihitung menggunakan fungsi matematika murni Python tanpa melibatkan perkiraan atau tebakan LLM.

### A. Penghitungan Poin per Kriteria
Untuk setiap kriteria lowongan ($R_i$), poin yang diperoleh kandidat dihitung dengan rumus:
$$\text{Poin Terbobot}(R_i) = W_i \times S(st_i) \times D(d_i)$$

Keterangan:
- $W_i$: Bobot poin kriteria yang ditentukan di tabel kriteria (misal: 25 poin, 20 poin, dst.).
- $S(st_i)$: Faktor nilai status pemenuhan:
  - `STRONG` = `1.0`
  - `PARTIAL` = `0.5`
  - `NONE` / `UNKNOWN` = `0.0`
- $D(d_i)$: Faktor pengali level kedalaman (*Depth Factor*):
  - `L4` (Leadership / Architect) = `1.0`
  - `L3` (Advanced Specialist) = `0.9`
  - `L2` (Independent Practitioner) = `0.7`
  - `L1` (Basic Exposure / Academic) = `0.4`
  - `L0` (Unproven / Keyword Only) = `0.0`

---

## 2. Normalisasi Skor Kategori (0 – 100%)

Kriteria dikelompokkan ke dalam 4 kategori fungsional:
1. `EXPERIENCE` (Pengalaman Kerja)
2. `HARD_SKILLS` (Keahlian Teknis & Bahasa Pemrograman)
3. `EDUCATION_CERT` (Pendidikan & Sertifikasi)
4. `ACHIEVEMENT` (Pencapaian Terukur & Kepemimpinan)

Skor untuk masing-masing kategori dihitung secara persentase proporsional:
$$\text{Skor Kategori}(C) = \left( \frac{\sum_{i \in C} \text{Poin Terbobot}(R_i)}{\sum_{i \in C} W_i} \right) \times 100\%$$

### Fitur Skalasi Otomatis (*Automatic Category Rebalancing*):
Jika sebuah lowongan kerja **tidak mencantumkan kriteria tertentu** (contoh: lowongan Sharing Happiness hanya menetapkan kriteria *Pengalaman* dan *Hard Skill*, sedangkan *Pendidikan* dan *Pencapaian* kosong):
- Sistem **tidak memotong nilai kandidat**.
- Sistem hanya menjumlahkan bobot makro kategori yang aktif dari Card Atas ($40\% + 30\% = 70\%$).
- Total nilai aktif tersebut kemudian diskalakan ulang (*renormalized*) menjadi **100% penuh**:
  $$\text{Bobot Efektif Pengalaman} = \frac{40}{70} = 57.1\%$$
  $$\text{Bobot Efektif Hard Skill} = \frac{30}{70} = 42.9\%$$

---

## 3. Komputasi Skor Akhir Rapor (Skala 0 – 100)

Nilai akhir kandidat dihitung dengan menggabungkan skor persentase kategori dengan bobot makro efektifnya:
$$\text{Skor Akhir} = \sum_{C} \left( \text{Skor Kategori}(C) \times \text{Bobot Efektif}(C) \right)$$

Hasilnya adalah angka desimal presisi satu angka di belakang koma (contoh: `84.5`, `100.0`, `50.0`).

---

## 4. Logika Penentuan Band Kelulusan (Band A, B, C, R)

Sistem menerapkan **Gerbang Kriteria Wajib (*Hard Gate MUST_HAVE*)**. Kandidat tidak bisa lulus hanya karena nilai totalnya tinggi jika ada syarat mutlak yang gagal dipenuhi!

```text
               [ HASIL SKOR AKHIR & STATUS KRITERIA ]
                                │
                                ▼
         Apakah Ada Syarat MUST_HAVE yang Bernilai NONE / UNKNOWN?
         ├── Ya ──► [ BAND R ]: Ditolak / Perlu Review Manual Khusus
         └── Tidak
              │
              ▼
         Apakah SEMUA Syarat MUST_HAVE Terbukti STRONG?
         ├── Ya
         │    ├── Skor Akhir >= 80 ──► [ BAND A ]: Shortlist Prioritas Utama
         │    └── Skor Akhir < 80  ──► [ BAND B ]: Dipertimbangkan
         │
         └── Tidak (Ada 1 Syarat MUST_HAVE yang Berstatus PARTIAL)
              ├── Skor Akhir >= 65 ──► [ BAND B ]: Dipertimbangkan
              └── Skor Akhir < 65  ──► [ BAND C ]: Prioritas Rendah
```

### Rincian Klasifikasi Band:
- **Band A (Shortlist Prioritas Utama):**  
  Skor $\ge 80.0$ **DAN** seluruh kriteria bertingkat `MUST_HAVE` terbukti `STRONG`. Kandidat ini adalah talenta terbaik yang memenuhi seluruh syarat mutlak dan memiliki keahlian mendalam.
- **Band B (Dipertimbangkan / Talent Pool):**  
  Skor $\ge 65.0$, tetapi terdapat maksimal 1 kriteria `MUST_HAVE` yang berstatus `PARTIAL` (misal: jam terbang baru 1.8 tahun dari syarat minimal 2 tahun, tetapi keahlian teknisnya sangat memuaskan).
- **Band C (Prioritas Rendah):**  
  Skor $50.0 \le \text{Skor} < 65.0$, atau terdapat lebih dari 1 syarat wajib yang belum memuaskan.
- **Band R (Ditolak / Review Manual Khusus):**  
  Skor $< 50.0$, atau terdapat kriteria wajib yang bernilai `NONE` (sama sekali tidak bisa), atau terjadi pertentangan tajam antar-agen (*Agent Disagreement*).

---

## 5. Fitur Antarmuka Pengguna (Leaderboard & Drawer Detail)

Pada Step 3 antarmuka web (`frontend/src/App.tsx`):

1. **Papan Peringkat Leaderboard:**
   - Menampilkan urutan kandidat dari peringkat #1 ke bawah berdasarkan kombinasi Band dan Skor Akhir.
   - Dilengkapi tab filter cepat (*Semua, Band A, Band B, Band C*).
   - Menampilkan visual indikator bulat untuk pemenuhan kriteria wajib (Hijau = Strong, Kuning = Partial, Abu-abu = None).
   - Menampilkan progress bar visual perbandingan kontribusi kategori (*Pengalaman vs Hard Skill vs Pendidikan*).
2. **Laci Kandidat Interaktif (*Candidate Detail Drawer*):**
   - Mengklik nama kandidat membuka drawer samping selebar 55% layar.
   - Menampilkan tab: **Ringkasan Evaluasi**, **Kartu Skor Lengkap**, **Teks CV Asli Tersanitasi**, dan **Riwayat Keputusan**.
   - Menampilkan kutipan atom bukti asli yang mendasari setiap penilaian kriteria.
3. **Tabel Berkas Dikecualikan (*Excluded / Flagged Documents Table*):**
   - Menampung berkas yang bermasalah (hasil scan gambar tanpa layer teks, dokumen rusak, file duplikat, atau berkas bukan CV).
   - Menampilkan alasan teknis transparan dan menyediakan tombol aksi perbaikan cepat (`↺ Ulang` atau `🗑 Hapus`).

Dengan rancangan ini, seluruh proses dari pemilihan lowongan hingga penetapan keputusan kerja berjalan secara transparan, adil, objektif, dan dapat dipertanggungjawabkan secara hukum! 🚀
