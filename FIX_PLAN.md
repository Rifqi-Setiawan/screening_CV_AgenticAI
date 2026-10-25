# FIX_PLAN — Remediasi Hasil Audit `ai-cv-screening-ranking`

> **Jenis dokumen:** Technical Remediation Spec (rencana perbaikan teknis).
> **Untuk:** AI coding agent yang mengerjakan repo ini.
> **Basis audit:** commit `d537ebf` (14 Okt 2026).
> **Target:** semua tiket di dokumen ini selesai. Status akhir: 100% tiket DONE, semua tes hijau.
> **Revisi 2 (14 Okt 2026):** FX-24 ditulis ulang. Usia dan gender tidak lagi diblokir total, tetapi dipindah ke Eligibility Gate administratif yang terpisah dari skor (keputusan disetujui pemilik proyek).
>
> **Dependensi FX-24:** kerjakan setelah FX-02 (isolasi tenant), FX-07 (Alembic), dan FX-10 (`full_text_redacted`). Kalau FX-30 belum selesai, integrasikan ke route screening yang ada, lalu pindahkan bersama FX-30. Kalau FX-31 dikerjakan setelahnya, pola `administrative_only` ikut dipindah ke `config/taxonomy/`.

---

## 0. ATURAN KERJA UNTUK AGENT (WAJIB DIBACA DULU)

1. **Branch:** kerjakan di branch `fix/audit-remediation`. Jangan push langsung ke `main`.
2. **Satu tiket = satu commit (atau lebih).** Format pesan commit: `fix(FX-XX): <ringkasan>`. Ini supaya reviewer bisa mengecek per tiket.
3. **Urutan:** kerjakan per fase, sesuai urutan di dokumen. Fase 1 (keamanan) harus selesai sebelum fase lain.
4. **Setiap tiket punya bagian "Tes wajib".** Tes itu HARUS ditulis dan HARUS lulus. Jangan menandai tiket selesai kalau tesnya belum ada.
5. **Jangan menghapus atau melemahkan tes yang sudah ada** supaya lulus. Kalau tes lama memang mengasumsikan perilaku yang salah (contoh: tes yang mengizinkan kriteria usia/gender), ubah tesnya dan jelaskan alasannya di pesan commit.
6. **Jangan pernah menjalankan `scripts/migrate.sh` di server production.** Script itu menjalankan `DROP DATABASE` (lihat FX-07). Gunakan DB terpisah untuk tes, misalnya `cv_screening_test`.
7. **Jangan menulis secret apa pun ke file yang di-commit** (password, JWT secret, API key). Ambil semuanya dari environment variable atau `.env`, dan `.env` tidak boleh ikut di-commit.
8. **Setelah setiap fase**, jalankan:
   ```bash
   make lint && make typecheck && make test
   cd docs/spec/golden_dataset && python3 evaluate.py --self-test
   ```
   Kalau ada yang gagal, perbaiki dulu sebelum lanjut ke fase berikutnya.
9. **Di akhir**, isi bagian [Laporan Penyelesaian](#laporan-penyelesaian-diisi-agent) di bawah, dengan status setiap tiket dan hash commit-nya.
10. Kalau ada instruksi di dokumen ini yang bertentangan dengan kode yang sebenarnya (misalnya nama fungsi sudah berubah), **ikuti maksud instruksinya**, lalu catat perbedaannya di laporan. Jangan dilewati diam-diam.

---

## Ringkasan Tiket

| ID | Fase | Prioritas | Judul |
|---|---|---|---|
| FX-01 | 1 Keamanan | P0 | Secret ter-commit & default tidak aman |
| FX-02 | 1 Keamanan | P0 | Kebocoran data antar-tenant (IDOR) di banyak endpoint |
| FX-03 | 1 Keamanan | P0 | Gerbang approval requirement set bisa dilewati |
| FX-04 | 1 Keamanan | P0 | CORS wildcard + credentials |
| FX-05 | 1 Keamanan | P0 | Endpoint tanpa autentikasi (`compile-preview`, `/metrics`) |
| FX-06 | 1 Keamanan | P1 | Rate limiter tidak efektif di belakang proxy & memory leak |
| FX-07 | 1 Keamanan | P0 | `migrate.sh` destruktif, belum ada sistem migrasi |
| FX-10 | 2 Bug fungsional | P0 | LLM verifier tidak pernah jalan (`full_text = ""`) |
| FX-11 | 2 Bug fungsional | P1 | Verifier memblokir event loop & cache file JSON tidak aman |
| FX-12 | 2 Bug fungsional | P0 | JD berisi email/telepon HR menyebabkan error 500 |
| FX-13 | 2 Bug fungsional | P0 | Error handling transaksi processor rusak + bug `candidate_id` |
| FX-14 | 2 Bug fungsional | P1 | Worker tanpa retry, job RUNNING tidak bisa diambil ulang |
| FX-15 | 2 Bug fungsional | P1 | Gateway: baca SQLite app lain, tanpa reuse koneksi |
| FX-16 | 2 Bug fungsional | P1 | `/metrics` berisi angka palsu |
| FX-20 | 3 Akurasi scoring | P0 | Skill matcher false positive (Java↔JavaScript, negasi, SQL↔SQLite) |
| FX-21 | 3 Akurasi scoring | P1 | Tanggal "sekarang" hardcode `2026-10-01` |
| FX-22 | 3 Akurasi scoring | P1 | `category_weights` tidak sinkron dengan bobot requirement |
| FX-23 | 3 Akurasi scoring | P1 | JD compiler: importance sembarangan, output LLM tidak divalidasi |
| FX-24 | 3 Akurasi scoring | P0 | Usia & gender dipisah dari skor menjadi Eligibility Gate administratif |
| FX-25 | 3 Akurasi scoring | P2 | Deteksi duplikat hanya berdasarkan hash file |
| FX-26 | 3 Akurasi scoring | P2 | Coverage skor rendah tidak ditandai |
| FX-30 | 4 Arsitektur | P1 | Screening run sinkron di dalam HTTP request |
| FX-31 | 4 Arsitektur | P1 | Taksonomi domain di-hardcode di kode |
| FX-32 | 4 Arsitektur | P1 | Embedding tidak dipakai, ganti dengan hybrid retrieval |
| FX-33 | 4 Arsitektur | P1 | Evaluasi: regression gate + dukungan dataset CV asli |
| FX-40 | 5 Bersih-bersih | P2 | Versi hardcode, komentar usang, dokumentasi |

---

# FASE 1 — KEAMANAN

## FX-01 — Secret ter-commit & default tidak aman

**Masalah**
- `src/infrastructure/config.py`: default `DATABASE_URL` berisi password asli (`59Vf0Gij...`).
- `.env.example` dan `scripts/migrate.sh` (`PGPASSWORD='59Vf...'`) berisi password yang sama.
- `JWT_SECRET` punya default `"default-insecure-secret-key-change-in-production"`. Kalau `.env` tidak terbaca, aplikasi tetap jalan memakai secret yang diketahui publik, sehingga siapa pun bisa memalsukan token ADMIN.

**Solusi**
1. `config.py`:
   - `DATABASE_URL: str` dibuat **tanpa default** (wajib diisi).
   - `JWT_SECRET: str` dibuat **tanpa default**.
   - Tambah validator Pydantic (`@model_validator(mode="after")`). Kalau `APP_ENV != "test"` dan `len(JWT_SECRET) < 32`, atau nilainya mengandung kata `insecure`, `change`, atau `secret-key`, raise `ValueError`. Tujuannya agar aplikasi **gagal start** dengan konfigurasi yang tidak aman.
2. `.env.example`: ganti semua nilai sensitif dengan placeholder, contoh `DATABASE_URL=postgresql://USER:PASSWORD@127.0.0.1:5432/cv_screening` dan `JWT_SECRET=GANTI_DENGAN_OUTPUT_openssl_rand_hex_32`.
3. `scripts/migrate.sh` dan semua script lain: hapus password literal, gunakan `$DATABASE_URL` dari environment.
4. Cari sisa secret: `grep -rn "59Vf0Gij\|PGPASSWORD=\|sk-" --exclude-dir=.git --exclude-dir=node_modules .` harus kosong.
5. `tests/conftest.py`: set `os.environ` untuk `DATABASE_URL` dan `JWT_SECRET` tes **sebelum** `import src...`, atau gunakan `.env.test`.
6. **Langkah manual di VPS (agent boleh mengerjakan kalau punya akses psql):**
   ```sql
   ALTER USER cv_screening_user WITH PASSWORD '<password_baru_acak_32+_char>';
   ```
   Lalu update `.env` di server dan restart service `cv-screening-api` dan `cv-screening-worker`. Password lama sudah ada di riwayat git publik, jadi **rotasi password wajib**. Menghapus dari kode saja tidak cukup.
7. Buat JWT secret baru (`openssl rand -hex 32`). Semua token lama otomatis tidak berlaku.

**Kriteria selesai**
- Aplikasi menolak start kalau `JWT_SECRET` kosong atau lemah (kecuali `APP_ENV=test`).
- Tidak ada password literal di repo (kecuali di riwayat git).
- Password DB di server sudah dirotasi.

**Tes wajib**
- `tests/test_config.py`: `Settings(APP_ENV="production", JWT_SECRET="short", DATABASE_URL="postgresql://x")` raise `ValidationError`, dan secret 64 hex char lolos.

---

## FX-02 — Kebocoran data antar-tenant (IDOR)

**Masalah.** Banyak query hanya memfilter `job_id`, `run_id`, atau `candidate_id` tanpa `tenant_id`. User tenant A bisa membaca atau mengubah data tenant B. Contoh paling parah:

- **`candidates.py` `reveal-identity`**: mencari kandidat dengan `WHERE c.id::text = %s OR c.candidate_code = %s` tanpa tenant. `candidate_code` berbentuk berurutan (`C-0001`, `C-0002`, …) dan dibuat dari sequence global. Siapa pun yang login bisa melihat **nama, email, dan telepon** kandidat milik tenant lain hanya dengan menebak `C-0001`.
- **`candidates.py` `delete`**: menghapus berdasarkan `d.original_filename = %s` tanpa tenant. Menghapus "cv.pdf" bisa ikut menghapus dokumen tenant lain dengan nama file yang sama.
- **`screenings.py`**: `trigger_screening_run` mengambil requirement set dan dokumen hanya dengan `job_id`. Tenant A bisa menjalankan screening atas CV milik tenant B, dan hasilnya disimpan dengan `tenant_id` A, sehingga data B pindah ke A.
- `get_candidate_detail`, `get_rankings`, `get_latest_screening`: tidak mengecek tenant.
- `requirements.py`: `/manual` (baris ±218), `/approve` (±316, ±330, ±349, ±382), `/compile` (±59 `MAX(version)`), dan `/import-approved` (DELETE ±157) punya query tanpa tenant.

**Solusi**
1. Buat helper di `src/api/dependencies.py`:
   ```python
   async def get_job_for_tenant(cur, job_id: UUID, tenant_id: UUID) -> dict:
       await cur.execute("SELECT * FROM jobs WHERE id = %s AND tenant_id = %s", (job_id, tenant_id))
       job = await cur.fetchone()
       if not job:
           raise HTTPException(status_code=404, detail="Job tidak ditemukan")
       return job
   ```
   Panggil helper ini **di awal setiap endpoint** yang menerima `job_id`. Kembalikan 404, bukan 403, supaya keberadaan resource tenant lain tidak bocor.
2. Tambahkan `AND tenant_id = %s` (atau `AND <alias>.tenant_id = %s`) ke **setiap** query SELECT, UPDATE, dan DELETE di `screenings.py`, `candidates.py`, `requirements.py`, `jobs.py`, dan `cvs.py`. Untuk query dengan subquery `IN (SELECT ...)`, filter tenant di subquery-nya juga.
3. `candidates.py`:
   - `reveal-identity`, `object`, `delete`: cari kandidat dengan `WHERE (c.id::text = %s OR c.candidate_code = %s) AND c.tenant_id = %s`.
   - **Hapus** pencarian berdasarkan `original_filename` di endpoint delete. Delete hanya boleh berdasarkan `document_id` atau `candidate_id`.
   - Kalau kandidat tidak ditemukan, kembalikan 404. Jangan mengembalikan objek default `"Candidate"` seperti sekarang.
4. `get_candidate_detail`, `get_rankings`, `get_latest_screening`: join ke `screening_runs` dan filter `sr.tenant_id = %s AND sr.job_id = %s`.
5. Lakukan audit menyeluruh: `grep -n "WHERE" src/api/routes/*.py` dan cek **satu per satu**. Buat daftar semua query beserta status filter tenant-nya di laporan akhir.
6. (Opsional tapi disarankan) Tambahkan Postgres Row-Level Security sebagai lapisan kedua. Kalau dikerjakan, lakukan lewat migrasi FX-07.

**Kriteria selesai**
- Tidak ada query ke tabel ber-`tenant_id` yang tidak memfilter tenant.

**Tes wajib** — `tests/test_tenant_isolation.py`
- Fixture: dua tenant (A dan B), masing-masing punya user RECRUITER, job, dokumen, kandidat, dan screening run (insert langsung ke DB tes).
- Dengan token user A, panggil setiap endpoint berikut memakai ID milik B. Semuanya harus **404** dan data B tidak berubah:
  `GET /jobs/{B}`, `POST /jobs/{B}/screenings`, `GET .../screenings/latest`, `GET .../rankings`, `GET .../candidates/{cv}`, `POST /candidates/{B_cand}/reveal-identity`, `POST /candidates/C-xxxx(B)/reveal-identity`, `DELETE /candidates/{B_cand}`, `POST /requirements/manual`, `POST /requirements/approve`, `GET/DELETE /jobs/{B}/cvs`.
- `reveal-identity` dengan kode yang tidak ada mengembalikan 404.

---

## FX-03 — Gerbang approval requirement set bisa dilewati

**Masalah.** `screenings.py` `trigger_screening_run`: kalau belum ada requirement set `APPROVED`, kode memakai versi terbaru apa pun statusnya ("Fallback ... for testing"). Policy linter hanya memblokir saat approve, jadi **kriteria terlarang bisa tetap dipakai untuk menilai** cukup dengan tidak pernah meng-approve.

**Solusi**
1. Hapus blok fallback. Kalau tidak ada set `APPROVED`, kembalikan `HTTP 409` dengan pesan `"Kriteria belum disetujui. Setujui requirement set terlebih dahulu."`.
2. Frontend (`App.tsx`): tangani 409 dengan menampilkan pesan dan mengarahkan user ke langkah approval.
3. Untuk tes atau script yang selama ini bergantung pada fallback, approve requirement set terlebih dahulu di fixture.

**Tes wajib**
- Screening tanpa set APPROVED mengembalikan 409.
- Setelah approve, screening mengembalikan 201 (atau 202 setelah FX-30).

---

## FX-04 — CORS wildcard + credentials

**Masalah.** `src/api/main.py`: `allow_origins=["*"]` bersama `allow_credentials=True`.

**Solusi**
1. Tambah setting `CORS_ALLOWED_ORIGINS: list[str]` (isi dari env, dipisah koma). Untuk dev, default `["http://localhost:5173"]`.
2. Gunakan setting itu di `CORSMiddleware`. Batasi `allow_methods` ke `["GET","POST","PATCH","DELETE","OPTIONS"]` dan `allow_headers` ke `["Authorization","Content-Type"]`.
3. Tambahkan domain production ke `.env` server. SPA saat ini di-serve dari domain yang sama, jadi cek apakah CORS sebenarnya diperlukan. Kalau tidak, cukup isi dengan origin domain itu.

**Tes wajib**
- Request preflight dari origin yang tidak terdaftar tidak mendapat header `access-control-allow-origin`.

---

## FX-05 — Endpoint tanpa autentikasi

**Masalah**
- `POST /api/v1/requirements/compile-preview` tidak memakai `Depends` auth, sehingga siapa pun di internet bisa menghabiskan kuota LLM.
- `GET /metrics` terbuka untuk publik dan membocorkan statistik bisnis (jumlah CV, token, dan sebagainya).

**Solusi**
1. `compile-preview`: tambah `current_user = Depends(require_role([ADMIN, RECRUITER, HIRING_MANAGER]))`, teruskan `tenant_id` ke `compile_job_requirements`, dan pasang `check_rate_limit(max_requests=10, window_seconds=60)`.
2. `/metrics`: lindungi dengan salah satu cara berikut. (a) Header `Authorization: Bearer <METRICS_TOKEN>` dari env. (b) Hanya izinkan `request.client.host` dari `127.0.0.1` kalau Prometheus berjalan lokal. Pilih (a) dan dokumentasikan di runbook.

**Tes wajib**
- `compile-preview` tanpa token mengembalikan 401.
- `/metrics` tanpa token mengembalikan 401, dengan token benar mengembalikan 200.

---

## FX-06 — Rate limiter

**Masalah.** `src/api/middleware/rate_limiter.py`:
- Kalau berjalan di belakang reverse proxy, `request.client.host` selalu `127.0.0.1`, jadi semua user berbagi satu kuota.
- Dictionary `_request_history` tidak pernah dibersihkan untuk key lama, sehingga terjadi memory leak.

**Solusi**
1. Jalankan uvicorn dengan `--proxy-headers --forwarded-allow-ips="127.0.0.1"` (update `deploy/systemd/cv-screening-api.service`). Dengan begitu `request.client.host` berisi IP asli.
2. Key limiter: kalau ada user terautentikasi, gunakan `user:{user_id}`. Kalau tidak, gunakan `ip:{ip}`. Tambahkan path route **template** (`request.scope["route"].path`), bukan URL mentah, supaya `/jobs/<uuid>` tidak membuat key baru di setiap request.
3. Hapus key yang list-nya kosong setelah dibersihkan. Lakukan juga sweep periodik: setiap 1000 request, hapus key yang timestamp terakhirnya lebih tua dari window.
4. Gunakan `time.monotonic()`, bukan `time.time()`.
5. Tambahkan catatan di runbook: limiter ini hanya berlaku untuk satu proses. Kalau nanti `--workers > 1`, pindahkan ke Redis atau Postgres.

**Tes wajib**
- Request ke-N+1 dalam window mengembalikan 429.
- Setelah window lewat, request kembali 200.
- Dua user berbeda tidak saling memengaruhi kuota.

---

## FX-07 — `migrate.sh` destruktif & belum ada sistem migrasi

**Masalah.** `scripts/migrate.sh` menjalankan `DROP DATABASE IF EXISTS cv_screening`. Kalau dijalankan di production, **semua data hilang**. Spec (`db_schema.sql` baris 2) menyebut Alembic, tapi Alembic belum dipakai. Fase-fase berikutnya butuh kolom dan tabel baru.

**Solusi**
1. Rename `scripts/migrate.sh` menjadi `scripts/reset_dev_db.sh`. Tambahkan guard di awal:
   ```bash
   if [[ "${APP_ENV:-}" == "production" || "${CONFIRM_RESET:-}" != "yes" ]]; then
     echo "Ditolak: script ini MENGHAPUS database. Set CONFIRM_RESET=yes dan pastikan APP_ENV bukan production."; exit 1
   fi
   ```
2. Setup Alembic (`alembic init migrations`), dengan URL diambil dari `settings.DATABASE_URL`.
3. Migrasi `0001_baseline`: buat skema persis seperti `docs/spec/schemas/db_schema.sql`. Untuk DB production yang sudah ada, jalankan `alembic stamp 0001_baseline` (jangan `upgrade`).
4. Semua perubahan skema di tiket lain (FX-10, FX-11, FX-14, FX-16, FX-25, FX-30) dibuat sebagai migrasi Alembic terpisah.
5. Tambah target Makefile: `migrate: alembic upgrade head`.
6. Update `docs/DEPLOYMENT_AND_RUNBOOK.md`: prosedur deploy menjadi backup, lalu `alembic upgrade head`, lalu restart.

**Tes wajib**
- `alembic upgrade head` di DB kosong berhasil.
- `alembic downgrade -1` lalu `upgrade head` untuk migrasi baru berhasil.
- `reset_dev_db.sh` tanpa `CONFIRM_RESET=yes` keluar dengan exit 1.

---

# FASE 2 — BUG FUNGSIONAL

## FX-10 — LLM verifier tidak pernah berjalan

**Masalah.** `screenings.py` baris ±137: `full_text = ""` dan variabel itu tidak pernah diisi. `verify_requirement_with_llm` di baris pertamanya menjalankan `if not cv_full_text: return rule_state`, sehingga **`use_verifier=true` tidak berpengaruh sama sekali**. Selain itu, teks lengkap CV memang tidak pernah disimpan: `adapter.py` membuat `full_text` (baris ±410), tapi teks itu tidak ikut dikembalikan di `profile`.

**Solusi**
1. `src/worker/adapter.py`: tambah `"full_text": full_text` ke dict `profile` yang dikembalikan.
2. `src/worker/redaction.py` `extract_identity_and_redact`: tambah `matching["full_text_redacted"] = redact_text(raw_profile.get("full_text", ""), name, emails, phones)`.
   - **Jangan** simpan `full_text` mentah di `matching_profile`. Teks mentah boleh tetap di `candidate_profiles.profile` (kolom identitas), karena kolom itu tidak dikirim ke LLM.
3. Reprocess: tambah endpoint admin atau script `scripts/reprocess_profiles.py` yang memasukkan ulang job `ingest_cv` untuk dokumen `READY` yang `matching_profile` tidak punya `full_text_redacted`.
4. `screenings.py`: ganti `full_text = ""` dengan `full_text = matching_prof.get("full_text_redacted", "")`.
5. Grounding check di `verifier.py`:
   - Normalisasi whitespace di kedua sisi (`" ".join(s.split()).lower()`) sebelum memeriksa `quote in text`.
   - Tolak quote yang terlalu pendek (`len(quote) < 15` karakter) karena bisa ditemukan di mana saja (contoh: "Python"). Perlakukan sebagai `GROUNDING_FAIL`.
   - Quote harus berada di dalam **salah satu snippet** yang dikirim, bukan sekadar di mana saja di CV.
6. Verifier hanya boleh **menurunkan** atau mengonfirmasi state, bukan menaikkan dari NOT_DEMONSTRATED. Saat ini verifier hanya dipanggil kalau state PARTIAL atau STRONG, jadi pertahankan itu. Tambahkan aturan: kalau rule menghasilkan PARTIAL dan LLM mengatakan STRONG, terima hanya kalau quote berasal dari konteks `experience`. Kalau tidak, tetap PARTIAL.

**Tes wajib** — `tests/test_verifier.py` (mock gateway, tanpa jaringan)
- Dengan `use_verifier=true` dan profil berisi `full_text_redacted`, gateway **benar-benar dipanggil** (assert jumlah panggilan > 0).
- LLM mengembalikan quote yang tidak ada di snippet: state kembali ke rule_state dan flag `GROUNDING_FAIL`.
- LLM mengembalikan quote "Python" (pendek): `GROUNDING_FAIL`.
- LLM mengembalikan state di luar enum: `INVALID_LLM_STATE`.
- `full_text_redacted` tidak mengandung email atau telepon kandidat.

---

## FX-11 — Verifier memblokir event loop & cache tidak aman

**Masalah**
- `call_dev_llm` (`gateway.py`) dipanggil dari handler async. Fungsi ini membuat `ThreadPoolExecutor` dan `asyncio.run` lalu memanggil `.result()`, sehingga **seluruh API berhenti** selama LLM merespons (bisa sampai 90 detik per panggilan). `_record_call` juga berjalan di event loop lain dan memakai pool DB milik loop utama, sehingga gagal diam-diam.
- Cache (`data/verifier_cache.json`) dibaca dan ditulis ulang utuh di setiap panggilan. Cara ini tidak aman untuk akses bersamaan, lambat, dan key-nya tidak menyertakan versi model, versi prompt, atau deskripsi requirement.

**Solusi**
1. Ubah `verify_requirement_with_llm` menjadi `async def`, panggil langsung `await gateway.call_chat(messages, task="verification", tenant_id=...)`. Hapus pemakaian `call_dev_llm` dari jalur API. Fungsi itu boleh tetap ada untuk script, dengan nama `call_llm_sync_for_scripts`.
2. Konstanta `VERIFIER_PROMPT_VERSION = "v2"` di `verifier.py`.
3. Migrasi: tabel `verifier_cache`
   ```sql
   CREATE TABLE verifier_cache (
     cache_key text PRIMARY KEY,
     state text NOT NULL, quote text NOT NULL DEFAULT '', flags text[] NOT NULL DEFAULT '{}',
     model text NOT NULL, prompt_version text NOT NULL,
     created_at timestamptz NOT NULL DEFAULT now()
   );
   ```
   Key cache = `sha256(model | prompt_version | requirement_id | description | kind | rule_state | snippets)`.
4. Hasil `LLM_PARSE_ERROR` dan kegagalan jaringan **tidak** di-cache.
5. Batasi konkurensi verifier dengan `asyncio.Semaphore(settings.VERIFIER_CONCURRENCY)` (default 4). Kumpulkan semua panggilan untuk satu kandidat dengan `asyncio.gather`.
6. Hapus `data/verifier_cache.json` dari repo kalau ada, dan tambahkan ke `.gitignore`.

**Tes wajib**
- Dua panggilan dengan input identik: gateway hanya dipanggil sekali (yang kedua dari cache DB).
- Mengganti `VERIFIER_PROMPT_VERSION` membuat cache miss.
- Selama verifier menunggu (mock `asyncio.sleep(2)`), request `GET /health` tetap merespons di bawah 200 ms.

---

## FX-12 — JD berisi email/telepon HR menyebabkan error 500

**Masalah.** `gateway.call_chat` memanggil `verify_redacted_text` **di luar** blok `try`. Fungsi itu melempar `PrivacyViolationError` kalau ada email atau telepon. JD yang memuat "Kirim CV ke hr@perusahaan.com" (sangat umum) membuat `compile_job_requirements` crash dengan 500, alih-alih fallback ke parser rule-based.

**Solusi**
1. `jd_compiler.compile_job_requirements`: **sebelum** mengirim ke LLM, bersihkan JD dengan mengganti email menjadi `[EMAIL]` dan telepon menjadi `[TELEPON]` (pakai regex di `redaction.py`). Email dan telepon di JD adalah kontak perusahaan, bukan PII kandidat, dan tidak berguna untuk ekstraksi kriteria.
2. Bungkus panggilan gateway di `compile_job_requirements` dengan `try/except PrivacyViolationError`. Kalau tertangkap, log warning dan jalankan `compile_job_requirements_rule_based`.
3. Untuk task `verification` (data kandidat), pemblokiran tetap dipertahankan. Itu memang lapisan pengaman yang benar, tapi pastikan pemanggilnya menangkap exception dan kembali ke `rule_state` dengan flag `PII_BLOCKED`.
4. Perluas `PHONE_REGEX` agar mencakup format `+62 812-xxxx`, `(021) xxxx`, dan nomor internasional umum `\+\d{1,3}[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}`. Satukan regex di satu modul (`src/domain/pii.py`) lalu import dari `gateway.py` dan `redaction.py`. Saat ini regex-nya terduplikasi.

**Tes wajib**
- Compile JD yang mengandung `hr@contoh.com` dan `0812-3456-7890` mengembalikan 201 dengan requirements, tanpa error.
- Prompt yang dikirim ke gateway (mock) tidak mengandung email atau telepon tersebut.

---

## FX-13 — Processor: error handling transaksi rusak + bug `candidate_id`

**Masalah** di `src/worker/processor.py`
1. Kalau terjadi exception di tengah transaksi, blok `except` langsung menjalankan `UPDATE`. Di psycopg 3, transaksi yang error berstatus *aborted*, sehingga UPDATE tersebut gagal (`InFailedSqlTransaction`) dan dokumen **tertahan** di status lama.
2. `SELECT` di awal tidak mengambil kolom `candidate_id`, jadi `doc.get("candidate_id")` selalu `None`. Setiap reprocess **membuat kandidat baru** dengan kode baru, dan kandidat lama menjadi yatim.
3. Lock `FOR UPDATE` dan transaksi ditahan selama ekstraksi PDF/OCR dan embedding (detik hingga menit). Ini transaksi panjang, dan `embed_texts` (CPU) berjalan sinkron di dalam fungsi async sehingga memblokir event loop.
4. Upsert `candidate_identities` hanya memperbarui name, email, dan phone. `location_raw` dan `other_personal` tidak ikut diperbarui.
5. Chunk di-insert satu per satu (N round-trip).

**Solusi** — susun ulang `process_document` menjadi 3 tahap:
1. **Klaim (transaksi pendek):** `SELECT ... , candidate_id FROM documents WHERE id=%s FOR UPDATE`. Cek status terminal, lalu `UPDATE documents SET status='PROCESSING'`, lalu COMMIT. (Tambahkan `PROCESSING` ke CHECK constraint status lewat migrasi kalau ada constraint.)
2. **Kerja berat (tanpa transaksi):** baca file, `sanitize_file`, `extract_candidate_profile`, `extract_identity_and_redact`, `embed_texts`. Panggil yang CPU-bound lewat `await asyncio.to_thread(...)`.
3. **Simpan (satu transaksi pendek):** dedup check, upsert candidate/identity/profile, `DELETE` chunk lama, insert chunk dengan `cur.executemany(...)`, `UPDATE documents SET status='READY'`, COMMIT.
4. Error handling: kalau terjadi exception di tahap mana pun, jalankan `await conn.rollback()` kalau koneksi masih dalam transaksi, lalu tulis status `NEEDS_REVIEW` dengan alasan error menggunakan **koneksi baru** dari pool. Error kemudian di-raise ulang (atau kembalikan status) agar worker tahu (lihat FX-14).
5. Upsert identity: `ON CONFLICT (candidate_id) DO UPDATE SET full_name=EXCLUDED.full_name, email=EXCLUDED.email, phone=EXCLUDED.phone, location_raw=EXCLUDED.location_raw, other_personal=EXCLUDED.other_personal`.
6. Pakai ulang `candidate_id` yang sudah ada saat reprocess.

**Tes wajib**
- Reprocess dokumen yang sama dua kali menghasilkan `candidate_id` dan `candidate_code` yang **sama**, dan jumlah baris `candidates` tidak bertambah.
- Mock `embed_texts` agar raise Exception: dokumen berakhir di `NEEDS_REVIEW` dengan alasan `PROCESSING_ERROR...`, bukan tertahan di `RECEIVED` atau `PROCESSING`.
- Jumlah `profile_chunks` setelah reprocess sama dengan jumlah chunk (tidak dobel).

---

## FX-14 — Worker tanpa retry & job RUNNING tidak bisa diambil ulang

**Masalah** di `src/worker/main.py`
- Kalau gagal, status langsung `FAILED`. Kolom `attempts` naik tapi tidak pernah dipakai untuk retry.
- Kalau worker crash atau restart saat job berstatus `RUNNING`, job itu tertahan selamanya (`locked_at` tidak pernah dicek).
- `process_document` menelan semua error dan mengembalikan dict, sehingga job hampir selalu ditandai `DONE`.
- Polling setiap 0,5 detik ke DB.

**Solusi**
1. Konstanta `MAX_ATTEMPTS = 3`. Saat gagal:
   - Kalau `attempts + 1 < MAX_ATTEMPTS`: `status='PENDING'`, `attempts=attempts+1`, `run_after = now() + (interval '1 minute' * power(2, attempts))`.
   - Selain itu: `status='FAILED'`.
2. **Reaper:** di awal setiap iterasi (atau setiap 60 detik), jalankan `UPDATE jobs_queue SET status='PENDING', locked_at=NULL WHERE status='RUNNING' AND locked_at < now() - interval '15 minutes'`.
3. `process_document` mengembalikan status. Kalau statusnya `NEEDS_REVIEW` karena `PROCESSING_ERROR` (error teknis, bukan CV yang memang bermasalah), lempar exception agar mekanisme retry berjalan. Hanya penolakan karena isi (CV kosong, terenkripsi, bukan CV) yang dianggap DONE.
4. Pindahkan update status job ke koneksi terpisah dari koneksi yang dipakai `process_document`.
5. Ganti polling dengan `LISTEN cv_jobs` dan `NOTIFY cv_jobs` (dikirim dari endpoint upload setelah insert ke `jobs_queue`), dengan fallback polling setiap 5 detik.
6. Opsional: `WORKER_CONCURRENCY` (default 2), jalankan N task `worker_loop` paralel. `FOR UPDATE SKIP LOCKED` sudah aman untuk itu.
7. Muat model embedding saat worker start (panggil `get_embedding_model()` di `main()`), bukan saat dokumen pertama diproses.

**Tes wajib**
- Job yang gagal 1 kali kembali ke `PENDING` dengan `attempts=1` dan `run_after` di masa depan.
- Job yang gagal 3 kali berstatus `FAILED`.
- Job `RUNNING` dengan `locked_at` 20 menit lalu kembali ke `PENDING` setelah reaper berjalan.

---

## FX-15 — Gateway LLM

**Masalah** di `src/infrastructure/gateway.py`
- `resolve_router_key()` membaca file SQLite milik aplikasi lain (`/srv/apps/9router/data/db/data.sqlite`) dan fallback ke `"dev-key"`. Coupling ini rapuh dan berisiko.
- Setiap panggilan membuat `httpx.AsyncClient` baru, jadi tidak ada reuse koneksi.
- Model verifikasi memakai `LLM_MODEL_JD_COMPILER`.
- `prompt_version` di-hardcode `'v1.0'` saat insert `model_calls`.
- Panggilan yang gagal (HTTP non-200 atau exception) tidak tercatat di `model_calls`.

**Solusi**
1. Hapus pembacaan SQLite. `LLM_GATEWAY_KEY` wajib diisi lewat env. Kalau kosong, gateway dalam keadaan **disabled**: `call_chat` mengembalikan `None` dengan log warning sekali saat start, dan sistem otomatis memakai jalur rule-based.
2. Satu `httpx.AsyncClient` per proses (dibuat lazy, ditutup di lifespan FastAPI dan di shutdown worker). Timeout dibuat granular: `httpx.Timeout(connect=5, read=60, write=10, pool=5)`.
3. Setting baru: `LLM_MODEL_VERIFIER` (default sama dengan JD compiler). Tambahkan parameter `model` dan `prompt_version` ke `call_chat`.
4. Catat **semua** panggilan ke `model_calls`, termasuk yang gagal, dengan `status='FAILED'` dan `error` (tambahkan kolom lewat migrasi kalau belum ada).
5. Retry sekali untuk HTTP 429 dan 5xx dengan jeda 2 detik.
6. Pindahkan logika parsing JSON (4 strategi) ke fungsi terpisah `parse_llm_json(text) -> dict | list | None` lalu beri unit test.

**Tes wajib**
- `parse_llm_json`: JSON murni, JSON dalam code fence, JSON diapit teks, array, dan teks sampah (mengembalikan None).
- Gateway tanpa key mengembalikan `None` tanpa melakukan request jaringan.
- Response HTTP 500 menghasilkan baris `model_calls` dengan `status='FAILED'`.

---

## FX-16 — `/metrics` berisi angka palsu

**Masalah** di `src/api/routes/metrics.py`
- `pipeline_stage_latency_seconds` untuk sanitizer, parsing, redaction, embedding, dan scoring di-hardcode (`0.052`, `0.315`, dan seterusnya).
- Kalau tidak ada kegagalan, endpoint justru menampilkan `cv_failures_total{reason="ENCRYPTED_FILE"} 1` dan `EMPTY_DOCUMENT 1`.

**Solusi**
1. Hapus semua angka hardcode.
2. Di `processor.py`, ukur durasi setiap tahap dengan `time.perf_counter()` lalu simpan ke kolom baru `documents.timings jsonb` (lewat migrasi), contoh `{"sanitizer": 0.04, "parsing": 0.3, ...}`.
3. Di `/metrics`, hitung rata-rata dan p95 setiap tahap dari 500 dokumen terakhir. Kalau belum ada data, **jangan tampilkan** baris metrik tersebut.
4. Untuk `cv_failures_total`: kalau tidak ada kegagalan, tampilkan nol atau tidak tampilkan sama sekali, jangan angka palsu.
5. (Opsional) Ganti format manual dengan library `prometheus_client`.

**Tes wajib**
- DB tes kosong: output `/metrics` tidak mengandung `ENCRYPTED_FILE` maupun angka latensi.
- Setelah satu dokumen diproses: ada baris latensi dengan nilai yang berasal dari `timings`.

---

# FASE 3 — AKURASI SCORING

## FX-20 — Skill matcher false positive

**Masalah.** `kind_rules.py` `eval_skill` (dan pola yang sama di `eval_responsibility`, `eval_certification`, `eval_education`, `eval_leadership`):

Hasil uji pada kode saat ini:

| Kriteria | Kalimat CV | Hasil sekarang | Seharusnya |
|---|---|---|---|
| `skill:java` | "Membangun dashboard dengan JavaScript dan React" | STRONG | NOT_DEMONSTRATED |
| `skill:docker` | "Belum pernah menggunakan Docker, ingin belajar" | STRONG | NOT_DEMONSTRATED |
| `skill:sql` | "Menyimpan data lokal di SQLite pada aplikasi mobile" | STRONG | NOT_DEMONSTRATED |

Penyebabnya:
1. Regex `rf"\b{re.escape(kw)}"` hanya punya batas kata **di depan**, tidak di belakang.
2. Tidak ada deteksi negasi.
3. Beberapa fungsi memakai substring `"hr" in c_lower`, yang cocok dengan "three", "chrome", "hrs", dan sebagainya. Contoh: `eval_certification` sekitar baris ±636, dan `eval_education` memakai `deg in summary_txt.lower()`.
4. Kutipan bukti adalah `combined_text[:120]`, yaitu 120 karakter pertama pengalaman, **bukan kalimat yang cocok**. Akibatnya penjelasan untuk HR sering tidak relevan dan grounding verifier (FX-10) jadi lemah.
5. Fallback keyword (kalau requirement tidak punya `concepts`) memakai stopword Indonesia saja. Kata seperti "experience", "years", "with", "knowledge", dan "good" menjadi keyword dan cocok dengan hampir semua CV.

**Solusi** — buat modul baru `src/domain/text_match.py`, lalu **semua** fungsi `eval_*` wajib memakai modul ini (tidak boleh lagi ada `re.search(rf"\b...")` atau `x in text` untuk mencocokkan keyword):

```python
NEGATION_CUES_ID = ["belum pernah", "tidak pernah", "belum menguasai", "tidak menguasai",
                    "ingin belajar", "sedang belajar", "tertarik mempelajari", "tanpa"]
NEGATION_CUES_EN = ["never", "no experience", "not familiar", "willing to learn",
                    "want to learn", "learning", "without", "basic knowledge of"]  # 'basic' -> turunkan ke PARTIAL, lihat di bawah

def keyword_regex(kw: str) -> re.Pattern:
    # batas kata di KEDUA sisi; aman untuk c++, c#, .net, node.js, ci/cd
    return re.compile(rf"(?<![\w+#.]){re.escape(kw)}(?![\w+#])", re.IGNORECASE)

def split_sentences(text: str) -> list[str]: ...   # pecah per bullet/kalimat (., ;, \n, •)

def find_mentions(text: str, keywords: list[str]) -> list[Mention]:
    """Kembalikan kalimat yang memuat keyword dan TIDAK dinegasi.
    Negasi = cue muncul dalam jendela 6 token sebelum keyword di kalimat yang sama."""
```

Aturannya:
1. Batas kata di kedua sisi. `java` tidak cocok dengan `javascript`, `sql` tidak cocok dengan `sqlite`, sedangkan `c++`, `c#`, `node.js`, dan `ci/cd` tetap bisa dicocokkan.
2. Kalimat dengan negasi diabaikan sebagai bukti. Kalimat dengan "basic"/"dasar"/"pemula" maksimal menghasilkan PARTIAL.
3. `evidence.quote` berisi **kalimat yang cocok** (maksimal 200 karakter), bukan potongan awal teks.
4. Aturan konteks tetap seperti sekarang: pengalaman kerja menghasilkan STRONG, sedangkan proyek, organisasi, daftar skill, atau summary menghasilkan PARTIAL.
5. Fallback tanpa `concepts`:
   - Stopword ID **dan** EN (minimal 150 kata umum, simpan di `src/domain/data/stopwords.txt`), dan panjang keyword minimal 3 karakter.
   - Hanya token yang ada di alias taksonomi atau yang berbentuk teknis (mengandung huruf kapital di tengah, angka, `+`, `#`, `.`) yang dipakai.
   - Requirement tanpa concept diberi flag `NO_CONCEPT_MAPPING`, dan confidence dibatasi maksimal 0,6.
6. Ganti semua `"x" in text.lower()` di `eval_certification`, `eval_education`, dan `eval_leadership` dengan `find_mentions`.

**Tes wajib** — `tests/test_text_match.py` + tambahan di `tests/test_kind_rules.py`
- Tiga kasus di tabel atas menghasilkan NOT_DEMONSTRATED.
- `skill:javascript` + kalimat "JavaScript" menghasilkan STRONG.
- `skill:c++` + "Develop firmware in C++" menghasilkan STRONG, dan `skill:c` + "C++" tidak cocok.
- `skill:node.js` + "REST API dengan Node.js" menghasilkan STRONG.
- "Tidak pernah memakai Kubernetes, tapi aktif memakai Docker": `kubernetes` NOT_DEMONSTRATED, `docker` STRONG.
- `cert:hr` tidak cocok dengan teks "three years".
- Quote bukti sama persis dengan kalimat yang memuat keyword.
- Golden dataset (`evaluate.py`) tetap lulus. Kalau ada label yang berubah karena perbaikan ini, **jelaskan per kasus** di laporan, jangan mengubah label diam-diam.

---

## FX-21 — Tanggal "sekarang" di-hardcode

**Masalah**
- `ScreeningRunCreate.as_of` default `"2026-10-01"`, dan `kind_rules.parse_ym` serta `eval_experience_duration` juga punya default `as_of="2026-10-01"`. Akibatnya, mulai bulan depan pengalaman kandidat yang masih bekerja ("Present") akan terus dihitung kurang.
- Spec `02_SCORING_RUBRIC_SPEC.md` baris 94: kalau hanya ada tahun, **awal = Juli, akhir = Juni**, dan ditandai INFERENSI. Kode saat ini mengembalikan bulan 7 untuk awal **maupun** akhir.

**Solusi**
1. `ScreeningRunCreate.as_of: date | None = None`. Kalau None, pakai `datetime.now(ZoneInfo("Asia/Jakarta")).date()`. Simpan nilai yang dipakai ke `screening_runs.as_of` (supaya run tetap bisa direproduksi).
2. Di `kind_rules.py`, `as_of` menjadi parameter **wajib** (hapus default) di semua fungsi. Perbaiki semua pemanggilnya.
3. `parse_ym(val, as_of, is_end: bool)`: kalau hanya tahun, kembalikan `(Y, 7)` untuk awal dan `(Y, 6)` untuk akhir. Tambahkan flag `DATE_YEAR_ONLY_INFERRED` ke hasil evaluasi.
4. Validasi: tanggal akhir sebelum tanggal awal menghasilkan flag `DATE_INCONSISTENT` dan interval diabaikan. Tanggal awal di masa depan relatif terhadap `as_of` juga diabaikan.

**Tes wajib**
- `as_of` tidak dikirim: run memakai tanggal hari ini.
- "2020 – 2022" menghasilkan 2020-07 s/d 2022-06 = 24 bulan, dengan flag inferensi.
- "Present" dengan `as_of=2027-03-15` menghasilkan akhir 2027-03.

---

## FX-22 — `category_weights` tidak sinkron dengan bobot requirement

**Masalah.** Spec (`02_SCORING` baris 33): *bobot kategori dibagi ke kriteria di dalamnya* (contoh EXPERIENCE 40 = R1 25 + R2 15). `scorer.py` sudah benar memakai bobot per requirement. Masalahnya, **tidak ada yang memastikan** jumlah bobot requirement per kategori sama dengan `category_weights`. UI menampilkan 40/30/15/15, padahal hasil compile LLM atau rule bisa memberi bobot apa saja. Akibatnya, angka yang dilihat HR tidak mencerminkan perhitungan skor yang sebenarnya.

**Solusi**
1. Fungsi `normalize_weights(requirement_set) -> requirement_set` di `src/domain/scorer.py`. Untuk setiap kategori, bobot requirement di-rescale proporsional supaya jumlahnya sama dengan `category_weights[cat]`, dibulatkan 1 desimal (sisa pembulatan diberikan ke requirement dengan bobot terbesar). Kategori yang tidak punya requirement: bobotnya didistribusikan proporsional ke kategori lain, dan dikembalikan sebagai peringatan `EMPTY_CATEGORY:<cat>`.
2. Panggil `normalize_weights` di akhir `compile_job_requirements` dan saat `/approve`.
3. Validasi saat approve: jumlah `category_weights` = 100 (toleransi ±0,5). Kalau tidak, kembalikan 422.
4. Frontend: kalau HR mengubah bobot kategori, kirim ke backend lalu tampilkan bobot requirement hasil normalisasi. Hapus nilai hardcode `{EXPERIENCE: 40, ...}` di `App.tsx` (baris ±648 dan ±902) dan ambil dari response API.
5. `test_scorer_parity.py` harus tetap lulus. Requirement set golden dataset sudah konsisten, jadi normalisasi tidak boleh mengubah bobotnya.

**Tes wajib**
- Kategori EXPERIENCE 40 dengan R1=10 dan R2=10 menghasilkan R1=20 dan R2=20.
- Approve dengan total kategori 90 mengembalikan 422.
- Approved set JD-01 setelah normalisasi identik dengan sebelumnya.

---

## FX-23 — JD compiler

**Masalah** di `src/domain/jd_compiler.py`
1. Fallback rule-based: `imp = "MUST_HAVE" if (... or req_idx <= 2)`. Dua bullet pertama yang tidak dikenali **otomatis** menjadi MUST_HAVE. Karena MUST_HAVE menentukan band A/B/C, urutan penulisan JD bisa mengubah ranking.
2. Importance tidak membaca header seksi ("Kualifikasi wajib" vs "Nilai tambah / Nice to have").
3. Output LLM tidak divalidasi: `category`, `kind`, dan `importance` bisa berisi apa saja, `weight` bisa negatif atau 500, `requirement_id` bisa duplikat. Default `importance` kalau field kosong adalah `MUST_HAVE`, yang terlalu ketat.
4. Regex `r"kubernetes|k8s|cloud\s*\(aws|gcp|azure"`: karena precedence operator `|`, pola ini cocok dengan kata "gcp" atau "azure" di mana saja, bukan "cloud (aws/gcp/azure)". Banyak pola juga tidak punya `\b` (`python|fastapi`, `skala`, `certified`, `must` yang cocok dengan "mustahil").
5. Augmentasi concept: semua `CONCEPT_RULES` yang cocok ditambahkan ke requirement apa pun, termasuk yang beda kategori. Contoh: requirement pengalaman yang menyebut "Python" ikut mendapat `skill:python`.

**Solusi**
1. Hapus `req_idx <= 2`.
2. Parser seksi: deteksi header (baris diakhiri ":" atau diawali `#`, atau cocok dengan pola `kualifikasi|persyaratan|requirements|wajib|must`, `nilai tambah|diutamakan|preferred|nice to have|plus`). Bullet di bawah header "wajib" menjadi MUST_HAVE, di bawah "nilai tambah" menjadi NICE_TO_HAVE, dan selain itu STRONG_PREFERENCE. Kata `wajib`, `harus`, `minimal`, atau `must` (dengan `\b`) di dalam bullet tetap memaksa MUST_HAVE.
3. Model Pydantic `CompiledRequirement` dengan `Literal[...]` untuk category, kind, dan importance, serta `weight: float = Field(ge=1, le=30)`. Item LLM yang tidak valid diperbaiki kalau bisa (clamp weight, default importance **STRONG_PREFERENCE**). Kalau tidak bisa diperbaiki, item dibuang dan alasannya dicatat di `compile_warnings`. ID dibuat ulang berurutan `R1..Rn`.
4. Perbaiki semua regex `CONCEPT_RULES`: tambahkan `\b...\b` dan perbaiki grouping (`cloud\s*\((?:aws|gcp|azure)\)|\b(?:kubernetes|k8s)\b`).
5. Augmentasi concept hanya untuk rule yang `category`-nya sama dengan kategori requirement.
6. Batasi MUST_HAVE: kalau lebih dari 5 requirement berstatus MUST_HAVE, tambahkan warning `TOO_MANY_MUST_HAVE` supaya HR meninjau ulang. Jangan diubah otomatis.
7. (Akan dipindah ke data di FX-31.)

**Tes wajib**
- JD dengan seksi "Kualifikasi Wajib" (2 bullet) dan "Nilai Tambah" (2 bullet): importance sesuai seksinya, tidak bergantung pada urutan.
- Menukar urutan bullet tidak mengubah importance.
- Output LLM (mock) dengan `weight: 500`, `importance: "SUPER"`, dan ID duplikat dinormalisasi atau dibuang dengan warning.
- Teks "Familiar dengan Azure DevOps" **tidak** menghasilkan concept `skill:kubernetes`.

---

## FX-24 — Usia & gender: pisahkan dari skor menjadi Eligibility Gate administratif

> **Keputusan desain (disetujui pemilik proyek, 14 Okt 2026).** Usia dan gender **tidak boleh** menjadi bagian dari scoring rubric, skor, band, maupun input LLM. Keduanya hanya boleh dipakai sebagai **syarat administratif** yang terpisah, opsional per job, wajib disertai justifikasi tertulis, wajib disetujui ADMIN, dan dievaluasi secara deterministik. Sistem **tidak pernah menolak kandidat secara otomatis**: hasil gate hanya berupa status dan filter, dan keputusan tetap dibuat HR.
>
> Latar belakang: SE Menaker No. M/6/HK.04/V/2025 menggolongkan pembatasan usia sebagai diskriminatif, kecuali ada karakteristik jabatan yang secara nyata memengaruhi kemampuan kerja dan pembatasan itu tidak mengurangi kesempatan kerja. Selain itu, UU PDP memberi hak keberatan atas keputusan yang sepenuhnya otomatis. Karena itu: wajib ada justifikasi, ada jejak audit, dan tidak ada penolakan otomatis.

### Masalah saat ini
1. Commit `5bbbf90` membuat usia dan gender diizinkan sebagai **requirement biasa** di scoring rubric.
2. `redaction.py` menghapus tanggal lahir dan gender dari `matching_profile`, sehingga requirement tersebut **tidak mungkin terbukti** dan selalu NOT_DEMONSTRATED. Kalau requirement itu MUST_HAVE, **semua kandidat** turun ke band B atau C secara diam-diam.
3. Tidak ada justifikasi, persetujuan, atau jejak audit untuk kriteria demografis.
4. `adapter.py` hanya mengenali format `Tanggal lahir:` dan `Jenis kelamin:`. Format umum seperti `TTL: Jakarta, 12 Maret 1999` atau `Date of Birth` tidak terbaca.

### Arsitektur target

```
CV → ekstraksi ──┬─► identity (candidate_identities.other_personal: DOB, gender)
                 │        └─► Eligibility Gate (deterministik, TANPA LLM)
                 │                 └─► candidate_eligibility: ELIGIBLE / NOT_ELIGIBLE / UNKNOWN / NOT_APPLICABLE
                 │
                 └─► matching_profile (sudah diredaksi) ─► Scoring ─► skor, band, rekomendasi
                                                                      (TIDAK tahu apa pun soal usia/gender)

Ranking = urutan berdasarkan SKOR + badge eligibility + filter UI. Eligibility TIDAK mengubah urutan atau skor.
```

**Invarian yang wajib dijaga (akan diuji):**
- I-1: Skor, band, rekomendasi, dan rank kandidat **identik** dengan atau tanpa eligibility rules.
- I-2: Data tanggal lahir dan gender **tidak pernah** masuk ke `matching_profile`, `profile_chunks`, prompt LLM, `evidence`, atau `candidate_scores`.
- I-3: Tidak ada status kandidat yang otomatis berubah menjadi ditolak, dihapus, atau disembunyikan permanen karena eligibility.
- I-4: Data yang tidak ada (DOB atau gender tidak dicantumkan) menghasilkan `UNKNOWN`, **bukan** `NOT_ELIGIBLE`.
- I-5: Tidak boleh ada inferensi. Usia tidak boleh ditebak dari tahun lulus, lama pengalaman, atau foto. Gender tidak boleh ditebak dari nama, foto, atau kata ganti.

### Langkah 1 — Migrasi skema (Alembic, setelah FX-07)

```sql
CREATE TABLE eligibility_rules (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  job_id           uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  rule_type        text NOT NULL CHECK (rule_type IN ('AGE_MAX','AGE_MIN','GENDER')),
  value            jsonb NOT NULL,
      -- AGE_MAX / AGE_MIN : {"years": 27}           (integer 15..70)
      -- GENDER            : {"allowed": ["F"]}       (subset tidak kosong dari ["M","F"], bukan keduanya)
  basis_category   text NOT NULL CHECK (basis_category IN (
                     'KARAKTERISTIK_JABATAN',   -- sifat pekerjaan memengaruhi kemampuan kerja
                     'REGULASI_SEKTOR',         -- diwajibkan regulasi/otoritas sektor tertentu
                     'PROGRAM_KHUSUS',          -- mis. MT/ODP dengan ikatan dinas
                     'LAINNYA')),
  justification    text NOT NULL CHECK (char_length(justification) >= 30),
  reference_date   date NOT NULL,              -- tanggal acuan hitung usia (mis. tanggal tutup lowongan)
  status           text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','REVOKED')),
  created_by       uuid NOT NULL REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  approved_by      uuid REFERENCES users(id),
  approved_at      timestamptz,
  revoked_by       uuid REFERENCES users(id),
  revoked_at       timestamptz,
  revoke_reason    text,
  CHECK (status <> 'APPROVED' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)),
  CHECK (status <> 'REVOKED'  OR (revoked_by  IS NOT NULL AND revoke_reason IS NOT NULL))
);
-- satu rule aktif per tipe per job
CREATE UNIQUE INDEX eligibility_rules_one_active
  ON eligibility_rules (job_id, rule_type) WHERE status IN ('DRAFT','APPROVED');
CREATE INDEX ON eligibility_rules (tenant_id, job_id);

CREATE TABLE candidate_eligibility (
  run_id          uuid NOT NULL REFERENCES screening_runs(id) ON DELETE CASCADE,
  candidate_id    uuid NOT NULL REFERENCES candidates(id),
  tenant_id       uuid NOT NULL,
  document_id     uuid NOT NULL REFERENCES documents(id),
  overall_status  text NOT NULL CHECK (overall_status IN ('ELIGIBLE','NOT_ELIGIBLE','UNKNOWN','NOT_APPLICABLE')),
  details         jsonb NOT NULL DEFAULT '[]',
      -- [{"rule_id": "...", "rule_type": "AGE_MAX", "status": "NOT_ELIGIBLE", "reason_code": "AGE_ABOVE_MAX"}]
      -- JANGAN simpan usia, tanggal lahir, atau gender di sini (minimisasi data)
  evaluated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (run_id, candidate_id)
);
CREATE INDEX ON candidate_eligibility (tenant_id, run_id, overall_status);
```

Tambahan:
- Kolom `screening_runs.eligibility_snapshot jsonb`: salinan rule `APPROVED` (id, type, value, reference_date) saat run dibuat. Run lama tidak berubah walaupun rule kemudian diubah atau dicabut.
- Skema saat ini tidak punya tabel `tenants` (tenant_id hanya kolom uuid), jadi `tenant_id` di sini juga tanpa FK, konsisten dengan tabel lain.

### Langkah 2 — Ekstraksi data administratif (`src/worker/adapter.py`, `redaction.py`)

1. **Tanggal lahir.** Kenali label (case-insensitive): `tanggal lahir`, `tgl lahir`, `tempat(,| dan| &)? tanggal lahir`, `TTL`, `date of birth`, `DOB`, `born`, `lahir`.
   - Parser `parse_dob(raw: str) -> DobResult` di modul baru `src/domain/eligibility.py`:
     - Format yang didukung: `12 Maret 1999`, `12 Mar 1999`, `March 12, 1999`, `12-03-1999`, `12/03/1999` (asumsikan **DD/MM** untuk ID; kalau bagian pertama > 12 tetap DD/MM, kalau kedua bagian ≤ 12 tetap DD/MM tapi beri flag `DOB_DMY_ASSUMED`), `1999-03-12`, dan **tahun saja** `1999`.
     - Buang prefix tempat ("Jakarta, ").
     - Hasilnya berupa `{precision: "DAY"|"YEAR"|None, date_or_year, flags}`. Kalau tidak bisa diparse, `precision=None`.
     - Tahun yang tidak masuk akal (umur < 15 atau > 80 terhadap tanggal hari ini) dianggap tidak bisa diparse, dengan flag `DOB_IMPLAUSIBLE`.
2. **Gender.** Kenali label `jenis kelamin`, `gender`, `sex`, `kelamin`. Normalisasi:
   - `laki-laki|laki laki|pria|male|l|m` → `M`
   - `perempuan|wanita|female|p|f` → `F`
   - Selain itu (termasuk kosong) → tidak diketahui. Nilai mentah **tidak** disimpan.
   - **Dilarang** memakai sumber lain apa pun (nama, foto, kata ganti, sapaan "Bpk/Ibu").
3. Simpan hasil di `candidate_identities.other_personal` sebagai `{"dob": {...}, "gender": "M"|"F"|null}`. **Hanya di tabel identitas.**
   - **Bug yang ikut diperbaiki:** `db_schema.sql` baris 86 menyatakan `other_personal` adalah *JSON terenkripsi (pgp_sym_encrypt)*, tapi `processor.py` menyimpannya sebagai JSON **plaintext** (`json.dumps(...).encode()`). Perbaiki: tulis dengan `pgp_sym_encrypt(%s, %s)` memakai kunci dari env `PII_ENCRYPTION_KEY` (wajib diisi, divalidasi seperti `JWT_SECRET` di FX-01), dan baca dengan `pgp_sym_decrypt`. Hanya modul eligibility dan script migrasi data yang boleh mendekripsi.
   - Buat script migrasi data satu kali yang mengenkripsi baris `other_personal` lama yang masih plaintext.
4. `redaction.py`: tambahkan pola penghapus untuk semua label di atas (termasuk `TTL\s*:`) supaya **tidak ada** sisa tanggal lahir atau gender di `matching_profile`, `full_text_redacted` (FX-10), maupun chunk.
5. Endpoint `reveal-identity` **tidak** mengembalikan DOB atau gender.

### Langkah 3 — Engine eligibility (`src/domain/eligibility.py`, fungsi murni tanpa DB)

```python
def evaluate_rule(rule: EligibilityRule, ident: AdminData) -> RuleResult: ...
def evaluate_all(rules: list[EligibilityRule], ident: AdminData) -> EligibilityResult: ...
```

Aturan:
- **AGE_MAX `n`** (usia ≤ n pada `reference_date`) dan **AGE_MIN `n`** (usia ≥ n):
  - DOB presisi hari: `age = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))`.
  - DOB hanya tahun `y`: rentang usia yang mungkin = `[ref.year - y - 1, ref.year - y]`. Kalau **seluruh** rentang memenuhi, hasilnya ELIGIBLE. Kalau **seluruh** rentang melanggar, NOT_ELIGIBLE. Kalau sebagian, UNKNOWN dengan `reason_code=DOB_YEAR_ONLY_AMBIGUOUS`.
  - DOB tidak ada atau tidak bisa diparse: UNKNOWN dengan `reason_code=DOB_MISSING`.
  - Reason code: `AGE_WITHIN_RANGE`, `AGE_ABOVE_MAX`, `AGE_BELOW_MIN`, `DOB_MISSING`, `DOB_YEAR_ONLY_AMBIGUOUS`.
- **GENDER**: `gender in allowed` → ELIGIBLE (`GENDER_MATCH`). Gender diketahui tapi tidak ada di `allowed` → NOT_ELIGIBLE (`GENDER_MISMATCH`). Gender tidak diketahui → UNKNOWN (`GENDER_MISSING`).
- **Status keseluruhan:** tidak ada rule APPROVED → `NOT_APPLICABLE`. Ada rule NOT_ELIGIBLE → `NOT_ELIGIBLE`. Selain itu, ada UNKNOWN → `UNKNOWN`. Sisanya `ELIGIBLE`.
- Engine **tidak** mengembalikan nilai usia atau gender. Output hanya status dan reason code.

### Langkah 4 — Integrasi ke screening run

1. Saat run dibuat: ambil rule `APPROVED` untuk job (filter tenant!), simpan ke `screening_runs.eligibility_snapshot`.
2. Untuk setiap kandidat: baca `candidate_identities.other_personal`, panggil `evaluate_all(snapshot_rules, ...)`, lalu insert ke `candidate_eligibility`.
3. Langkah ini **terpisah** dari loop scoring. Scorer, verifier, dan explainer tidak menerima objek eligibility sama sekali (tidak ada parameter, tidak ada import).
4. Kalau FX-30 sudah selesai, lakukan di `execute_screening_run`. Kalau belum, di route yang ada sekarang, lalu pindahkan bersama FX-30.
5. Kandidat berstatus `REJECTED`/`NEEDS_REVIEW`/`DUPLICATE` (tidak diskor) tidak perlu dievaluasi eligibility-nya.

### Langkah 5 — Policy linter & JD compiler

1. `policy_linter.py`: buat kategori baru **`ADMIN_DEMOGRAPHIC`** (bukan PROHIBITED, bukan RISKY) untuk pola usia dan gender. Ambil pola dari `docs/spec/reference/prohibited_criteria.yaml` (`age`, `gender`), lalu pindahkan ke key baru `administrative_only` di YAML itu. Flag yang dihasilkan: `ADMIN_ONLY_AGE`, `ADMIN_ONLY_GENDER`.
2. Tetap **PROHIBITED** (tidak bisa dijadikan requirement **maupun** eligibility rule): penampilan, tinggi/berat badan, agama, suku/etnis/ras, warna kulit, status pernikahan/kehamilan, golongan darah, tato/tindik.
3. Tetap **RISKY** (boleh, dengan peringatan): `fresh graduate`, `lulusan tahun X` (proxy usia), PTN/kampus ternama, IPK minimal, domisili.
4. `jd_compiler.compile_job_requirements`:
   - Bullet atau requirement yang mendapat flag `ADMIN_ONLY_*` **dikeluarkan dari `requirements`** dan dimasukkan ke field baru `eligibility_suggestions`:
     ```json
     [{"rule_type": "AGE_MAX", "value": {"years": 27}, "source_text": "Usia maksimal 27 tahun"},
      {"rule_type": "GENDER", "value": {"allowed": ["F"]}, "source_text": "Diutamakan wanita"}]
     ```
     Parse nilai secara deterministik dengan regex (`maks(imal)?\.?\s*(\d+)\s*tahun`, `max(imum)?\s*(\d+)\s*years`, `minimal\s*(\d+)\s*tahun`, `pria|laki-laki|male` → `["M"]`, `wanita|perempuan|female` → `["F"]`). Kalau tidak bisa diparse, `value: null`.
     - **Jangan** kirim usia atau gender ke LLM untuk diparse.
   - Saran ini **tidak** otomatis menjadi rule. HR harus membuatnya lewat endpoint di Langkah 6 dan mengisi justifikasi.
5. `POST /requirements/approve`: kalau ada requirement dengan flag `ADMIN_ONLY_*`, kembalikan **422** dengan `{"code": "MOVE_TO_ELIGIBILITY", "requirement_ids": [...], "message": "Kriteria usia/gender tidak boleh menjadi kriteria penilaian. Pindahkan ke Syarat Administratif."}`.
6. Guard di scorer: requirement ber-flag `PROHIBITED_*` atau `ADMIN_ONLY_*` yang entah bagaimana masuk ke set yang dipakai screening **dilewati**, dan run mendapat flag `NON_SCORABLE_REQUIREMENT_SKIPPED`.

### Langkah 6 — Endpoint

Semua endpoint wajib memakai `get_job_for_tenant` (FX-02) dan semua query difilter `tenant_id`. Semua aksi tulis dicatat di `audit_logs` (`action`: `ELIGIBILITY_RULE_CREATED|APPROVED|REVOKED|DELETED`, metadata: rule_type, value, basis_category, justification).

| Method & path | Role | Perilaku |
|---|---|---|
| `GET /api/v1/jobs/{job_id}/eligibility-rules` | ADMIN, RECRUITER, HIRING_MANAGER | Daftar rule (semua status), urut `created_at`. |
| `POST /api/v1/jobs/{job_id}/eligibility-rules` | ADMIN, RECRUITER | Body `{rule_type, value, basis_category, justification, reference_date}`, menghasilkan rule `DRAFT`, **201**. Validasi Pydantic (lihat di bawah). Rule aktif dengan tipe sama sudah ada → **409**. |
| `PATCH /api/v1/jobs/{job_id}/eligibility-rules/{rule_id}` | ADMIN, RECRUITER | Hanya untuk `DRAFT`. Status lain → **409** `RULE_NOT_EDITABLE`. |
| `DELETE /api/v1/jobs/{job_id}/eligibility-rules/{rule_id}` | ADMIN, RECRUITER | Hanya untuk `DRAFT`. Rule APPROVED harus di-*revoke*, bukan dihapus (jejak audit). |
| `POST /api/v1/jobs/{job_id}/eligibility-rules/{rule_id}/approve` | **ADMIN saja** | `DRAFT` → `APPROVED`. Kalau `settings.ELIGIBILITY_FOUR_EYES=true` (default) dan `approved_by == created_by`, kembalikan **403** `FOUR_EYES_REQUIRED`. |
| `POST /api/v1/jobs/{job_id}/eligibility-rules/{rule_id}/revoke` | **ADMIN saja** | Body `{reason}` (min 10 karakter). `APPROVED` → `REVOKED`. Run yang sudah ada tidak berubah. |
| `GET /api/v1/jobs/{job_id}/screenings/{run_id}/rankings` | (sama seperti sekarang) | Tambahkan `eligibility_status` dan `eligibility_reasons` (list reason_code) per kandidat. Query param `eligibility=all|eligible|eligible_or_unknown`, default **`all`**. Filter hanya menyaring tampilan. **Nilai `rank` tetap rank asli berdasarkan skor** (jangan dinomori ulang). |
| `GET /api/v1/jobs/{job_id}/screenings/{run_id}/candidates/{cv_id}` | (sama seperti sekarang) | Tambahkan blok `eligibility: {overall_status, details:[{rule_type, status, reason_code, message}]}`. **Tanpa** nilai usia atau gender. |
| `GET /api/v1/jobs/{job_id}/screenings/{run_id}/eligibility-summary` | ADMIN, RECRUITER, HIRING_MANAGER | `{counts: {ELIGIBLE, NOT_ELIGIBLE, UNKNOWN, NOT_APPLICABLE}, impact: {top_n: 10, not_eligible_in_top_n: 3, unknown_in_top_n: 1}, rules: [snapshot]}`. `top_n` diambil dari query param (default 10, maksimal 50). |
| `POST /api/v1/requirements/compile-preview` dan `/compile` | (sama) | Response menyertakan `eligibility_suggestions`. |

Validasi body `POST`:
- `AGE_MAX`/`AGE_MIN`: `value.years` integer 15–70. Kalau job sudah punya AGE_MIN dan AGE_MAX, maka `AGE_MIN ≤ AGE_MAX` (422 kalau tidak).
- `GENDER`: `value.allowed` ⊂ {"M","F"}, tidak kosong, **bukan** keduanya (aturan yang mengizinkan semua gender tidak ada artinya).
- `justification`: minimal 30 karakter, dan tidak boleh hanya berisi kalimat generik. Tolak (422 `JUSTIFICATION_TOO_GENERIC`) kalau setelah dinormalisasi isinya sama dengan salah satu dari: "sesuai kebutuhan", "kebijakan perusahaan", "permintaan user", "sesuai kebutuhan perusahaan".
- `reference_date`: wajib, tidak boleh lebih dari 365 hari ke belakang atau ke depan dari hari ini.

Pesan untuk reason code (`message`, Bahasa Indonesia, tanpa angka usia kandidat):
- `AGE_ABOVE_MAX`: "Melebihi batas usia maksimal yang ditetapkan untuk lowongan ini."
- `AGE_BELOW_MIN`: "Di bawah batas usia minimal yang ditetapkan untuk lowongan ini."
- `AGE_WITHIN_RANGE`: "Memenuhi syarat usia."
- `DOB_MISSING`: "Tanggal lahir tidak tercantum di CV. Perlu konfirmasi ke kandidat."
- `DOB_YEAR_ONLY_AMBIGUOUS`: "CV hanya mencantumkan tahun lahir. Perlu konfirmasi ke kandidat."
- `GENDER_MATCH`: "Memenuhi syarat administratif jenis kelamin."
- `GENDER_MISMATCH`: "Tidak memenuhi syarat administratif jenis kelamin."
- `GENDER_MISSING`: "Jenis kelamin tidak tercantum di CV. Perlu konfirmasi ke kandidat."

### Langkah 7 — Perubahan UI (`frontend/src/App.tsx` dan komponen terkait)

1. **Halaman setup job: seksi baru "Syarat Administratif (opsional)"**, terpisah secara visual dari "Kriteria Penilaian". Defaultnya tertutup (collapsed).
   - Banner info: "Syarat ini **tidak memengaruhi skor**. Sistem hanya menandai kandidat, dan keputusan tetap di tangan Anda. Pembatasan usia hanya dibenarkan bila karakteristik jabatan memerlukannya (SE Menaker M/6/HK.04/V/2025). Isi alasan dengan jelas."
   - Form berisi: tipe (Usia maksimal / Usia minimal / Jenis kelamin), nilai, kategori dasar, justifikasi (textarea dengan penghitung karakter, minimal 30), dan tanggal acuan (default: hari ini + 30 hari, bisa diubah).
   - Daftar rule dengan chip status `Draft` / `Disetujui` / `Dicabut`, nama pembuat, dan nama penyetuju. Tombol **Setujui** dan **Cabut** hanya tampil untuk ADMIN. Tombol Setujui dinonaktifkan dengan tooltip kalau ADMIN tersebut adalah pembuat rule (four-eyes).
2. **Saran dari JD:** kalau response compile berisi `eligibility_suggestions`, tampilkan kartu kuning: "Kami menemukan syarat usia/jenis kelamin di JD ('Usia maksimal 27 tahun'). Syarat ini tidak dimasukkan ke kriteria penilaian." Sertakan tombol **"Jadikan Syarat Administratif"** yang membuka form dengan nilai sudah terisi. Justifikasi tetap kosong dan wajib diisi.
3. **Error 422 `MOVE_TO_ELIGIBILITY`** saat approve kriteria: tampilkan pesan dan tombol yang mengarah ke seksi Syarat Administratif.
4. **Tabel ranking:**
   - Kolom baru "Administrasi" dengan badge: `✓ Memenuhi` (hijau), `✕ Tidak memenuhi` (abu-abu, **bukan merah**, supaya tidak terlihat seperti penilaian kualitas), `? Perlu konfirmasi` (kuning), dan `—` kalau tidak ada syarat. Tooltip menampilkan `message` dari reason code.
   - Dropdown filter "Tampilkan: Semua / Memenuhi saja / Memenuhi + perlu konfirmasi", default **Semua**. Kolom # tetap menampilkan rank asli (misalnya #1, #3, #4 kalau #2 tersaring).
   - Banner ringkasan dari `eligibility-summary` kalau `not_eligible_in_top_n > 0`: "3 dari 10 kandidat dengan skor tertinggi tidak memenuhi syarat administratif. Tinjau kembali apakah syarat tersebut memang diperlukan."
   - Kolom skor, band, dan rekomendasi **tidak** dipengaruhi eligibility.
5. **Detail kandidat:** seksi "Syarat Administratif" berisi status dan pesan per rule. **Jangan pernah menampilkan usia, tanggal lahir, atau jenis kelamin**, termasuk di dalam modal reveal identity.
6. Tidak ada tombol atau aksi otomatis untuk menolak berdasarkan eligibility. Aksi "Tidak lanjut" yang sudah ada tetap manual dan wajib diisi alasan.
7. Hapus validasi frontend lama (regex usia/gender di `App.tsx` dari commit `5bbbf90` dan sebelumnya). Validasi sekarang mengikuti flag dari backend.

### Langkah 8 — Pembaruan spec & dokumentasi

1. `docs/spec/02_SCORING_RUBRIC_SPEC.md`: ubah baris ±52. Usia dan gender **dilarang sebagai kriteria penilaian**, tetapi **boleh sebagai Syarat Administratif** dengan aturan di dokumen ini. Tambahkan seksi baru "Syarat Administratif (Eligibility Gate)" yang meringkas invarian I-1 s/d I-5.
2. `docs/spec/reference/prohibited_criteria.yaml`: pisahkan menjadi `prohibited` dan `administrative_only`.
3. `docs/DECISIONS.md`: tambahkan entri keputusan (tanggal, alasan, alternatif yang ditolak, yaitu Opsi A "blokir total" dan "hard-gate otomatis").
4. Tes lama `test_age_gender_and_fresh_grad_allowed` diganti dengan tes-tes di bawah.

### Tes wajib

**Unit — `tests/test_eligibility_engine.py`** (fungsi murni, tanpa DB):
- DOB `1999-03-12`, ref `2026-11-01`, AGE_MAX 27 → usia 27 → ELIGIBLE.
- DOB `1999-03-12`, ref `2026-03-11`, AGE_MAX 26 → usia 26 → ELIGIBLE (sehari sebelum ulang tahun).
- DOB `1998-01-01`, ref `2026-11-01`, AGE_MAX 27 → usia 28 → NOT_ELIGIBLE `AGE_ABOVE_MAX`.
- DOB hanya tahun `1999`, ref `2026-11-01`, AGE_MAX 27 → rentang [26, 27] → ELIGIBLE.
- DOB hanya tahun `1999`, ref `2026-11-01`, AGE_MAX 26 → rentang [26, 27] → UNKNOWN `DOB_YEAR_ONLY_AMBIGUOUS`.
- DOB hanya tahun `1990`, AGE_MAX 27 → rentang [35, 36] → NOT_ELIGIBLE.
- Tidak ada DOB → UNKNOWN `DOB_MISSING` (**bukan** NOT_ELIGIBLE). Ini invarian I-4.
- GENDER allowed `["F"]`: `F` → ELIGIBLE, `M` → NOT_ELIGIBLE, `None` → UNKNOWN.
- Kombinasi: satu rule UNKNOWN dan satu NOT_ELIGIBLE → overall NOT_ELIGIBLE. Satu ELIGIBLE dan satu UNKNOWN → UNKNOWN. Tanpa rule → NOT_APPLICABLE.
- Output engine tidak mengandung key `age`, `dob`, atau `gender` (assert pada `dict` hasil).

**Unit — `tests/test_admin_extraction.py`:**
- `parse_dob` untuk: `"Jakarta, 12 Maret 1999"`, `"12 Mar 1999"`, `"March 12, 1999"`, `"12/03/1999"` (DD/MM), `"1999-03-12"`, `"1999"` (precision YEAR), `"lahir di Bandung"` (None), `"12/03/2030"` (`DOB_IMPLAUSIBLE`).
- Normalisasi gender: `"Laki-laki"`, `"PRIA"`, `"Male"`, `"P"`, `"Wanita"`, `"-"` (None).
- CV berisi `TTL: Jakarta, 12 Maret 1999` dan `Jenis Kelamin: Perempuan`: hasil `matching_profile`, `full_text_redacted`, dan seluruh `profile_chunks` **tidak mengandung** "1999", "Maret 1999", "Perempuan", maupun "TTL". Ini invarian I-2.
- CV dengan nama "Siti Aminah" **tanpa** baris gender menghasilkan gender `None` (tidak menebak dari nama). Ini invarian I-5.

**Integrasi — `tests/test_eligibility_api.py`:**
- CRUD rule: RECRUITER membuat rule → 201 DRAFT. Membuat rule kedua dengan tipe sama → 409. RECRUITER mencoba approve → 403. ADMIN yang membuat rule mencoba approve sendiri → 403 `FOUR_EYES_REQUIRED`. ADMIN lain approve → 200. PATCH rule APPROVED → 409. DELETE rule APPROVED → 409. Revoke → 200.
- Validasi: `years: 10` → 422. GENDER `allowed: ["M","F"]` → 422. Justifikasi 20 karakter → 422. Justifikasi "sesuai kebutuhan perusahaan" → 422 `JUSTIFICATION_TOO_GENERIC`.
- Setiap aksi tulis menghasilkan baris di `audit_logs`.
- Tenant isolation: user tenant A mengakses semua endpoint eligibility milik job tenant B → 404 (tambahkan ke `test_tenant_isolation.py` FX-02).
- `compile` JD "Usia maksimal 27 tahun\n- Diutamakan wanita\n- Menguasai Excel" → `requirements` **tidak** memuat usia/gender, dan `eligibility_suggestions` berisi `AGE_MAX 27` serta `GENDER ["F"]`.
- Approve requirement set yang berisi requirement usia (diinsert manual) → 422 `MOVE_TO_ELIGIBILITY`.
- `lint_text("berpenampilan menarik, beragama X")` tetap menghasilkan PROHIBITED. `lint_text("usia maks 25")` menghasilkan `ADMIN_ONLY_AGE` dan bukan PROHIBITED.

**Integrasi — `tests/test_eligibility_screening.py`** (memakai golden dataset JD-01):
- **Invarian I-1:** jalankan screening tanpa rule, simpan (candidate_id, final_score, band, recommendation, rank). Tambahkan rule AGE_MAX yang APPROVED, jalankan ulang. Kelima nilai harus **identik** untuk semua kandidat.
- `candidate_identities.other_personal` di DB tidak bisa dibaca sebagai JSON tanpa `pgp_sym_decrypt` (terenkripsi).
- `candidate_eligibility` terisi untuk setiap kandidat yang diskor, dan `screening_runs.eligibility_snapshot` berisi rule tersebut.
- Revoke rule setelah run selesai: data run lama (snapshot dan `candidate_eligibility`) tidak berubah.
- `rankings?eligibility=eligible` hanya mengembalikan ELIGIBLE, dan nilai `rank` tetap rank asli (tidak dinomori ulang).
- **Invarian I-3:** setelah run, tidak ada `documents.status` atau `candidates.status` yang berubah karena eligibility.
- **Invarian I-2:** mock gateway LLM dan rekam semua prompt selama run dengan verifier aktif. Tidak ada prompt yang mengandung tanggal lahir atau label gender dari CV uji.
- `eligibility-summary` mengembalikan count dan `not_eligible_in_top_n` yang benar untuk data uji.

**Frontend** (kalau ada test runner; kalau belum, buat checklist manual di laporan):
- Badge dan filter tampil sesuai status. Kolom # menampilkan rank asli setelah difilter. Tidak ada usia atau gender di halaman mana pun.

### Kriteria selesai
- Semua tes di atas lulus, dan invarian I-1 s/d I-5 masing-masing punya minimal satu tes yang namanya menyebut invarian tersebut (`test_invariant_I1_...`).
- `grep -rn "dob\|gender\|other_personal" src/domain/scorer.py src/domain/verifier.py src/domain/explainer.py src/domain/kind_rules.py` → kosong.
- Spec, YAML, dan `DECISIONS.md` sudah diperbarui.

---

## FX-25 — Deteksi duplikat hanya berdasarkan hash file

**Masalah.** Dedup hanya memakai `sha256` byte file. CV yang sama tapi diekspor ulang (PDF baru, atau DOCX dan PDF) dianggap dua kandidat berbeda dan bisa muncul dua kali di ranking.

**Solusi**
1. Setelah ekstraksi, cek di **job yang sama dan tenant yang sama**: apakah ada kandidat lain dengan email yang sama (dinormalisasi lowercase) **atau** nomor telepon yang sama (dinormalisasi ke digit, `0812` menjadi `62812`).
2. Kalau ada, **jangan tolak otomatis**. Beri flag `POSSIBLE_DUPLICATE_OF:<candidate_code>` di dokumen, lalu tampilkan di UI dan ranking.
3. Tambahkan juga fingerprint teks: `sha256` dari `full_text_redacted` yang dinormalisasi (lowercase, whitespace dirapikan). Kalau identik dengan dokumen lain di job yang sama, status `DUPLICATE`.

**Tes wajib**
- Dua file berbeda byte dengan email sama: dokumen kedua mendapat flag `POSSIBLE_DUPLICATE_OF`.
- Dua file dengan teks identik: dokumen kedua berstatus `DUPLICATE`.

---

## FX-26 — Coverage skor rendah tidak ditandai

**Masalah.** `scorer.score`: requirement `UNKNOWN` dikeluarkan dari pembilang **dan** penyebut. Kandidat yang hanya 1 dari 10 requirement-nya bisa dinilai (sisanya UNKNOWN) bisa mendapat skor 100.

**Solusi**
1. Hitung `coverage = den / total_weight`.
2. Tambahkan `coverage` ke `ScoreResult` dan simpan ke `candidate_scores` (kolom baru lewat migrasi).
3. Kalau `coverage < 0.6`: flag `LOW_COVERAGE` dan rekomendasi minimal `MANUAL_CHECK` (jangan SHORTLIST).
4. Tampilkan coverage di UI detail kandidat.
5. `test_scorer_parity` harus tetap lulus. Kasus golden dengan coverage penuh tidak berubah.

**Tes wajib**
- 1 requirement STRONG dan 9 UNKNOWN: `coverage` 0,1, flag `LOW_COVERAGE`, bukan SHORTLIST.

---

# FASE 4 — ARSITEKTUR

## FX-30 — Screening run sinkron di dalam HTTP request

**Masalah.** `POST /jobs/{id}/screenings` memproses semua CV secara berurutan di dalam request, ditambah insert evidence satu per satu. Untuk ratusan CV (dan dengan verifier aktif setelah FX-10), request akan timeout di proxy dan terlihat seperti gagal di UI.

**Solusi**
1. Endpoint membuat baris `screening_runs` dengan status `QUEUED`, memasukkan job `screening_run` ke `jobs_queue` (payload: `run_id`), mengirim `NOTIFY`, lalu mengembalikan **202** `{run_id, status: "QUEUED"}`.
2. Pindahkan seluruh logika scoring ke `src/domain/screening_service.py` → `async def execute_screening_run(run_id)`. Fungsi ini dipanggil oleh worker (`q_type == "screening_run"`). Handler route hanya berisi validasi dan enqueue.
3. Worker meng-update `screening_runs.progress` (kolom jsonb `{done, total}`) setiap 10 CV, lalu status `RUNNING`, kemudian `COMPLETED` atau `FAILED` dengan `finished_at`.
4. Endpoint baru `GET /jobs/{job_id}/screenings/{run_id}` mengembalikan status dan progress.
5. Insert `requirement_states` dan `evidence` memakai `executemany` per kandidat.
6. Frontend: setelah klik "Jalankan screening", polling endpoint status setiap 2 detik dan tampilkan progress bar. Saat selesai, muat ranking.
7. Run bersifat immutable: run yang `COMPLETED` tidak boleh ditulis ulang.

**Tes wajib**
- POST mengembalikan 202 dalam waktu kurang dari 500 ms walaupun ada 50 dokumen READY.
- Setelah worker memproses (panggil `execute_screening_run` langsung di tes), status `COMPLETED` dan ranking tersedia.
- Hasil ranking identik dengan implementasi lama untuk golden dataset JD-01 (uji paritas).

---

## FX-31 — Taksonomi domain di-hardcode

**Masalah.** Setiap role baru butuh perubahan kode (lihat commit "support civil engineering", "business analyst & finance domains"). Daftar istilah tersebar di:
- `kind_rules.py`: `ROLE_FAMILY_PATTERNS`, `CONCEPT_ALIASES`, list istilah di dalam `eval_experience_duration` (`["sipil","civil",...]`, `["hr","human capital",...]`, dll), istilah sertifikasi di `eval_certification`, kata kerja kepemimpinan di `eval_leadership`.
- `jd_compiler.py`: `CONCEPT_RULES`.
- `policy_linter.py`: `PROHIBITED_RULES`, `RISKY_RULES`.

Padahal `docs/spec/reference/*.yaml` (role_families, skills_seed, prohibited_criteria, section_headings, date_formats) sudah ada.

**Solusi**
1. Buat folder `config/taxonomy/` berisi:
   - `role_families.yaml`: per role family berisi `title_patterns`, `domain_terms` (pengganti list di `eval_experience_duration`), `related_families`.
   - `skills.yaml`: per concept berisi `aliases`, `category`, `kind`, `default_importance`, `default_weight`, dan `jd_patterns` (pengganti `CONCEPT_RULES`).
   - `certifications.yaml`, `leadership.yaml`, `prohibited_criteria.yaml`, `stopwords.txt`.
   - Sumber awal: gabungkan isi yang sekarang ada di kode **dan** isi `docs/spec/reference/*.yaml`. **Tidak boleh ada istilah yang hilang** dalam proses migrasi.
2. `src/domain/taxonomy.py`: loader dengan validasi Pydantic, di-cache (`functools.lru_cache`), dan path diambil dari setting `TAXONOMY_DIR`.
3. Semua fungsi `eval_*`, `jd_compiler`, dan `policy_linter` membaca dari `taxonomy`. Setelah tiket ini, **tidak boleh ada lagi list istilah domain literal** di file Python tersebut. Cek dengan grep `"sipil"`, `"payroll"`, `"konsultan"`: hasilnya harus kosong di `src/`.
4. Validasi saat startup: semua regex di YAML harus bisa di-compile. Kalau ada yang gagal, aplikasi tidak start dan pesan errornya menyebut file serta key yang bermasalah.
5. Dokumentasikan di `docs/TAXONOMY.md` cara menambah role baru (contoh lengkap: `data_analyst`).

**Tes wajib**
- Semua tes `test_kind_rules.py` dan golden dataset tetap lulus (paritas sebelum dan sesudah).
- Tes dengan `TAXONOMY_DIR` fixture yang menambahkan role `data_analyst` lewat YAML saja: CV data analyst dinilai STRONG untuk requirement pengalaman data analyst **tanpa perubahan kode**.

---

## FX-32 — Embedding tidak dipakai → hybrid retrieval

**Masalah.** Worker meng-embed setiap chunk dengan `microsoft/harrier-oss-v1-270m` dan menyimpannya di `profile_chunks.embedding` (ada index HNSW dan kolom `fts` tsvector + GIN). Tapi **tidak ada satu pun query** yang memakainya. Biaya CPU terbuang, dan matching tetap murni keyword. Akibatnya, kandidat yang menulis "membangun layanan berbasis REST" tidak cocok dengan "pengalaman API development".

**Solusi.** Tambahkan mode `SCORING_MODE = "rules" | "hybrid"` (default `"rules"`, ubah ke `"hybrid"` **hanya** setelah lulus gate evaluasi FX-33).

1. Embedding requirement: saat approve, embed `description` setiap requirement lalu simpan di `requirements.embedding vector(640)` (lewat migrasi). Cek model card harrier: kalau model memakai prefix instruksi untuk query vs dokumen, terapkan prefix yang benar di kedua sisi.
2. Retrieval per (kandidat, requirement), sebagai fungsi `retrieve_evidence(profile_id, requirement, k=5)`:
   - Vektor: `SELECT ..., 1 - (embedding <=> %s) AS sim FROM profile_chunks WHERE profile_id = %s ORDER BY embedding <=> %s LIMIT 10`.
   - Keyword: `ts_rank(fts, plainto_tsquery('simple', %s))` dengan alias dari taksonomi.
   - Gabungkan dengan Reciprocal Rank Fusion (k=60), lalu ambil top 5.
   - Chunk dipecah per kalimat untuk kutipan (pakai `split_sentences` dari FX-20).
3. Logika state (mode hybrid):
   - Rule menghasilkan STRONG/PARTIAL: pertahankan (verifier opsional seperti sekarang).
   - Rule menghasilkan NOT_DEMONSTRATED, **dan** ada chunk dengan `sim >= SEMANTIC_THRESHOLD` (dikalibrasi, lihat poin 5): state kandidat `PARTIAL` dengan flag `SEMANTIC_MATCH`. Kalau verifier aktif, kirim ke verifier dengan snippet hasil retrieval. Verifier boleh mengonfirmasi PARTIAL atau STRONG (STRONG hanya kalau quote berasal dari chunk `experience`) atau menurunkannya ke NOT_DEMONSTRATED.
   - Kalau verifier tidak aktif, `SEMANTIC_MATCH` maksimal PARTIAL dan tidak pernah STRONG.
   - `EXPERIENCE_DURATION`, `EDUCATION`, dan `CERTIFICATION` **tetap murni rule** (deterministik). Hybrid hanya untuk `SKILL`, `RESPONSIBILITY`, `ACHIEVEMENT`, dan `LEADERSHIP`.
4. Snippet untuk verifier di semua mode diambil dari `retrieve_evidence`, bukan dari `evs[].quote`.
5. Kalibrasi threshold: script `scripts/calibrate_semantic_threshold.py` menjalankan grid 0,50–0,85 (step 0,05) pada golden dataset, lalu pilih threshold dengan F1 tertinggi untuk state ≠ NOT_DEMONSTRATED **tanpa** menambah false positive pada CV kategori I (irrelevant) dan kasus keyword-stuffing di `cvs/edge/`. Simpan hasilnya di `docs/eval/threshold_calibration.md` dan setting `SEMANTIC_THRESHOLD`.
6. Perbaiki komentar usang di `embedding.py` ("MiniLM max tokens is 128"). Cek `max_seq_length` harrier, lalu pastikan chunk yang lebih panjang dipotong atau dipecah secara sengaja, bukan terpotong diam-diam.

**Tes wajib**
- Profil dengan kalimat "Merancang dan membangun layanan berbasis REST untuk aplikasi mobile" dan requirement "Pengalaman API development": mode `rules` menghasilkan NOT_DEMONSTRATED, mode `hybrid` menghasilkan PARTIAL dengan `SEMANTIC_MATCH`.
- Mode `hybrid` tanpa verifier tidak pernah menghasilkan STRONG dari `SEMANTIC_MATCH`.
- CV irrelevant di golden dataset tidak naik band di mode hybrid.

---

## FX-33 — Evaluasi & regression gate

**Masalah.** Golden dataset hanya 15 CV inti sintetis, dibuat oleh pembuat yang sama dengan aturan yang diuji, sehingga rawan overfitting. Selain itu belum ada gate otomatis yang mencegah regresi akurasi.

**Solusi**
1. `make eval` menjalankan end-to-end: proses semua CV golden lewat pipeline lalu export, lalu `evaluate.py`. Hapus path hardcode `/srv/hermes-control/services/cv-extractor/src` di Makefile dan gunakan variabel env `CV_EXTRACTOR_PATH`.
2. Tambahkan metrik ke `evaluate.py`: **NDCG@5**, **precision@shortlist** (berapa persen kandidat SHORTLIST yang berlabel S), dan **akurasi state per requirement** (confusion matrix STRONG/PARTIAL/NOT_DEMONSTRATED).
3. Tambah kasus golden baru dari FX-20 (Java/JavaScript, negasi, SQLite) ke `cvs/edge/` + label.
4. Baseline: simpan metrik hasil run saat ini ke `docs/eval/baseline.json`. Gate: `make eval` gagal kalau NDCG@5 atau precision@shortlist turun lebih dari 0,02 dari baseline.
5. Dukungan dataset CV asli (diisi manual oleh pemilik proyek):
   - Folder `data/private_eval/` (masukkan ke `.gitignore`) dengan format sama seperti golden dataset: `cvs/`, `jd.md`, dan `labels.json` (label per kandidat: S/M/I dan state per requirement).
   - `scripts/eval_private.py` menjalankan evaluasi yang sama pada folder itu. Kalau folder kosong, script hanya mencetak instruksi.
   - Tulis panduan pelabelan di `docs/eval/LABELING_GUIDE.md`: siapa yang melabel (HR), cara melabel state per requirement, dan target minimal 50 CV per role.
6. `SCORING_MODE=hybrid` hanya boleh dijadikan default kalau metrik hybrid lebih baik dari atau sama dengan mode rules di golden dataset **dan** di private eval (kalau tersedia).

**Tes wajib**
- `make eval` lulus di akhir semua fase.
- Ubah satu aturan sengaja supaya rusak (secara lokal, jangan di-commit): gate gagal. Jelaskan percobaan ini di laporan.

---

# FASE 5 — BERSIH-BERSIH

## FX-40 — Versi hardcode, komentar usang, dokumentasi

**Solusi**
1. `screenings.py` `versions_info`: ambil dari konstanta atau setting (`EXTRACTOR_VERSION`, `settings.EMBEDDING_MODEL`, `SCORING_VERSION`, `VERIFIER_PROMPT_VERSION`, `SCORING_MODE`, `SEMANTIC_THRESHOLD`, versi hash taksonomi). Jangan pakai string literal.
2. `processor.py`: `'cv-extractor-1.0.0'` diganti konstanta yang sama.
3. Naikkan `SCORING_VERSION` menjadi `2.0.0` karena perilaku scoring berubah (FX-20, 21, 22, 24, 26, 32).
4. Hapus atau perbarui `scripts/eval_runs/*.json`, `verifier_report.json`, dan `pred_extraction.json` yang dibuat sebelum perbaikan. Data lama itu menyesatkan, terutama hasil verifier yang dibuat saat verifier sebenarnya tidak berjalan. Regenerasi setelah semua fase selesai.
5. Perbarui `docs/DEPLOYMENT_AND_RUNBOOK.md` (Alembic, env baru, metrics token, proxy headers, rotasi secret), `docs/ANSWERS.md`, dan README. Tambahkan `.env.example` yang mencantumkan semua setting baru: `CORS_ALLOWED_ORIGINS`, `METRICS_TOKEN`, `PII_ENCRYPTION_KEY`, `ELIGIBILITY_FOUR_EYES`, `LLM_MODEL_VERIFIER`, `VERIFIER_CONCURRENCY`, `WORKER_CONCURRENCY`, `TAXONOMY_DIR`, `SCORING_MODE`, `SEMANTIC_THRESHOLD`.
6. `ruff` dan `mypy` bersih, tanpa `# type: ignore` atau `noqa` baru tanpa komentar alasan.

---

## Definition of Done (keseluruhan)

- [ ] Semua tiket FX-01 s/d FX-40 berstatus DONE di laporan.
- [ ] `make lint`, `make typecheck`, `make test`, dan `make eval` hijau.
- [ ] Tidak ada secret di kode. Password DB dan JWT secret di server sudah dirotasi.
- [ ] Tes isolasi tenant (FX-02) mencakup **semua** endpoint yang menerima ID.
- [ ] Tidak ada query ke tabel ber-tenant tanpa filter tenant (daftar audit ada di laporan).
- [ ] Verifier benar-benar memanggil LLM ketika `use_verifier=true` (dibuktikan oleh tes dan baris `model_calls` di staging).
- [ ] Invarian Eligibility Gate I-1 s/d I-5 (FX-24) terbukti oleh tes: skor tidak terpengaruh, data demografis tidak bocor ke scoring/LLM, tidak ada penolakan otomatis, data kosong = UNKNOWN, tanpa inferensi.
- [ ] Deploy ke server sudah dilakukan dengan urutan: backup DB → `alembic stamp 0001_baseline` (sekali saja) → `alembic upgrade head` → reprocess profil (FX-10) → restart API dan worker.

---

## Laporan Penyelesaian (diisi agent)

| ID | Status (DONE/PARTIAL/BLOCKED) | Commit | Catatan / penyimpangan dari spec |
|---|---|---|---|
| FX-01 | ✅ DONE | `414db59` | Kredensial DB & JWT dirotasi; fail-fast validator Pydantic; clean test data; test-db target |
| FX-02 | ✅ DONE | `fix(FX-02)` | Filter multi-tenant konsisten (tenant_id = %s) di semua rute & reveal-identity |
| FX-03 | ✅ DONE | `fix(FX-03)` | Requirement sets wajib APPROVED sebelum screening run (HTTP 409 Conflict) |
| FX-04 | ✅ DONE | `fix(FX-04)` | Whitelist CORS eksplisit via settings.CORS_ALLOWED_ORIGINS |
| FX-05 | ✅ DONE | `317f7f2` | Endpoint compile-preview & /metrics dilindungi auth & METRICS_TOKEN kuat |
| FX-06 | ✅ DONE | `d7c9d69` | Rate limiter membaca X-Forwarded-For; dokumentasi uvicorn 2 workers runbook |
| FX-07 | ✅ DONE | `f21f7af` | Penggantian migrate.sh dengan Alembic migrations terkelola & guarded reset |
| FX-10 | ✅ DONE | `988858e` | full_text_redacted pada scoring & pengerasan grounding quote min 5 karakter |
| FX-11 | ✅ DONE | `29ab6a5` | Verifier async, cache DB llm_cache dengan prompt version/model, semaphore concurrency |
| FX-12 | ✅ DONE | `aea52a0` | Sanitasi kontak HR di compiler, pemeriksaan pre-flight berlaku untuk semua task |
| FX-13 | ✅ DONE | `95d768e` | Transaksi DB rapi, deduplikasi candidate_id, offload worker thread, executemany |
| FX-14 | ✅ DONE | `40d4110` | Worker queue retry, reaper running stale, preload embedding model saat startup |
| FX-15 | ✅ DONE | `f12c1e6` | Reusable AsyncClient session di gateway, resolusi key env, parse JSON robust, retry |
| FX-16 | ✅ DONE | `fix(FX-16)` | Metrik riil Prometheus (/metrics) dari query database PostgreSQL |
| FX-20 | ✅ DONE | `fix(FX-20)` | Regex word boundary ketat (\b) & deteksi negasi untuk akurasi skill matcher |
| FX-21 | ✅ DONE | `54343e7` | Tanggal dinamis as_of, hapus fallback hardcode, aturan tahun Juli/Juni (24 bulan) |
| FX-22 | ✅ DONE | `fix(FX-22)` | Normalisasi bobot kategori dua lapis dan re-normalisasi dinamis kategori aktif |
| FX-23 | ✅ DONE | `46d76c3` | Section parser importance (Wajib -> MUST_HAVE, Nilai tambah -> NICE_TO_HAVE) |
| FX-24 | ✅ DONE | `95a98bf`, `9a1c513` | Administrative Eligibility Gate: blind competency scoring, pgp_sym_encrypt, 3-status |
| FX-25 | ✅ DONE | `fix(FX-25)` | Deduplikasi dokumen berbasis fingerprint teks ternormalisasi |
| FX-26 | ✅ DONE | `fix(FX-26)` | Penalti low coverage (< 60% requirement terisi) & coverage tracking |
| FX-30 | ✅ DONE | `502b769` | Asynchronous screening run queue via jobs_queue (HTTP 202) & status endpoint |
| FX-31 | ✅ DONE | `502b769` | Taksonomi domain eksternal YAML (role_families, skills, certifications, leadership) |
| FX-32 | ✅ DONE | `502b769` | Hybrid semantic retrieval (HNSW cosine + FTS plainto_tsquery + RRF k=60) |
| FX-33 | ✅ DONE | `502b769` | Evaluasi regression gate, NDCG@5, Precision@Shortlist, baseline.json, private eval |
| FX-40 | ✅ DONE | `502b769` | Bersih-bersih versi, konstanta rujukan SCORING_VERSION 2.0.0, ruff & mypy 0 error |

**Daftar audit query tenant (FX-02):** _(agent: tulis file:baris → tabel → sudah difilter tenant? ya/tidak)_

**Perubahan label golden dataset (kalau ada):** _(agent: per kasus, alasan)_

**Metrik eval sebelum vs sesudah:** _(NDCG@5, precision@shortlist, akurasi state)_
