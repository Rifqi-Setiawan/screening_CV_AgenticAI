# 07. Tahap 7: Graph B — Match Making (Matcher & Claude Critic)

Dokumen ini menjelaskan proses inti penjurian kualifikasi pelamar (*Match Making*) pada **Graph B**. Tahap ini mempertemukan kriteria lowongan (*RequirementIR*) dengan bukti nyata kandidat (*Evidence Atoms*) menggunakan arsitektur multi-model: **Matcher Agent (Gemini 3.8 Flash)** sebagai evaluator utama dan **Critic Agent (Claude Sonnet 5.5)** sebagai jaksa penuntut audit adversarial.

---

## 1. Penalaran Arah Asimetris (*Directional Asymmetric Entailment*)

Sistem tidak menilai kecocokan secara simetris, melainkan menguji hipotesis searah:
> **Pertanyaan Logika:** *"Apakah atom-atom bukti yang dimiliki kandidat secara logis membuktikan bahwa kandidat mampu memenuhi pernyataan syarat lowongan?"*

### Prinsip R1: Penalaran Terlebih Dahulu (*Analysis-First Serialization*)
Di skema output Pydantic (`src/agents/schemas/matcher.py`), urutan field diatur secara ketat:
```python
class FacetEvaluationResult(BaseModel):
    facet_key: str
    analysis: str        # Token reasoning HARUS dicetak lebih dulu oleh LLM
    depth_level: DepthLevel  # L0, L1, L2, L3, L4
    verdict: EntailmentVerdict  # ENTAILED, PARTIALLY_ENTAILED, NOT_ENTAILED
    cited_atom_ids: list[str]   # Wajib mengutip ID atom asli (misal: E1.B1)
```
Prinsip **R1 Analysis-First** memaksa model AI untuk menjabarkan argumen bukti dan pemikiran logisnya terlebih dahulu sebelum mengeluarkan kata kesimpulan (*verdict*). Hal ini secara terbukti menghapus halusinasi putusan prematur.

---

## 2. Rubrik Level Kedalaman Kompetensi (*Depth Rubric L0 s.d. L4*)

Untuk membedakan pelamar pemula yang sekadar tahu teori vs insinyur senior yang berpengalaman menangani skala besar, Matcher Agent mengevaluasi ke dalam 5 tingkatan kedalaman penguasaan:

| Level | Kategori Kompetensi | Karakteristik Bukti di CV | Dampak Skor |
| :--- | :--- | :--- | :--- |
| **L0** | **Unproven** | Hanya menyebutkan nama teknologi di daftar skill/ringkasan bio tanpa ada konteks pernah dipakai di proyek/pekerjaan nyata. | Faktor: `0.0` (Poin = 0) |
| **L1** | **Basic Exposure** | Menggunakan teknologi dalam konteks tugas kuliah, skripsi, sertifikasi pemula, atau proyek hobi pribadi. | Faktor: `0.4` (Poin Rendah) |
| **L2** | **Independent Practitioner** | Menjalankan tugas operasional standar di dunia kerja nyata (magang, kerja penuh waktu, menyelesaikan tiket fitur). | Faktor: `0.7` (Poin Standar) |
| **L3** | **Advanced Specialist** | Mampu melakukan optimasi query, perancangan arsitektur scalable, pemecahan insiden kritis, dan menyertakan metrik bisnis nyata. | Faktor: `0.9` (Poin Tinggi) |
| **L4** | **High Mastery / Leadership** | Memimpin migrasi teknologi skala perusahaan (*enterprise migration*), bertindak sebagai tech lead, arsitek sistem, atau pemilik keputusan teknis. | Faktor: `1.0` (Poin Sempurna) |

---

## 3. Klasifikasi Status Kriteria Akhir

Dari kombinasi putusan *entailment* dan level kedalaman, sistem menghasilkan status pemenuhan untuk setiap kriteria:

1. **`STRONG` (Terbukti Kuat):**
   - Bukti berasal dari pekerjaan nyata (Tier 3: `EXP_BULLET` atau `PROJECT_BULLET`).
   - Berada pada level kompetensi **L2, L3, atau L4**.
   - Menyumbang **100% nilai bobot kriteria**.
2. **`PARTIAL` (Terbukti Sebagian):**
   - Kandidat hanya memiliki bukti di level **L1** (akademis/hobi), atau bukti jam terbangnya baru memenuhi sebagian dari syarat minimal yang diminta.
   - Menyumbang **50% nilai bobot kriteria**.
3. **`NONE` (Tidak Terbukti):**
   - Kandidat berada di level **L0** atau tidak ditemukan bukti yang relevan sama sekali.
   - Menyumbang **0% nilai bobot kriteria**.

---

## 4. Peran Claude Critic Agent: Jaksa Penuntut Adversarial

Sistem tidak mempercayai penilaian satu model AI secara buta. Modul `src/agents/critic.py` menggunakan **Anthropic Claude Sonnet 5.5** (`cc/claude-sonnet-5-5`) yang berperan sebagai peninjau kritis independen.

### Pemicu Pemanggilan Critic (Triggers E1 s.d. E6):
Critic Agent tidak dipanggil untuk semua kandidat (demi efisiensi biaya), melainkan dipicu secara otomatis jika terdeteksi kondisi anomali:
- **E1 (Borderline Score):** Skor kandidat berada di batas kritis kelulusan (skor 78–82).
- **E2 (High T0 Ratio):** Lebih dari 40% klaim keahlian kandidat hanya bersumber dari daftar skill tanpa riwayat proyek.
- **E3 (Contested High-Depth):** Kandidat mengklaim level L4 (*Leadership/Architect*) padahal total jam terbang kerjanya masih di bawah 2 tahun.
- **E4 (OCR Bleed / Noise):** Dokumen mengandung indikasi teks miring, tabel pecah, atau artefak OCR rusak.
- **E5 (Hidden Text Detection):** Ditemukan teks tersembunyi berukuran font kecil atau warna mencurigakan.
- **E6 (Agent Disagreement):** Adanya pertentangan antara hasil pencarian ontologi dan hasil penilaian semantik.

```text
               [ Hasil Awal Matcher Agent ]
                            │
                            ▼
           Apakah Memenuhi Pemicu E1 - E6?
           ├── Tidak ──► [ Teruskan ke Scorer v2 ]
           └── Ya
                │
                ▼
      ┌────────────────────────────────────────┐
      │  CLAUDE CRITIC AGENT (Sonnet 5.5)     │
      │  "Periksa ulang bukti atom E2.B1!      │
      │   Kandidat mengklaim Microservices,    │
      │   tetapi apakah ada bukti riilnya?"    │
      └─────────────────┬──────────────────────┘
                        │
             Audit Menemukan Bukti Lemah?
             ├── Ya ──► [ DOWNGRADE ]: Turunkan STRONG ➔ PARTIAL / L2 ➔ L0
             └── Tidak ──► [ CONFIRMED ]: Pertahankan Nilai Asli
                        │
                        ▼
           [ Teruskan ke Scorer v2 ]
```

---

## 5. Pertahanan Anti-Keyword Stuffing

Salah satu keunggulan terbesar sistem ini adalah kekebalannya terhadap trik pelamar yang menaruh ratusan kata kunci di resume:
- Seluruh teks yang berada di luar riwayat pengalaman kerja (seperti *Skills Summary*, *List of Technologies*) diklasifikasikan sebagai atom jenis `T0` (`SKILL_LIST_ITEM`).
- Sistem menerapkan aturan baku:  
  **`T0_CAPPED_AT_PARTIAL` & `T0_DEPTH_FLOOR_ENFORCED (L0)`**
- Jika pelamar menulis *"Menguasai Docker, Kubernetes, Kafka, Redis, Golang"* di daftar keahlian, tetapi di riwayat kerjanya tidak pernah ada satu kalimat pun yang menceritakan proyek Kafka/Kubernetes:
  - Matcher atau Critic otomatis mengunci nilainya di level **`L0`**.
  - Nilai kriteria tersebut **hanya bernilai 0 atau maksimal 50%**, dan predikatnya **tidak akan pernah bisa `STRONG`**.

Dengan mekanisme pertahanan ini, hanya kandidat yang **benar-benar memiliki rekam jejak kerja nyatalah** yang bisa menduduki puncak peringkat Leaderboard! 🏆
