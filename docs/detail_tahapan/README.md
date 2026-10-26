# Buku Panduan Arsitektur & Tahapan Detail Sistem (Agentic CV Screening v2.1)

Direktori ini berisi dokumentasi teknis mendalam dan modular untuk setiap tahapan proses pada platform **Agentic AI CV Screening & Candidate Ranking Platform (v2.1)**. Setiap topik dipisahkan ke dalam berkas tersendiri agar mudah dipelajari, dipresentasikan, dan dirujuk dalam audit rekayasa perangkat lunak.

---

## 📚 Daftar Berkas Dokumentasi Tahapan

| No | Berkas Dokumentasi | Topik & Cakupan Utama |
| :---: | :--- | :--- |
| **00** | [00_ARSITEKTUR_MASTER_DAN_DUAL_GRAPH.md](./00_ARSITEKTUR_MASTER_DAN_DUAL_GRAPH.md) | Visi arsitektur v2.1, 4 masalah besar ATS lama, pemisahan Graph A (Profiling Dokumen) vs Graph B (Screening Lowongan), dan tumpukan teknologi server. |
| **01** | [01_TAHAP_1_SETUP_LOWONGAN_DAN_JD_COMPILER.md](./01_TAHAP_1_SETUP_LOWONGAN_DAN_JD_COMPILER.md) | Setup lowongan, role templates, RequirementIR 5 Facets, kompilasi Gemini 3.8 Flash JSON mode, scoring 2-lapis, dan modal popup kriteria. |
| **02** | [02_TAHAP_2_INGESTION_SANITASI_DAN_GATEWAY_UU_PDP.md](./02_TAHAP_2_INGESTION_SANITASI_DAN_GATEWAY_UU_PDP.md) | Multi-format parser, sanitasi biner, deteksi teks sembunyi (Visibility Gate), sensor PII nomor HP Indonesia, dan proteksi Gateway UU PDP. |
| **03** | [03_TAHAP_3_GRAPH_A_ATOMISASI_BUKTI_DAN_OFFSETMAP.md](./03_TAHAP_3_GRAPH_A_ATOMISASI_BUKTI_DAN_OFFSETMAP.md) | Konsep Evidence Atoms (`E1.B1`), tier keandalan bukti (T3 vs T0), OffsetMap dwiarah, dan koordinat visual PyMuPDF untuk sorotan PDF di web. |
| **04** | [04_TAHAP_4_TEMPORAL_ENGINE_SWEEP_LINE_CALENDAR_UNION.md](./04_TAHAP_4_TEMPORAL_ENGINE_SWEEP_LINE_CALENDAR_UNION.md) | Mengapa LLM dilarang hitung tanggal, algoritma Sweep-Line weighted calendar union murni Python, penggabungan pekerjaan tumpang tindih, dan buku kas bulanan. |
| **05** | [05_TAHAP_5_PETA_ONTOLOGI_DAN_KNOWLEDGE_GRAPH.md](./05_TAHAP_5_PETA_ONTOLOGI_DAN_KNOWLEDGE_GRAPH.md) | Peta taksonomi YAML (`skills.yaml`, `role_families.yaml`), hukum implikasi asimetris `IMPLIES`, BFS Traversal 0.001s, dan akomodasi peran non-IT. |
| **06** | [06_TAHAP_6_HYBRID_RETRIEVAL_DAN_MODEL_HARRIER_270M.md](./06_TAHAP_6_HYBRID_RETRIEVAL_DAN_MODEL_HARRIER_270M.md) | Profil model Microsoft Harrier-270m CPU lokal, HNSW cosine index di PostgreSQL `pgvector`, Hybrid Search FTS + Vektor via RRF (k=60), dan sinergi Radar vs Buku Hukum. |
| **07** | [07_TAHAP_7_GRAPH_B_MATCH_MAKING_MATCHER_DAN_CLAUDE_CRITIC.md](./07_TAHAP_7_GRAPH_B_MATCH_MAKING_MATCHER_DAN_CLAUDE_CRITIC.md) | Directional Asymmetric Entailment, prinsip R1 Analysis-First, Depth Rubric L0 s.d. L4, status STRONG/PARTIAL/NONE, peran Claude Critic Agent, dan anti-keyword stuffing. |
| **08** | [08_TAHAP_8_SCORER_V2_MATEMATIKA_DAN_SISTEM_BAND_LEADERBOARD.md](./08_TAHAP_8_SCORER_V2_MATEMATIKA_DAN_SISTEM_BAND_LEADERBOARD.md) | Rumus komputasi Scorer v2 Python, renormalisasi kategori, gerbang mutlak MUST_HAVE, sistem Band A/B/C/R, Leaderboard UI, dan penanganan berkas bermasalah. |

---

## 🎯 Panduan Singkat Alur Eksekusi Sistem

```text
       [ Berkas CV Pelamar ]                   [ Teks Lowongan Kerja (JD) ]
                 │                                           │
                 ▼                                           ▼
      [ GRAPH A: PROFILING ]                     [ TAHAP 1: JD COMPILER ]
      • Sanitasi & Visibility Gate               • 5 Facets RequirementIR
      • PII Sensor & OffsetMap Dwiarah           • Card Atas (100%) vs Poin Bawah
      • Pemotongan Evidence Atoms                • Kunci Kriteria Versi Disetujui
      • Sweep-Line Hitung Durasi                             │
      • Harrier-270m Vektor Embedding                        │
                 │                                           │
                 └─────────────────────┬─────────────────────┘
                                       │
                                       ▼
                         [ GRAPH B: EVALUASI & MATCHING ]
                         • Shortcut Ontologi (Kamus IMPLIES 0.001s)
                         • Harrier-270m HNSW + FTS RRF (k=60)
                         • Matcher Agent (Gemini 3.8 Flash, L0-L4)
                         • Critic Agent (Claude Sonnet 5.5, Audit E1-E6)
                         • Scorer v2 Deterministik Murni Python
                                       │
                                       ▼
                         [ HASIL RANKING & LEADERBOARD ]
                         • Band A (Shortlist), Band B, Band C, Band R
                         • Sorotan Bukti Nyata di Pratinjau Dokumen
```
