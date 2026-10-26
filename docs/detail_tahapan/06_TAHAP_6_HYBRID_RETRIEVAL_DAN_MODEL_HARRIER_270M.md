# 06. Tahap 6: Hybrid Retrieval & Model Harrier-270m

Dokumen ini menjelaskan arsitektur pencarian hibrida (*Hybrid Retrieval*) pada `src/domain/retrieval.py` dan `src/worker/embedding.py`. Modul ini bertugas menjembatani kriteria lowongan kerja dengan ribuan kalimat yang ada di CV pelamar menggunakan kombinasi **Pencarian Vektor Semantik (Microsoft Harrier-270m)** dan **Pencarian Kata Kunci Klasik (Full-Text Search)** dengan pembobotan *Reciprocal Rank Fusion (RRF)*.

---

## 1. Profil Model Microsoft Harrier-270m

Model yang digunakan di server untuk vektorisasi teks adalah **`microsoft/harrier-oss-v1-270m`**:

| Parameter | Spesifikasi | Keterangan & Keunggulan |
| :--- | :--- | :--- |
| **Ukuran Model** | 270 Juta Parameter (~1.1 GB disk) | Sangat ringan, dirancang khusus untuk inferensi CPU tanpa butuh GPU mahal. |
| **Dimensi Vektor** | 640 Dimensi (`vector(640)`) | Kerapatan representasi semantik tinggi, mengungguli model 384d konvensional. |
| **Konteks Input** | Hingga 32.768 Token | Mampu membaca dokumen panjang sekaligus tanpa terpotong di tengah kalimat. |
| **Kecepatan Inferensi** | ~5 milidetik per chunk di CPU | Eksekusi instan di memori server lokal, nol biaya API per panggilan. |
| **Normalisasi** | Cosine Normalization (`L2 = 1.0`) | Nilai kesamaan kosinus (*Cosine Similarity*) langsung sebanding dengan jarak sudut. |

---

## 2. Penyimpanan Vektor di PostgreSQL (`pgvector`)

Vektor hasil encoding disimpan di database PostgreSQL lokal menggunakan ekstensi `pgvector` pada tabel `profile_chunks`:

```sql
CREATE TABLE profile_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    profile_id UUID NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,                -- 'experience', 'project', 'summary', 'education'
    entry_ref TEXT NOT NULL,           -- 'exp_1', 'exp_2', 'proj_1'
    text_redacted TEXT NOT NULL,       -- Teks bersih tersanitasi
    embedding vector(640) NOT NULL     -- Deret 640 angka desimal dari Harrier
);

-- Indeks Akselerasi Pencarian HNSW (Hierarchical Navigable Small World)
CREATE INDEX idx_profile_chunks_embedding_hnsw 
ON profile_chunks 
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

### Jarak Kosinus (*Cosine Distance Operator* `<=>`):
Pencarian kemiripan dihitung dengan operator bawaan PostgreSQL:
$$\text{Cosine Similarity} = 1 - (\text{embedding} \iff \text{target\_vector})$$
Rentang nilai berkisar antara `0.0` (tidak ada kemiripan sama sekali) hingga `1.0` (makna identik 100%).

---

## 3. Mengapa Harus Hybrid Search? (Vektor + Full-Text Search)

Pencarian semantik murni (*Vector Only*) terkadang memiliki kelemahan: model vektor bisa terkecoh oleh dua istilah teknologi yang memiliki kemiripan konteks tata bahasa padahal fungsinya berbeda (contoh: *Java* dan *JavaScript* sering memiliki nilai vektor yang berdekatan).

Sebaliknya, pencarian kata kunci murni (*Keyword Search / BM25*) gagal total jika pelamar menulis dengan sinonim atau struktur kalimat naratif.

### Solusi Sistem Kita: Hybrid Search dengan RRF (k=60)
Sistem menjalankan dua query pencarian secara independen di database:
1. **Pencarian Semantik (Vektor Harrier):** Menemukan kalimat berdasarkan kesamaan konsep dan ide.
2. **Pencarian Kata Kunci (Full-Text Search / FTS):** Menggunakan parser `to_tsquery('simple', ...)` untuk mencocokkan kata kunci eksak dan alias ontologi.

Kedua daftar peringkat digabungkan menggunakan rumus standar industri **Reciprocal Rank Fusion (RRF)**:
$$\text{Skor RRF} = \sum_{m \in \{\text{Vektor}, \text{FTS}\}} \frac{1}{60 + \text{Peringkat}_m}$$

Kalimat bukti yang menempati peringkat atas di kedua metode pencarian akan mendapatkan skor tertinggi dan dipilih sebagai **Top-K Evidence Atoms** untuk diserahkan ke meja Matcher Agent!

---

## 4. Matriks Pembagian Tugas: Harrier-270m vs Ontologi

Untuk memahami pembagian peran di sistem, perhatikan tabel komparasi berikut:

```text
┌────────────────────────────────────────────────────────────────────────┐
│             KOLABORASI DUA KEKUATAN: RADAR VS BUKU HUKUM               │
├──────────────────────────┬─────────────────────────────────────────────┤
│ Model Harrier-270m       │ Kamus Ontologi (Knowledge Graph)            │
│ (Radar Pelacak Kalimat)  │ (Buku Hukum Logika Ilmiah)                  │
├──────────────────────────┼─────────────────────────────────────────────┤
│ Bertugas menemukan       │ Bertugas memvalidasi keabsahan hubungan     │
│ JARUM DALAM JERAMI       │ antara konsep yang ditemukan                │
│ (mencari kalimat bukti   │ (apakah teknologi A secara sah membuktikan  │
│ di antara 300 kalimat CV)│ penguasaan teknologi B).                    │
├──────────────────────────┼─────────────────────────────────────────────┤
│ Bekerja secara           │ Bekerja secara DETERMINISTIK 100%           │
│ PROBABILISTIK SEMANTIK   │ (pasti benar, zero margin of error,         │
│ (skala kemiripan makna   │ aturan mutlak IMPLIES).                     │
│ 0.0 s.d. 1.0).           │                                             │
├──────────────────────────┼─────────────────────────────────────────────┤
│ Kecepatan: 5 milidetik   │ Kecepatan: 0.5 milidetik                    │
│ di HNSW pgvector.        │ via Python Hash & BFS Traversal.            │
└──────────────────────────┴─────────────────────────────────────────────┘
```

---

## 5. Alur Kerja Nyata Saat Menilai Kandidat

Mari kita lihat contoh eksekusinya:
1. **Kriteria Lowongan (JD):** *"Menguasai arsitektur backend asynchronous dan messaging queue."*
2. **Kamus Ontologi:** Mengembangkan kata kunci ke konsep terkait: `["rabbitmq", "kafka", "celery", "pubsub", "event-driven"]`.
3. **Model Harrier-270m:** Mengubah teks kriteria dan konsep tadi menjadi vektor 640d, lalu memindai tabel `profile_chunks` milik kandidat.
4. **Hasil Temuan Harrier:**  
   Menemukan kalimat di halaman 2 CV pelamar:  
   *"Mengimplementasikan message broker menggunakan RabbitMQ untuk pemrosesan background task ribuan email per menit."* (Kemiripan Cosine: **89.4%**).
5. **Penyerahan Bukti:**  
   Atom bukti `E2.B3` ini langsung dipotong dan dikirimkan ke **Gemini Matcher** sebagai bukti sah nomor satu! 🎯
