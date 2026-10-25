# Panduan Pelabelan Dataset Evaluasi CV (FX-33)

Dokumen ini adalah panduan standar untuk Human Resources (HR) dan Domain Specialist dalam menyusun *ground truth* (label acuan) evaluasi akurasi sistem screening.

---

## 1. Siapa yang Melakukan Pelabelan?
- Pelabelan wajib dilakukan oleh **Recruiter Senior** atau **Hiring Manager / Tech Lead** yang memahami kompetensi pekerjaan secara mendalam.
- Jangan menggunakan model AI atau perkiraan otomatis untuk membuat label ground truth.

---

## 2. Target Ukuran Dataset
- Minimal **50 CV per role / lowongan**.
- Komposisi seimbang:
  - **Strong (S)**: ~20-30% kandidat yang sangat kompeten dan memenuhi seluruh syarat wajib.
  - **Marginal (M)**: ~40-50% kandidat yang memenuhi sebagian syarat (mis. beda tech stack atau pengalaman kurang sedikit).
  - **Irrelevant (I)**: ~20-30% berkas tidak cocok (salah jurusan, beda industri, atau dokumen rusak/kosong).

---

## 3. Format Berkas `labels.json`

Setiap folder lowongan di `data/private_eval/<JOB_NAME>/` wajib memiliki `labels.json`:

```json
{
  "job_id": "JD-01",
  "job_title": "Senior Backend Engineer",
  "candidates": [
    {
      "cv_id": "CV_001",
      "file": "cvs/john_doe.pdf",
      "group": "strong",
      "relevance_grade": 3,
      "expected_states": {
        "R1": ["STRONG"],
        "R2": ["STRONG"],
        "R3": ["STRONG", "PARTIAL"]
      }
    }
  ]
}
```

### Keterangan Nilai Status Kriteria:
- `STRONG`: Bukti sangat jelas dan kuat di pekerjaan relevan (pengalaman berbayar).
- `PARTIAL`: Bukti sebagian, di proyek pribadi, tugas kuliah, atau relevansi terbatas.
- `NOT_DEMONSTRATED`: Tidak ada bukti kualifikasi tersebut di dalam CV.
- `UNKNOWN`: Ambigu atau perlu klarifikasi manual.

### Keterangan Tingkat Relevansi (`relevance_grade`):
- `3`: Sangat Direkomendasikan (Shortlist).
- `2`: Dipertimbangkan (Review).
- `1`: Prioritas Rendah (Low Priority).
- `0`: Tidak Relevan (Irrelevant).
