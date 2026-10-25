# CHECKPOINT PROJECT: cv-screening-agentic (ON HOLD)
**Tanggal Freeze:** 25 Oktober 2026  
**Status:** ON HOLD (Semua state, history, dan roadmap tersimpan aman)  
**Git HEAD:** `bd4103e` (branch `main`)  
**Workspace:** `/srv/hermes-control/services/cv-screening-agentic`  
**Database:** PostgreSQL `cv_screening_agentic` dan `cv_screening_agentic_test` (pgvector 0.8.7)  

---

## 1. Status Task Kanban yang Telah Selesai (100% Verified by Sentinel)
Semua 7 modul inti Blueprint v2.1 telah selesai diimplementasikan oleh `@forge` dan disetujui secara independen (PASS) oleh `@sentinel`:

| Task ID | Task Title | Implementer | Verifier | Status | Deliverables Utama |
|---|---|---|---|---|---|
| `t_a96e7036` | `forge-temporalengine` | `@forge` | `@sentinel` | **DONE** | Sweep-line weighted calendar union & month ledger (`src/domain/temporal.py`). Mengatasi durasi terfragmentasi & overlap. 20 tests pass. |
| `t_5e6a84de` | `forge-atomizer` | `@forge` | `@sentinel` | **DONE** | N0b Visibility Gate (<4pt, white font, bounds), OffsetMap dwiarah, Evidence Atomizer (`src/domain/atoms.py`). 19 tests pass. |
| `t_922751e1` | `forge-profiler` | `@forge` | `@sentinel` | **DONE** | Capability Ontology & Profiler Agent (`src/domain/ontology/`, `src/worker/profiler.py`). Alokasi domain tanpa label kaku title. 49 tests pass. |
| `t_4461e5a4` | `forge-requirement-ir` | `@forge` | `@sentinel` | **DONE** | RequirementIR & 5 Facets Decomposition (`src/domain/requirements/`). Skema DB migrasi 0012. 59 tests pass. |
| `t_dbcae10c` | `forge-matcher` | `@forge` | `@sentinel` | **DONE** | Matcher Agent (Directional Entailment dg R1 analysis-first), S3 Retriever, S4 Ontology Shortcut, S7 Aggregator. Memecahkan Title Bias. 8 tests pass. |
| `t_f22d4f5c` | `forge-critic` | `@forge` | `@sentinel` | **DONE** | Critic Agent multi-model adversarial (`cc/claude-sonnet-5-5`), pemicu eskalasi E1-E6, Scorer v2 anti-stuffing (T0 capped at PARTIAL). 15 tests pass. |
| `t_8e4ebcfb` | `forge-orchestrator` | `@forge` | `@sentinel` | **DONE** | End-to-End Orchestrator Graph A (`profiling_pipeline.py`) & Graph B (`screening_pipeline.py`). 4 E2E integration tests pass. |

**Total Suite Testing:** **86/86 tests PASS** (2.43s), Ruff linting 100% clean, Mypy typecheck 100% clean.

---

## 2. Masalah Krusial Blueprint v2.1 yang Terbukti Tuntas di Pengujian
1. **Problem 1 (Title Bias / Asymmetric Entailment):**
   - Kasus kandidat berjabatan *"Software Engineer"* yang mengerjakan proyek React/Redux melamar posisi *"Frontend Developer"*.
   - **Hasil:** Graph A memprofilkan pengalaman ke domain frontend (PRIMARY) -> Graph B mencocokkan bukti ke facet frontend -> Dinilai **STRONG** & Band A (Lolos!).
2. **Problem 2 (Fragmented Duration Accumulation):**
   - Kasus riwayat pengalaman terpecah: 18 bulan Backend + 6 bulan Magang Backend (@0.5 = 3 bulan) + 12 bulan Backend.
   - **Hasil:** Akumulasi kalender union tepat 33 bulan tanpa salah hitung atau dobel klaim. Dievaluasi presisi terhadap syarat 36 bulan (status PARTIAL, bukan false positive/negative).
3. **Problem 3 (Anti-Keyword Stuffing & Hidden Text Defense):**
   - Kasus CV manipulatif dengan teks tersembunyi (font 2.5pt warna putih) dan penumpukan daftar skill tanpa riwayat proyek.
   - **Hasil:** *Visibility Gate* langsung membuang teks tersembunyi, pemicu eskalasi E6 dan E4 memanggil Critic Agent (`Claude Sonnet 5.5`), bukti T0 dikunci maksimal PARTIAL, dan status kandidat diturunkan ke `MANUAL_CHECK`.

---

## 3. Task Kedepannya (Roadmap Saat Diaktifkan Kembali)
Ketika user siap melanjutkan proyek ini, langkah berikutnya yang tinggal dikerjakan adalah:

1. **Task API Wiring (`prism` / `forge`):**
   - Menghubungkan endpoint FastAPI di `src/api/routes/screenings.py` untuk memanggil `run_screening_pipeline` secara asynchronous via worker/queue.
2. **Task UI Dashboard (`prism`):**
   - Menampilkan transparansi *Evidence Atoms* ber-ID unik (`E1.B1`, dll), rincian penilaian *facets*, durasi kalender, dan bendera audit Critic di web frontend.
3. **Task Golden Dataset Benchmark (`sentinel`):**
   - Menjalankan evaluasi pada dataset evaluasi CV nyata untuk mengukur konsistensi ranking dan benchmark terhadap HR human recruiter.
4. **Task GitHub Publication (`relay`):**
   - Menyiapkan repo publik di GitHub `Rifqi-Setiawan/cv-screening-agentic` tanpa jejak internal, commit rapi, dan dokumentasi portfolio.
