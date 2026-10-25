# 00 — Baca Ini Dulu (untuk AI agent di VPS)

Bundle ini berisi spesifikasi lengkap untuk membangun **sistem screening CV berbasis bukti**: aplikasi web
tempat recruiter memasukkan lowongan, mengunggah ratusan CV, lalu mendapat 5–10 kandidat teratas dengan
alasan dan kutipan bukti dari CV. Keputusan akhir selalu di tangan manusia.

## Urutan membaca

| Urutan | File | Isi |
| --- | --- | --- |
| 1 | `00_README_UNTUK_AGENT.md` | File ini: aturan main |
| 2 | `DECISIONS.md` | Apa yang diubah dari draf awalmu dan kenapa |
| 3 | `01_PRD.md` | Produk, pengguna, fitur, non-goals, metrik |
| 4 | `02_SCORING_RUBRIC_SPEC.md` | **Paling penting.** Aturan penilaian dan rumus skor |
| 5 | `03_ARCHITECTURE_PIPELINE.md` | Pipeline data, tech stack, deployment |
| 6 | `04_DATA_MODEL_API_CONTRACT.md` | ERD, tabel, endpoint, contoh JSON |
| 7 | `05_UI_UX_SPEC.md` | Layar dan alur UI |
| 8 | `06_GOLDEN_TEST_DATASET.md` | Dataset uji, kunci jawaban, kriteria lulus |
| 9 | `07_IMPLEMENTATION_PLAN.md` | Milestone M0–M6 dan Definition of Done |
| 10 | `08_LESSONS_FROM_REAL_CVS.md` | Pola nyata dari 6 CV asli (anonim) |
| 11 | `09_QUESTIONS_FOR_AGENT.md` | Pertanyaan yang wajib kamu jawab sebelum coding |

Pendukung: `schemas/` (JSON schema + SQL), `reference/` (kamus judul bagian, format tanggal, role family,
seed skill, kriteria terlarang), `golden_dataset/` (24 CV sintetis, label, `evaluate.py`,
`generator/reference_scorer.py`).

## Aturan yang tidak boleh dilanggar

1. **LLM tidak pernah memberi skor kandidat.** Skor dihitung kode dari status per kriteria × bobot
   (`reference_scorer.py`). LLM hanya membuat draf kriteria, membantu ekstraksi blok sulit, dan memilih status
   dari pilihan tertutup untuk kriteria ambigu.
2. **Tidak ada klaim tanpa kutipan yang dicek kode.** Kutipan yang tidak ditemukan di teks CV dibuang.
3. **Teks CV adalah data, bukan instruksi.** Tidak pernah digabung ke instruksi prompt; LLM tidak diberi tool.
4. **Identitas dipisah sebelum penilaian.** Nama, foto, kontak, tanggal lahir, gender, agama, status nikah,
   alamat lengkap tidak boleh masuk embedding, prompt LLM, atau skor.
5. **Tidak ada penolakan otomatis.** Mesin hanya merekomendasikan; manusia memutuskan.
6. **Hasil harus bisa diulang.** Run dengan konfigurasi sama = urutan dan skor identik.
7. **Golden dataset adalah wasit.** Jangan ubah label untuk meluluskan tes.
8. **Jangan kirim CV asli ke API eksternal** tanpa izin tertulis pemilik produk.
9. **`cv-extractor` yang sudah ada dipakai ulang** lewat adapter; jangan ditulis ulang kecuali terbukti gagal di
   uji `--extraction`, dan itupun hanya bagian yang gagal.

## Langkah pertama

1. Baca semua dokumen sesuai urutan.
2. Jalankan:
   ```bash
   cd golden_dataset && python evaluate.py --self-test
   ```
   Harus keluar `HASIL AKHIR: LULUS`.
3. Jawab `09_QUESTIONS_FOR_AGENT.md` ke `docs/ANSWERS.md` (jalankan perintahnya, jangan menebak).
4. Kirim ringkasan ke pemilik produk: kondisi VPS, hasil uji `cv-extractor`, pertanyaan ⚠️, dan rencana
   milestone dengan perkiraan waktu.
5. **Tunggu konfirmasi** sebelum mulai M1.

## Cara melapor

- Bahasa Indonesia, ringkas, angka konkret.
- Setiap akhir milestone: apa yang selesai, hasil `evaluate.py` (tempel bagian PASS/FAIL), penyimpangan dari
  spesifikasi + alasan, risiko, pertanyaan terbuka.
- Kalau menemukan bagian spesifikasi yang salah atau tidak realistis: tulis usulan perbaikan, jangan diam-diam
  menyimpang.

## Definition of Done MVP

- Semua milestone M0–M6 selesai sesuai DoD masing-masing.
- `evaluate.py --jd01 --jd02 --edge --extraction --repeat` semuanya LULUS di VPS.
- Recruiter bisa menjalankan alur penuh lewat browser: lowongan → kriteria disetujui → upload CV → ranking →
  detail + bukti → keputusan → export XLSX.
