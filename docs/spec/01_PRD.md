# 01 — PRD: Sistem Screening CV Berbasis Bukti

| | |
| --- | --- |
| Versi | 1.0 (MVP) |
| Tanggal | 9 Oktober 2026 |
| Pemilik produk | Zafira |
| Status | Disetujui untuk dibangun |

## 1. Ringkasan

Aplikasi web yang membantu recruiter menemukan 5–10 kandidat paling cocok dari ratusan CV untuk satu lowongan.
Sistem membaca CV, menilai setiap CV **per kriteria lowongan** dengan **bukti kutipan dari CV**, lalu menyusun
peringkat yang bisa dijelaskan. **Keputusan akhir selalu di tangan manusia.** Sistem tidak menolak kandidat
secara otomatis.

## 2. Problem statement

- Satu lowongan bisa menerima 100–500 CV. Recruiter membaca manual sekitar 1–3 menit per CV, jadi butuh
  5–25 jam kerja hanya untuk screening awal.
- Screening manual tidak konsisten: kandidat ke-250 dibaca dengan energi berbeda dari kandidat ke-5.
- Filter kata kunci ATS biasa kaku ("Postgres" ≠ "PostgreSQL") dan mudah diakali (keyword stuffing, teks putih).
- "Melempar semua CV ke ChatGPT" mahal, hasilnya berubah-ubah, rawan halusinasi dan prompt injection,
  dan tidak bisa diaudit.

**Target hasil (hipotesis yang diuji saat pilot):** shortlist awal dari 300 CV, termasuk waktu review
recruiter, selesai **di bawah 60 menit**. Pemrosesan mesin selesai **di bawah 15 menit** setelah upload.

## 3. Pengguna

| Peran | Kebutuhan | Hak akses |
| --- | --- | --- |
| **HR Recruiter** | Membuat lowongan, mengunggah CV, menyetujui kriteria, meninjau ranking, memutuskan shortlist | Penuh di lowongan miliknya |
| **Hiring Manager** | Melihat shortlist, membaca bukti, memberi komentar dan rekomendasi | Baca + komentar pada lowongan yang dibagikan |
| **Admin** | Mengelola pengguna, template bobot, pengaturan retensi data, melihat audit log | Penuh, termasuk audit |

## 4. Prinsip produk (tidak boleh dilanggar)

1. **Manusia yang memutuskan.** Sistem memberi rekomendasi dan bukti. Tidak ada penolakan atau email otomatis.
2. **Tidak ada klaim tanpa bukti.** Setiap klaim tentang kandidat menunjuk kutipan persis di CV.
3. **Skor bisa diurai.** Tidak ada satu angka misterius. Skor = jumlah bobot × status per kriteria.
4. **"Tidak tercantum" ≠ "tidak bisa".** Bahasa di UI harus mencerminkan ini.
5. **Blind screening.** Nama, foto, umur, jenis kelamin, agama, status pernikahan, dan alamat lengkap tidak ikut
   dinilai.
6. **Bisa diulang.** Screening yang sama dengan konfigurasi sama menghasilkan urutan yang sama persis.

## 5. Fitur inti (scope MVP)

| # | Fitur | Kriteria penerimaan (acceptance criteria) |
| --- | --- | --- |
| F1 | **Input lowongan (JD)** | Recruiter bisa paste teks atau upload PDF/DOCX JD. Judul, lokasi, dan tipe kerja bisa diisi. |
| F2 | **Penyusunan kriteria otomatis + persetujuan** | Sistem membuat draf kriteria (wajib / diutamakan / nilai tambah, kategori, bobot) dalam < 60 detik. Recruiter bisa mengubah, menambah, menghapus, dan mengatur bobot. Kriteria diskriminatif (usia, jenis kelamin, agama, penampilan, status nikah) ditandai dan **tidak bisa** dipakai. Screening tidak bisa dimulai sebelum kriteria disetujui. |
| F3 | **Bulk upload CV** | Drag-and-drop hingga 500 file per batch (PDF, DOCX, DOC, JPG/PNG), atau satu file ZIP. Maks 10 MB dan 20 halaman per file. Progress bar per file dan total ("Memproses 15/50 CV…"). File gagal ditampilkan dengan alasannya, tidak hilang diam-diam. |
| F4 | **Tabel ranking** | Kandidat dikelompokkan per band (A/B/C dan "Perlu cek manual"), lalu diurutkan berdasarkan skor. Kolom: peringkat, kode/nama kandidat, skor (0–100, berwarna), band, rekomendasi, ringkasan kriteria wajib. Bisa disaring dan diurutkan. |
| F5 | **Alasan (reasoning) berbasis bukti** | Untuk tiap kandidat: status per kriteria, kutipan CV + nomor halaman, kelebihan, kriteria yang belum terbukti, dan saran pertanyaan interview. Perbandingan "kenapa A di atas B" ditampilkan per kriteria. |
| F6 | **Panel detail kandidat** | Klik baris membuka panel samping berisi ringkasan profil, kartu skor, bukti, dan preview CV asli dengan kutipan disorot. |
| F7 | **Keputusan recruiter** | Tombol Shortlist / Tahan / Tidak lanjut, dengan alasan wajib untuk "Tidak lanjut". Semua keputusan tercatat di audit log. |
| F8 | **Export** | Download hasil ke **XLSX dan CSV**: peringkat, skor, band, status per kriteria, kutipan bukti utama, keputusan recruiter. |
| F9 | **Audit log** | Siapa melakukan apa dan kapan (upload, setujui kriteria, jalankan screening, lihat identitas, putuskan, export). |
| F10 | **Ekspor evaluasi** | Endpoint yang mengeluarkan hasil run dalam format evaluator golden dataset (untuk QA, bukan untuk recruiter). |

## 6. Non-goals (di luar MVP)

- Email otomatis ke kandidat (penolakan, undangan).
- Penjadwalan interview otomatis.
- Analisis video/suara interview.
- Penilaian kepribadian, "culture fit", kejujuran, atau soft skill dari gaya tulisan CV. **Ini dilarang, bukan
  ditunda.**
- Belajar otomatis dari keputusan rekrutmen masa lalu (risiko bias historis).
- Multi-perusahaan (multi-tenant). Kolom `tenant_id` tetap ada untuk persiapan.
- Integrasi ATS pihak ketiga.
- Portal kandidat.
- Chat assistant (direncanakan setelah MVP, lihat 03_ARCHITECTURE bagian 9).

## 7. Metrik keberhasilan

| Metrik | Target MVP | Cara ukur |
| --- | --- | --- |
| Precision@5 di golden dataset JD-01 | 1.0 | `evaluate.py --jd01` |
| NDCG@10 di golden dataset | ≥ 0.95 | `evaluate.py --jd01` |
| Akurasi status per kriteria | ≥ 0.90 | `evaluate.py --jd01` |
| CV tidak relevan mendapat skor < 50 | 100% | `evaluate.py --jd01` |
| Hasil identik saat dijalankan ulang | 100% | `evaluate.py --repeat` |
| Klaim tanpa kutipan valid yang tampil ke recruiter | 0 | Uji otomatis grounding |
| Waktu proses 300 CV teks (tanpa scan) | < 15 menit | Load test |
| Tingkat gagal baca file | < 5% (di luar file rusak/terkunci) | Dashboard |
| Saat pilot: recruiter setuju dengan top-10 | ≥ 70% kandidat top-10 dinilai layak review | Survei + log keputusan |

## 8. Asumsi

- Bahasa CV: Indonesia, Inggris, atau campuran.
- 10–30% CV berupa scan/foto atau desain Canva yang sulit dibaca.
- Satu VPS milik pemilik produk. Spesifikasi dikonfirmasi agent di `ANSWERS.md` (lihat 09_QUESTIONS_FOR_AGENT.md).
- Engine `cv-extractor` sudah ada di VPS dan dipakai ulang lewat adapter.

## 9. Risiko utama

| Risiko | Mitigasi |
| --- | --- |
| Ekstraksi CV Indonesia/Canva/scan kurang akurat | Uji `--extraction` sejak awal; OCR + deteksi layout; antrian cek manual |
| Recruiter mengikuti ranking tanpa membaca ("rubber-stamping") | Band + bukti, alasan wajib untuk "Tidak lanjut", catat waktu review |
| Bias tersembunyi lewat proxy | Redaksi identitas sebelum embedding/LLM, uji counterfactual E5a/E5b |
| Data CV bocor ke penyedia LLM | Hanya teks yang sudah diredaksi yang boleh dikirim; mode `local_only` |
| Biaya/latensi LLM | LLM hanya untuk kasus ambigu; cache hasil |

## 10. Kepatuhan (ringkas, bukan nasihat hukum)

- **UU PDP + PP 33/2026** (berlaku 16 Januari 2027): kandidat berhak keberatan atas keputusan yang sepenuhnya
  otomatis → sistem wajib human-in-the-loop dan punya fitur "keluarkan kandidat dari penilaian AI".
- Data pribadi CV harus punya kebijakan retensi dan bisa dihapus permanen per kandidat.
- Pengiriman CV ke server LLM di luar negeri = transfer data lintas negara → default kirim teks teredaksi saja,
  dan bisa dimatikan total.
