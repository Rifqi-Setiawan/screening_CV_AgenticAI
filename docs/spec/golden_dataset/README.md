# Golden Dataset — CV Screening

Semua CV di folder ini **sintetis dan fiktif** (nama, perusahaan, kampus, email
`@example.com`, telepon `0812-0000-xxxx`). Aman di-commit ke git.

## Isi

| Path | Isi |
| --- | --- |
| `job_descriptions/JD-01_backend_engineer.md` | Lowongan utama untuk uji ranking |
| `job_descriptions/JD-01_requirements.approved.json` | Kriteria acuan yang sudah "disetujui recruiter" (R1–R10, bobot) |
| `job_descriptions/JD-02_hr_generalist.md` + `.approved.json` | Lowongan kontrol (CV HR harus juara) |
| `cvs/core/` | 15 CV inti: 5 sangat cocok (S), 5 marginal (M), 5 tidak relevan (I) |
| `cvs/edge/` | 9 kasus khusus: CV kosong, scan, prompt injection, keyword stuffing, pasangan counterfactual, PDF terkunci, bukan CV, duplikat |
| `labels/expected_JD-01.json` | Kunci jawaban ranking, status per kriteria, skor acuan |
| `labels/expected_JD-02.json` | Kunci jawaban uji kontrol |
| `labels/expected_edge_cases.json` | Perilaku yang diharapkan untuk tiap edge case |
| `labels/expected_extraction.json` | Kunci jawaban ekstraksi (pengalaman + tanggal, pendidikan, sertifikasi, skill) |
| `evaluate.py` | Evaluator otomatis (exit code 0 = lulus) |
| `generator/` | Sumber data + generator file + `reference_scorer.py` (implementasi acuan rumus skor) |

## Variasi format yang sengaja dibuat

| Format | CV |
| --- | --- |
| PDF satu kolom (teks) | S1, S2, S3, M2, I1, I4 |
| PDF dua kolom dengan sidebar | S4, M1, M5, I3 |
| DOCX | S5, M4, I2 |
| PDF hasil scan (tanpa text layer, wajib OCR) | M3, I5, E2 |
| Bahasa Indonesia / Inggris / Inggris + bulan Indonesia | ID: S1, S5, M2, M3, M5, I1, I2, I4, I5 · EN: S2, S4, M1, M4, I3 · campur: S3 |
| Tanggal: `Maret 2022 – Sekarang`, `Aug 2022 – Present`, `03/2023 - Present`, `MARET 2023 – SEKARANG`, `2020 – 2022` | tersebar |

## Cara menjalankan

```bash
# 0) Cek evaluator sendiri (harus LULUS)
python evaluate.py --self-test

# 1) Screening 15 CV inti untuk JD-01 memakai kriteria acuan, ekspor hasil
#    (endpoint ekspor evaluasi: lihat 04_DATA_MODEL_API_CONTRACT.md)
python evaluate.py --jd01 out/run_jd01.json

# 2) Jalankan ulang run yang sama -> harus identik
python evaluate.py --repeat out/run_jd01.json out/run_jd01_rerun.json

# 3) Uji kontrol JD-02
python evaluate.py --jd02 out/run_jd02.json

# 4) Edge case (15 CV inti + 9 file edge dalam satu run JD-01)
python evaluate.py --edge out/run_edge.json

# 5) Ekstraksi
python evaluate.py --extraction out/extraction.json

# Laporan markdown
python evaluate.py --jd01 out/run_jd01.json --report out/eval_report.md
```

## Membuat ulang file

```bash
cd generator
python generate_cvs.py      # butuh reportlab, python-docx, pillow, pypdf, poppler-utils
python build_labels.py
```

## CV asli

CV asli (punya orang sungguhan) **tidak boleh** masuk folder ini atau git.
Simpan di `golden_dataset/private/` (masukkan ke `.gitignore`), samarkan identitasnya
dulu, dan beri label manual dengan format yang sama seperti `labels/`.
