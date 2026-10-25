# 07 — Rencana Implementasi

Urutan milestone **wajib** diikuti. Satu milestone dianggap selesai hanya kalau semua "Definition of Done"
terpenuhi dan dilaporkan ke pemilik produk (ringkasan + hasil tes). Perkiraan waktu diasumsikan satu agent
dengan review harian; sesuaikan di `ANSWERS.md` setelah melihat kondisi VPS.

## M0 — Discovery (0,5–1 hari)

- Jawab semua pertanyaan di `09_QUESTIONS_FOR_AGENT.md` ke `docs/ANSWERS.md`.
- Jalankan `python golden_dataset/evaluate.py --self-test` (harus LULUS).
- Uji `cv-extractor` pada 15 CV inti + `--extraction` (adapter sementara boleh berupa skrip).
- **Berhenti dan tunggu konfirmasi** pemilik untuk pertanyaan bertanda ⚠️.

**DoD:** `ANSWERS.md` lengkap, angka akurasi ekstraksi awal tercatat, keputusan LLM/data policy disetujui.

## M1 — Fondasi (1–2 hari)

- Repo sesuai struktur di 03_ARCHITECTURE bagian 5; `docker-compose.yml` (caddy, api, worker, postgres+pgvector,
  clamav); `.env.example`; Makefile (`make up`, `make test`, `make eval`).
- Migrasi DB dari `schemas/db_schema.sql`.
- Auth (login, 3 peran), audit log dasar, health check, logging JSON.
- CI lokal: ruff, mypy (backend), eslint + typecheck (frontend), pytest.

**DoD:** `make up` menyalakan semua layanan; login berfungsi; migrasi bersih dari nol; tes lulus.

## M2 — Ingestion + ekstraksi (2–4 hari)

- Upload batch (multipart + ZIP), validasi MIME, ClamAV, hash/dedup, storage.
- Antrian worker (`jobs_queue`, `FOR UPDATE SKIP LOCKED`), retry, timeout per file.
- Adapter `cv-extractor` → `CandidateProfile` + provenance (halaman, offset, kutipan terverifikasi).
- Fallback parsing hanya untuk format yang gagal di M0.
- Quality checks: konten kosong, teks tersembunyi, injection, bukan CV, tanggal aneh.
- Redaksi identitas, normalisasi skill (`reference/skills_seed.yaml`), klasifikasi role family
  (`reference/role_families.yaml`), parser tanggal (`reference/date_formats.yaml`).
- Chunk + embedding + FTS.
- Endpoint `/cvs/status` dan `/extraction-export`.

**DoD:** `evaluate.py --extraction` LULUS; edge E1, E6, E7, E8 mendapat status yang benar; 300 CV teks diproses
< 15 menit; tidak ada nama/email/telepon di `matching_profile` dan `profile_chunks` (tes otomatis).

## M3 — Kriteria (1–2 hari)

- Compiler JD lewat model gateway (schema `requirement_set.schema.json`), bobot default 40/30/15/15.
- Policy linter (`reference/prohibited_criteria.yaml`).
- Endpoint draf, edit, approve (immutable), import.

**DoD:** compile `JD-01_backend_engineer.md` mencakup ≥ 9/10 konsep R1–R10; JD dengan "usia maks. 28 tahun,
pria, berpenampilan menarik" menghasilkan 3 flag terlarang dan tidak bisa disetujui; import JD-01/JD-02
approved berhasil.

## M4 — Scoring engine (2–4 hari)

- Aturan per kind (02_SCORING bagian 4.2) sebagai fungsi murni yang dites unit.
- Port `reference_scorer.py` (skor, band, cap, rekomendasi, urutan) **tanpa mengubah hasil**.
- LLM verifier untuk kriteria ambigu + cek kutipan oleh kode + cache.
- Screening run immutable dengan `versions` dan `as_of`.
- Template penjelasan, pertanyaan interview, perbandingan.
- Endpoint rankings, detail kandidat, compare, `eval-export`.

**DoD:** `evaluate.py --jd01`, `--jd02`, `--edge`, dan `--repeat` semuanya LULUS. Laporan `--report` dilampirkan.
Unit test aturan per kind mencakup semua contoh di 02_SCORING.

## M5 — Frontend (3–5 hari)

- Screen 1, 1b, 2, 3, 4, bandingkan, export (05_UI_UX_SPEC).
- Blind mode + reveal identity tercatat audit.
- Preview PDF dengan highlight kutipan; DOCX dikonversi ke PDF (LibreOffice headless) untuk preview.
- Export XLSX/CSV.

**DoD:** alur penuh JD-01 bisa dilakukan lewat UI tanpa curl; Playwright test untuk alur utama; aturan bahasa
UI (tidak ada "tidak menguasai", tidak ada "Reject") lolos pemeriksaan teks otomatis.

## M6 — Hardening (1–2 hari)

- Rate limit, backup terjadwal + uji restore, penghapusan kandidat (semua tabel + file + cache),
  endpoint keberatan (`MANUAL_ONLY`).
- `/metrics` Prometheus: CV/jam, gagal per alasan, latensi tahap, token & biaya LLM, cache hit.
- Load test 300 CV dan 5 screening paralel.
- README deploy dan runbook (restart, backup/restore, ganti model LLM).

**DoD:** semua uji golden tetap LULUS; load test memenuhi 03_ARCHITECTURE bagian 8; hapus kandidat terbukti
menghilangkan semua jejak kecuali tombstone di run lama.

## Setelah MVP (minta izin dulu)

- Reranker `bge-reranker-v2-m3` untuk pemilihan bukti (ukur dampak dengan golden dataset).
- Asisten recruiter (chat read-only dengan kutipan).
- Agent penyusun kriteria interaktif + kerangka kompetensi perusahaan (Obsidian → `taxonomy/`).
- Eksperimen Jev (TypeSafe) sebagai verifier: bandingkan akurasi status vs LLM verifier pada golden dataset.
- Evaluasi malam otomatis (cron) + laporan ke pemilik.

## Aturan kerja agent

1. Kerjakan milestone berurutan. Jangan mulai M(n+1) sebelum DoD M(n) terpenuhi.
2. Setiap selesai milestone: ringkasan perubahan, hasil tes, hal yang menyimpang dari spesifikasi beserta
   alasannya, dan pertanyaan terbuka.
3. Commit kecil dengan pesan jelas. Jangan commit `.env`, CV asli, atau data pribadi.
4. Jangan mengubah file di `golden_dataset/labels/` atau `cv_data.py` untuk "meluluskan" tes. Kalau labelnya
   salah, laporkan dan minta persetujuan.
5. Jangan mengirim CV asli ke API LLM eksternal tanpa izin tertulis pemilik produk.
6. Kalau ragu antara dua pilihan yang sama-sama masuk akal dan tidak bisa dibalik dengan mudah, tanya dulu.
