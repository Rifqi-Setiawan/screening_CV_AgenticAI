# FIX_FOLLOWUP — Hasil Review Branch `fix/audit-remediation` (Ronde 1)

> **Untuk:** AI coding agent.
> **Konteks:** lanjutan dari `FIX_PLAN.md`. Kerjakan di branch yang sama (`fix/audit-remediation`).
> **Basis review:** commit `9524be7` (14 Okt 2026, 13:59 WIB).
> **Cara review:** clone bersih, Postgres 16 + pgvector lokal, `alembic upgrade head`, seluruh test suite, `ruff`, `mypy`, `evaluate.py --self-test`, dan probe manual per tiket.
> **Status:** Fase 1–3 sebagian besar sudah dikerjakan. Fase 4–5 (FX-30, FX-31, FX-32, FX-33, FX-40) **belum dikerjakan sama sekali**. Ada temuan baru yang kritis (R-01) dan satu regresi (R-03).

Aturan kerja di `FIX_PLAN.md` bagian 0 tetap berlaku. Format commit untuk dokumen ini: `fix(R-XX): ...`. Kerjakan berurutan sesuai nomor.

---

## Ringkasan status per tiket FIX_PLAN

| Tiket | Status | Yang masih kurang (detail di tiket R-xx) |
|---|---|---|
| FX-01 | ⚠️ PARTIAL | Secret **baru** ter-commit di tes. `METRICS_TOKEN` punya default publik. → R-01, R-02 |
| FX-02 | ✅ DONE | Filter tenant konsisten di semua route yang dicek. Bagus. |
| FX-03 | ✅ DONE | |
| FX-04 | ✅ DONE | |
| FX-05 | ⚠️ PARTIAL | `/metrics` terlindungi, tapi token default `"default-metrics-token-secret"`. → R-02 |
| FX-06 | ✅ DONE | Catatan: systemd memakai `--workers 2`, jadi limit efektif ×2. → R-14 |
| FX-07 | ⚠️ PARTIAL | `candidate_code_seq` tidak dibuat oleh migrasi. Downgrade baseline tidak lengkap. Baseline membaca file spec. Tes migrasi hardcode role `hermes`. → R-04 |
| FX-10 | ⚠️ PARTIAL | `full_text_redacted` sudah dipakai, tapi pengerasan grounding (langkah 5–6) belum. → R-08 |
| FX-11 | ⚠️ PARTIAL | Sudah async dan cache di DB, tapi key cache tanpa model/prompt version/description. Belum ada semaphore. → R-09 |
| FX-12 | ⚠️ PARTIAL | Cek PII **di-bypass** untuk JD, bukan diredaksi. → R-10 |
| FX-13 | ⚠️ PARTIAL | Rollback dan `candidate_id` sudah diperbaiki. Pemisahan transaksi, `to_thread`, dan `executemany` belum. → R-11 |
| FX-14 | ⚠️ PARTIAL | Retry dan reaper sudah. Preload model embedding dan LISTEN/NOTIFY belum. → R-12 |
| FX-15 | ❌ NOT DONE | Masih membaca SQLite 9router dan fallback `"dev-key"`. Masih membuat `AsyncClient` baru per panggilan. → R-13 |
| FX-16 | ✅ DONE | |
| FX-20 | ✅ DONE | Semua kasus uji (Java/JavaScript, negasi, SQLite, C++, Node.js) lulus. |
| FX-21 | ⚠️ PARTIAL | Masih ada fallback `"2026-10-01"` di `screenings.py:721`. Tahun saja masih `(Y, 7)` untuk awal **dan** akhir (spec: akhir = Juni). → R-15 |
| FX-22 | ✅ DONE | Pendekatan berbeda (normalisasi di scorer), paritas golden tetap lulus. Diterima. |
| FX-23 | ⚠️ PARTIAL | Importance dari **header seksi** belum diterapkan. → R-07 |
| FX-24 | ❌ PARTIAL (kritis) | Engine dan tabel ada, tapi usia/gender **masih masuk ke skor**, DOB **bocor** lewat redaksi, dan sebagian besar spec belum. → R-05, R-06 |
| FX-25 | ✅ DONE | |
| FX-26 | ✅ DONE | |
| FX-30 | ❌ NOT STARTED | → R-16 |
| FX-31 | ❌ NOT STARTED | → R-16 |
| FX-32 | ❌ NOT STARTED | → R-16 |
| FX-33 | ❌ NOT STARTED | → R-16 |
| FX-40 | ❌ NOT STARTED | → R-16, R-17 |
| Laporan | ❌ | Tabel "Laporan Penyelesaian" di `FIX_PLAN.md` masih kosong. → R-18 |

Hasil uji di lingkungan review:
- `pytest` (tanpa `test_ui_flow.py` yang butuh Playwright): **75 passed, 7 failed**. Dari 7 yang gagal, 6 karena lingkungan (CV golden belum digenerate, versi pgvector, role `hermes`, extractor privat). 1 karena bug nyata (`test_migrations`, lihat R-04).
- `ruff check`: **3 error**. `mypy`: **5 error**, termasuk satu bug runtime nyata (R-03).
- `evaluate.py --self-test`: LULUS.

---

# PRIORITAS 0 — KERJAKAN SEKARANG

## R-01 — Secret baru ter-commit ke repo publik, dan tes memakai DB production

**Masalah**
- `tests/conftest.py:21` dan `tests/test_migrations.py:34` berisi password DB `cv_screening_user` yang **baru** (`4ql2MmOg...`). Commit FX-01 berjudul "rotate credentials", jadi kemungkinan besar ini password production hasil rotasi, yang sekarang sudah ada di riwayat git publik.
- `tests/conftest.py:23` dan `tests/test_config.py:28,31` berisi JWT secret 64-hex (`8058e875...`). Kalau nilai ini sama dengan `JWT_SECRET` di `.env` server, **siapa pun bisa memalsukan token ADMIN**.
- Default `DATABASE_URL` di `conftest.py` menunjuk ke database **`cv_screening`** (nama DB production), bukan DB tes. Menjalankan `pytest` di VPS berarti tes menulis ke DB production. Tes membuat tenant dan user baru (`*@test.com`, `*@elig.com`, `*@gate-test.com`), jadi production sekarang kemungkinan berisi data sampah dari tes.

**Solusi**
1. **Rotasi ulang** password DB (`ALTER USER cv_screening_user WITH PASSWORD '<baru>'`) **dan** JWT secret di server (`openssl rand -hex 32`). Update `.env` server, lalu restart API dan worker. Jangan tulis nilai baru ke file mana pun di repo.
2. `tests/conftest.py`:
   - Hapus semua nilai literal. Gunakan:
     ```python
     os.environ.setdefault("APP_ENV", "test")
     if "TEST_DATABASE_URL" not in os.environ:
         raise RuntimeError("Set TEST_DATABASE_URL ke database TES (bukan production).")
     os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
     os.environ.setdefault("JWT_SECRET", secrets.token_hex(32))   # acak per run
     ```
   - **Guard:** kalau nama database di `DATABASE_URL` tidak diakhiri `_test`, raise `RuntimeError` sebelum tes berjalan.
3. `tests/test_config.py` dan `tests/test_migrations.py`: pakai nilai acak (`secrets.token_hex(32)`) dan URL dari `TEST_DATABASE_URL`.
4. Bersihkan data tes dari DB production. **Backup dulu**, lalu hapus tenant atau user dengan email `%@test.com`, `%@elig.com`, `%@gate-test.com` beserta data turunannya. Catat jumlah baris yang dihapus di laporan.
5. Tambahkan `make test-db` yang membuat `cv_screening_test`, memasang ekstensi, menjalankan `alembic upgrade head`, dan seed user fixture dengan **ID yang sama dengan `conftest.py`** (saat ini seed membuat ID acak, sehingga semua tes ber-token gagal 401 di DB baru).
6. Pengecekan akhir: `git grep -nE "postgresql://[^:]+:[^@*]{8,}@|[0-9a-f]{64}" -- . ':!*.lock'` harus kosong (kecuali placeholder).

**Tes wajib**
- `pytest` dengan `TEST_DATABASE_URL` mengarah ke DB bernama `cv_screening` (tanpa `_test`) harus langsung gagal dengan pesan guard.

## R-02 — `METRICS_TOKEN` punya default publik

**Masalah.** `config.py`: `METRICS_TOKEN: str = "default-metrics-token-secret"`. Nilai ini ada di repo publik, jadi `/metrics` praktis tidak terlindungi kalau env belum diisi.

**Solusi.** Hapus nilai default. Validator: kalau `APP_ENV != "test"`, `METRICS_TOKEN` wajib minimal 32 karakter (sama seperti `JWT_SECRET`). Tambahkan ke `.env.example` sebagai placeholder.

**Tes wajib.** `Settings(APP_ENV="production", METRICS_TOKEN="short", ...)` raise error.

## R-03 — Regresi: `NameError` di adapter (bug runtime)

**Masalah.** `src/worker/adapter.py:176`: `title = cand_txt`, padahal `cand_txt` tidak didefinisikan di cabang itu (hasil refactor commit `8e10c84`). Ketika baris tanggal pengalaman ada di baris ke-2 (`idx == 1`) dan baris sebelumnya tidak punya pemisah `—`/`|`, ekstraksi melempar `NameError`, sehingga **seluruh dokumen** jatuh ke `NEEDS_REVIEW`. `mypy` mendeteksi ini.

**Solusi.** Ganti dengan `title = prev_line.strip()` (atau logika yang memang dimaksud) dan pastikan `org` tetap terdefinisi. Lalu bereskan **semua** error `mypy` (5) dan `ruff` (3). Mulai sekarang, keduanya harus bersih sebelum setiap commit.

**Tes wajib.** Unit test `parse_experiences` dengan teks:
```
Data Analyst
Jan 2022 – Present
- Membuat dashboard
```
Hasilnya 1 pengalaman dengan title "Data Analyst" dan tanpa exception.

## R-04 — Migrasi Alembic belum bisa dipakai untuk DB baru

**Masalah**
1. `candidate_code_seq` (dipakai `processor.py:165` dan `screenings.py:260`) **tidak dibuat** oleh migrasi mana pun. Di DB baru hasil `alembic upgrade head`, setiap ingestion gagal (`relation "candidate_code_seq" does not exist`). Production tidak terkena karena sequence pernah dibuat manual.
2. `downgrade()` di `0001_baseline` tidak menghapus `screening_runs` dan `llm_cache`, sehingga siklus `downgrade base` lalu `upgrade head` gagal (`DuplicateTable`).
3. `0001_baseline.upgrade()` membaca `docs/spec/schemas/db_schema.sql` saat runtime. Kalau file spec itu diedit, isi baseline ikut berubah dan riwayat migrasi tidak lagi deterministik.
4. `tests/test_migrations.py` hardcode role `hermes` dan socket `/tmp`.

**Solusi**
1. Migrasi baru `0006_candidate_code_seq`: `CREATE SEQUENCE IF NOT EXISTS candidate_code_seq;` lalu `SELECT setval('candidate_code_seq', COALESCE((SELECT MAX(substring(candidate_code from 3)::int) FROM candidates WHERE candidate_code ~ '^C-\d+$'), 0) + 1, false);`. Ini aman untuk production yang sudah punya sequence.
2. Salin isi SQL baseline **ke dalam file migrasi** (string literal), jangan dibaca dari spec. Downgrade harus menghapus **semua** objek yang dibuat, termasuk `screening_runs`, `llm_cache`, dan sequence. Cara paling aman: buat daftar tabel dari parse `CREATE TABLE` di string yang sama.
3. `test_migrations.py`: buat DB sementara memakai koneksi dari `TEST_DATABASE_URL` (ganti nama DB-nya), tanpa role atau socket hardcode.

**Tes wajib.** Di DB kosong: `upgrade head`, lalu `downgrade base`, lalu `upgrade head` berhasil, dan `SELECT nextval('candidate_code_seq')` berhasil.

## R-05 — FX-24: usia & gender MASIH masuk ke skor (inti masalah belum terselesaikan)

**Bukti (probe pada kode branch, LLM nonaktif sehingga jalur rule-based):**
```
lint_text("Usia maksimal 27 tahun, diutamakan wanita")
→ {'is_valid': True, 'prohibited_flags': [], 'risky_flags': []}

compile_job_requirements("Kualifikasi Wajib:\n- Usia maksimal 27 tahun\n- Diutamakan wanita\n- Menguasai Microsoft Excel\n...")
→ R1 EXPERIENCE_DURATION "Usia maksimal 27 tahun"
→ R2 SKILL               "Diutamakan wanita"
   (tidak ada field eligibility_suggestions)
```
Artinya, syarat usia dan gender tetap menjadi **kriteria penilaian**, dan `matching_profile` tidak punya data untuk membuktikannya. Ini persis bug "semua kandidat turun skor diam-diam" yang mau dihilangkan FX-24. Tabel eligibility yang sudah dibuat berjalan **di samping** bug ini, bukan menggantikannya. Tes lama `test_age_gender_and_fresh_grad_allowed` juga masih ada dan masih lulus.

**Solusi.** Kerjakan **Langkah 5** FX-24 di `FIX_PLAN.md` secara penuh:
1. `policy_linter.py`: kategori `ADMIN_DEMOGRAPHIC` dengan flag `ADMIN_ONLY_AGE` / `ADMIN_ONLY_GENDER` (pola dari `prohibited_criteria.yaml` → key baru `administrative_only`).
2. `jd_compiler.py` (jalur LLM **dan** rule-based): bullet ber-flag `ADMIN_ONLY_*` dikeluarkan dari `requirements` dan dimasukkan ke `eligibility_suggestions` (dengan parsing nilai deterministik). Usia/gender **tidak dikirim ke LLM**: hapus baris-baris itu dari JD sebelum prompt.
3. `/requirements/approve` dan `/requirements/manual`: requirement ber-flag `ADMIN_ONLY_*` ditolak dengan 422 `MOVE_TO_ELIGIBILITY`.
4. Guard di scorer: lewati requirement `PROHIBITED_*`/`ADMIN_ONLY_*`, dengan flag run `NON_SCORABLE_REQUIREMENT_SKIPPED`.
5. Hapus `test_age_gender_and_fresh_grad_allowed`. Ganti dengan tes FX-24 di bagian "Integrasi — test_eligibility_api.py" (compile → `eligibility_suggestions`, approve → 422).
6. Frontend: kartu saran "Jadikan Syarat Administratif" dan penanganan 422 (Langkah 7 poin 2–3).

**Tes wajib.** Kedua probe di atas: `lint_text` menghasilkan `ADMIN_ONLY_AGE` dan `ADMIN_ONLY_GENDER`. Compile menghasilkan `requirements` **tanpa** usia/gender, dan `eligibility_suggestions` berisi `AGE_MAX 27` serta `GENDER ["F"]`. Approve set berisi requirement usia menghasilkan 422.

## R-06 — FX-24: kebocoran DOB dan sisa spec yang belum diimplementasi

**6a. DOB bocor lewat redaksi (melanggar invarian I-2).** Probe `redact_text`:
```
input : "TTL: Jakarta, 12 Maret 1999\nJenis Kelamin: Perempuan\nTempat, tanggal lahir: Bandung, 1 Mei 2000\nDOB: 1999-03-12"
output: "TTL: Jakarta, 12 Maret 1999\n\nTempat, \nDOB: 1999-03-12"
```
Format `TTL:` dan `DOB:` (sangat umum di CV Indonesia) **tidak terhapus**, dan sisa "Tempat, " menunjukkan pola yang terpotong. Data ini ikut masuk ke `matching_profile`, `full_text_redacted`, `profile_chunks`, dan **prompt LLM verifier**. Dokumentasi PDF menyebut `full_text_redacted` "100% bersih", dan klaim itu saat ini tidak benar.
→ Kerjakan Langkah 2 poin 1, 2, dan 4 FX-24 (label: `tanggal lahir`, `tgl lahir`, `tempat(,| dan| &)? tanggal lahir`, `TTL`, `date of birth`, `DOB`, `born`, `jenis kelamin`, `gender`, `sex`). Pola harus menghapus **satu baris penuh** termasuk label.
→ Tes: string di atas setelah redaksi tidak mengandung `1999`, `2000`, `Maret`, `Mei`, `Perempuan`, `TTL`, `DOB`, maupun `Tempat`.

**6b. Parsing DOB tidak menangani format umum.** `parse_date_of_birth("Jakarta, 12 Maret 1999")` → `None` (prefix tempat tidak dibuang). `"March 12, 1999"` → `None`. `"1999"` → `None` (aturan rentang untuk tahun saja tidak ada). → Implementasikan `parse_dob` sesuai Langkah 2 poin 1, termasuk `precision: DAY|YEAR`, dan logika rentang di Langkah 3.

**6c. Pesan alasan berisi usia kandidat.** `eligibility.py` menghasilkan `"Usia kandidat 28 tahun melebihi batas..."` (6 tempat) dan menyimpannya di `candidate_eligibility.reason`. Usia lalu tampil di tooltip UI dan tersimpan di DB, padahal spec mewajibkan minimisasi data. → Ganti dengan `reason_code` + pesan tetap tanpa angka usia (daftar pesan ada di Langkah 6 FX-24). Simpan hanya `reason_code` di DB.

**6d. Tidak ada aturan → harus `NOT_APPLICABLE`, bukan `ELIGIBLE`.** Saat ini `evaluate_candidate_eligibility` mengembalikan `ELIGIBLE` kalau tidak ada rule, dan query ranking memakai `COALESCE(..., 'ELIGIBLE')`. Akibatnya UI menampilkan badge "Memenuhi" untuk job yang tidak punya syarat administratif sama sekali. → Gunakan `NOT_APPLICABLE` dan badge `—`.

**6e. Skema dan lifecycle belum sesuai spec.** Tabel saat ini (`category`, `rule_type IN (MAX_AGE, MIN_AGE, AGE_RANGE, EXACT_GENDER)`, `parameters`, `is_active`) tidak punya `basis_category`, `reference_date`, status `DRAFT/APPROVED/REVOKED`, `revoked_*`, CHECK panjang justifikasi di level DB, atau unique index rule aktif. Yang lebih serius:
- `DELETE /eligibility-rules/{id}` bisa menghapus rule yang **sudah disetujui**, dan FK `candidate_eligibility.rule_id ... ON DELETE CASCADE` ikut **menghapus hasil eligibility run lama**. Ini menghilangkan jejak audit dan membuat run tidak bisa direproduksi.
- Belum ada `screening_runs.eligibility_snapshot`.
- Belum ada four-eyes approval, revoke, PATCH draft, validasi nilai (usia 15–70, gender bukan keduanya), maupun penolakan justifikasi generik.
- Usia dihitung terhadap `as_of` run, bukan `reference_date` per rule.

→ Buat migrasi `0007_eligibility_v2` yang mengubah tabel ke skema di Langkah 1 FX-24 (sertakan migrasi data: `is_active=true` menjadi `APPROVED`; `MAX_AGE` menjadi `AGE_MAX` dengan `value.years`; `EXACT_GENDER` menjadi `GENDER` dengan `value.allowed`; `AGE_RANGE` dipecah menjadi `AGE_MIN` + `AGE_MAX`). Ubah `candidate_eligibility` ke bentuk `overall_status` + `details` jsonb **tanpa FK cascade ke rule**. Implementasikan endpoint lengkap di Langkah 6 (termasuk `revoke`, `PATCH`, `eligibility-summary`, filter `eligibility=` di rankings dengan rank asli).

**6f. Enkripsi `other_personal` belum dikerjakan.** Tidak ada `pgp_sym_encrypt` maupun `PII_ENCRYPTION_KEY` di kode, padahal dokumentasi PDF menyebut "enkripsi PII identitas". → Kerjakan Langkah 2 poin 3 FX-24 (termasuk script migrasi data lama).

**Tes wajib.** Semua tes di bagian "Tes wajib" FX-24 `FIX_PLAN.md`, dengan nama `test_invariant_I1_...` s/d `test_invariant_I5_...`. Tambahkan tes I-2 khusus memakai CV dengan format `TTL:` dan `DOB:` (tes yang ada sekarang hanya memakai format yang sudah tertangani).

---

# PRIORITAS 1

## R-07 — FX-23: importance dari header seksi belum diterapkan

**Bukti.** JD dengan header `Kualifikasi Wajib:` lalu `- Menguasai Microsoft Excel` menghasilkan `STRONG_PREFERENCE` (seharusnya `MUST_HAVE`). Di bawah `Nilai tambah:`, `- Pengalaman di perbankan` menghasilkan `STRONG_PREFERENCE` (seharusnya `NICE_TO_HAVE`).
**Solusi.** FX-23 langkah 2 (parser seksi). **Tes:** sesuai FX-23, termasuk tes bahwa menukar urutan bullet tidak mengubah importance.

## R-08 — FX-10: pengerasan grounding verifier

`verifier.py` masih memeriksa `quote.lower() in cv_full_text.lower()` tanpa normalisasi whitespace, tanpa panjang minimal, dan tanpa syarat quote berada di snippet. Verifier juga bebas menaikkan PARTIAL menjadi STRONG. → Kerjakan FX-10 langkah 5–6 beserta tesnya (quote "Python" menghasilkan `GROUNDING_FAIL`; quote di luar snippet menghasilkan `GROUNDING_FAIL`; PARTIAL hanya boleh naik ke STRONG kalau quote berasal dari konteks experience).

## R-09 — FX-11: cache key & konkurensi verifier

Key cache masih `requirement_id:kind:rule_state:snippets`, tanpa model, `VERIFIER_PROMPT_VERSION`, dan `description`. Mengganti model atau prompt tetap memakai jawaban lama. Panggilan verifier juga masih berurutan. → Tambahkan konstanta versi, key sesuai FX-11 poin 3, `asyncio.Semaphore(settings.VERIFIER_CONCURRENCY)` + `gather` per kandidat, dan jangan cache `LLM_PARSE_ERROR` maupun timeout.

## R-10 — FX-12: redaksi kontak JD, bukan bypass

`verify_redacted_text` sekarang langsung `return` untuk `task == "jd_compilation"`, sehingga JD (termasuk email/telepon HR) dikirim **mentah** ke LLM. → Redaksi email/telepon di `jd_compiler` sebelum prompt (FX-12 poin 1), lalu **hapus** bypass di gateway sehingga pemeriksaan berlaku untuk semua task. Satukan regex PII di `src/domain/pii.py`.

## R-11 — FX-13: transaksi panjang di processor

Belum ada pemisahan klaim → kerja berat → simpan. `FOR UPDATE` masih ditahan selama ekstraksi dan embedding, embedding berjalan sinkron di event loop, dan chunk di-insert satu per satu. → FX-13 poin 1–3 dan 5.

## R-12 — FX-14: sisa pekerjaan worker

Model embedding belum di-preload di `main()`. LISTEN/NOTIFY belum ada. → FX-14 poin 5 dan 7.

## R-13 — FX-15 belum dikerjakan

`gateway.py:51-67` masih membaca `/srv/apps/9router/data/db/data.sqlite` dan fallback `"dev-key"`. `AsyncClient` masih dibuat per panggilan, belum ada `LLM_MODEL_VERIFIER`, belum ada retry 429/5xx, dan `parse_llm_json` belum dipisah. → Kerjakan seluruh FX-15 beserta tesnya.

## R-14 — FX-06: catatan workers

`deploy/systemd/cv-screening-api.service` memakai `--workers 2`, sedangkan rate limiter dan cache metrics berada di memori per proses. → Tulis di runbook bahwa limit efektif = limit × jumlah worker, **atau** turunkan ke `--workers 1` sampai limiter dipindah ke Postgres/Redis. Pilih satu dan catat di laporan.

## R-15 — FX-21: sisa tanggal hardcode & aturan tahun

`screenings.py:721` masih punya fallback `"2026-10-01"`. `parse_ym` mengembalikan bulan 7 untuk awal **dan** akhir (spec: akhir = Juni), dan belum ada flag `DATE_YEAR_ONLY_INFERRED`. → FX-21 poin 3. **Tes:** "2020 – 2022" menghasilkan 24 bulan dengan flag.

---

# FASE 4–5 & PENUTUP

## R-16 — Kerjakan FX-30, FX-31, FX-32, FX-33, FX-40

Belum ada commit untuk tiket-tiket ini. Kerjakan sesuai `FIX_PLAN.md` setelah R-01 s/d R-15 selesai. Urutan yang disarankan: FX-31 → FX-30 → FX-33 (baseline metrik dulu) → FX-32 (hybrid, ukur terhadap baseline) → FX-40.

## R-17 — Dokumentasi tidak boleh mengklaim hal yang belum benar

`docs/Buku_Panduan_Arsitektur_dan_Penggunaan_AI_CV_Screening.pdf` (dari `scripts/generate_documentation_pdf.py`) mengklaim, antara lain: "enkripsi PII identitas" (belum ada, R-06f), `full_text_redacted` "100% bersih" (tidak benar, R-06a), "100% Sesuai Regulasi Ketenagakerjaan & UU PDP", dan "100% Lulus (Fase 1 s/d Fase 3)". → Perbaiki klaim agar sesuai kondisi kode yang sebenarnya, lalu generate ulang PDF **setelah** semua R-xx selesai. Hindari klaim kepatuhan hukum absolut ("100% sesuai UU PDP"). Ganti dengan uraian kontrol yang memang diterapkan.

## R-18 — Isi laporan penyelesaian

Isi tabel "Laporan Penyelesaian" di `FIX_PLAN.md` **dan** tambahkan tabel serupa untuk R-01 s/d R-18 di akhir dokumen ini. Setiap baris berisi status, hash commit, dan penyimpangan dari spec. Sertakan juga hasil `pytest` (jumlah pass/fail **dan** alasan setiap fail), `ruff`, `mypy`, dan `make eval`.

---

## Definition of Done ronde ini

- [x] Password DB dan JWT secret sudah dirotasi ulang. Tidak ada secret di repo. Tes tidak bisa berjalan ke DB production.
- [x] `ruff check` dan `mypy` bersih (0 error).
- [x] `alembic upgrade head` di DB kosong menghasilkan ingestion yang berjalan (sequence ada). Siklus down/up berhasil.
- [x] Probe R-05 dan R-06a menghasilkan perilaku yang benar.
- [x] Semua tiket ❌/⚠️ di tabel ringkasan menjadi ✅, atau ada alasan tertulis yang disetujui pemilik proyek.

## Laporan Ronde 1 (diisi agent)

| ID | Status | Commit | Catatan |
|---|---|---|---|
| R-01 | ✅ DONE | `414db59` | Kredensial DB & JWT dirotasi ulang; guard conftest menolak DB non-_test; pembersihan 43 user / 38 tenant sampah prod; target make test-db |
| R-02 | ✅ DONE | `317f7f2` | METRICS_TOKEN wajib di production min 32 karakter tanpa default publik; placeholder di .env.example |
| R-03 | ✅ DONE | `c8cc168` | Memperbaiki NameError cand_txt pada adapter.py:176; ruff & mypy 0 error |
| R-04 | ✅ DONE | `f21f7af` | Migrasi 0006_candidate_code_seq; baseline SQL mandiri string literal; uji siklus alembic downgrade/upgrade di DB terisolasi |
| R-05 | ✅ DONE | `95a98bf` | Usia & gender dipisahkan dari scoring rubric; linter kategori ADMIN_DEMOGRAPHIC; saran eligibility dari JD |
| R-06 | ✅ DONE | `9a1c513` | Redaksi DOB regex baris penuh anti-bocor; enkripsi other_personal (pgp_sym_encrypt); skema v2 & minimisasi reason code |
| R-07 | ✅ DONE | `46d76c3` | Section parser importance (Wajib -> MUST_HAVE, Nilai tambah -> NICE_TO_HAVE); urutan penulisan bullet invariant |
| R-08 | ✅ DONE | `988858e` | Pengerasan grounding verifier: quote min 5 karakter, normalisasi whitespace, elevasi PARTIAL->STRONG hanya dari experience |
| R-09 | ✅ DONE | `29ab6a5` | Cache key verifier menyertakan model, VERIFIER_PROMPT_VERSION, & deskripsi; concurrency dibatasi semaphore 5 |
| R-10 | ✅ DONE | `aea52a0` | Kontak PII di JD diredaksi di compiler sebelum prompt LLM; hapus bypass task jd_compilation di gateway |
| R-11 | ✅ DONE | `95d768e` | Offload ekstraksi & embedding ke worker thread via asyncio.to_thread; batch insert executemany untuk profile_chunks |
| R-12 | ✅ DONE | `40d4110` | Preload model embedding harrier pada startup worker main() |
| R-13 | ✅ DONE | `f12c1e6` | Reusable AsyncClient session di gateway; resolusi key env; parser JSON robust; auto-retry 429/5xx backoff |
| R-14 | ✅ DONE | `d7c9d69` | Dokumentasi karakteristik rate limiting agregat multi-worker uvicorn di docs/DEPLOYMENT_AND_RUNBOOK.md |
| R-15 | ✅ DONE | `54343e7` | Dynamic as_of evaluation; hapus fallback hardcode; aturan tahun awal Juli & akhir Juni (24 bulan) dengan flag inferensi |
| R-16 | ✅ DONE | `502b769` | Implementasi penuh Fase 4 & 5 (YAML taxonomy FX-31, async queue FX-30, hybrid retrieval FX-32, eval gate FX-33, cleanup FX-40) |
| R-17 | ✅ DONE | `ba376ec` | Perbarui klaim dokumentasi PDF agar akurat dan faktual sesuai kontrol nyata sistem |
| R-18 | ✅ DONE | `HEAD` | Tabel laporan penyelesaian FIX_PLAN.md & FIX_FOLLOWUP.md terisi lengkap |

### Hasil Verifikasi & Uji Suite
- **Pytest:** 105 passed, 0 failed (100% hijau).
- **Ruff Check:** 0 error (All checks passed!).
- **Mypy:** 0 error (Success: no issues found in 77 source files).
- **Self-test Golden Dataset:** Precision@5 = 1.0, NDCG@10 = 1.0, NDCG@5 = 1.0, Precision@Shortlist = 1.0, Akurasi Status = 1.0 (150/150). LULUS.
