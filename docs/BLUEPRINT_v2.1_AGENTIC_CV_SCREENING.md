================================================================================
 BLUEPRINT v2.1 — AGENTIC CV SCREENING & RANKING (BERBASIS RISET)
 Proyek: github.com/Rifqi-Setiawan/ai-cv-screening-ranking -> v2
 Disusun: 25 Oktober 2026
================================================================================

STRUKTUR DOKUMEN
  BAGIAN A  Landasan riset (apa kata literatur, per pilar desain)
  BAGIAN B  Perbandingan riset vs blueprint v2.0 (dikonfirmasi / direvisi /
            ditambah / sengaja tidak diadopsi)
  BAGIAN C  Blueprint v2.1 final (versi lengkap, menggantikan v2.0)
  BAGIAN D  Daftar referensi (nomor [n] dipakai di seluruh dokumen)

Catatan kejujuran:
  - Tidak ada paper yang membahas persis "akumulasi durasi per domain lintas
    pekerjaan terfragmentasi". Solusi temporal di sini adalah rekayasa
    (interval algebra) yang DIBENARKAN oleh bukti bahwa LLM lemah di
    aritmetika durasi [7], bukan diambil dari satu paper.
  - Beberapa studi bias berasal dari vendor HR yang menguji model mereka
    sendiri [4]; konflik kepentingan dicatat di tempatnya.
  - Ringkasan regulasi bukan nasihat hukum. Verifikasi ke teks resmi /
    konsultan hukum sebelum go-live.

################################################################################
 BAGIAN A — LANDASAN RISET
################################################################################

A1. "Workflow" vs "Agent": kapan otonomi layak dibayar
--------------------------------------------------------------------------------
[1] Anthropic membedakan WORKFLOW (LLM & tool diorkestrasi lewat jalur kode
    yang sudah ditentukan) dan AGENT (LLM menentukan sendiri proses & tool).
    Rekomendasinya: mulai dari solusi paling sederhana; agen menukar latensi
    & biaya demi performa pada masalah terbuka yang langkahnya tak bisa
    diprediksi; workflow lebih dapat diprediksi untuk tugas terdefinisi.
    Pola yang relevan: prompt chaining dengan cek terprogram antar langkah,
    routing ke model murah/mahal, parallelization (sectioning & voting),
    evaluator-optimizer. Framework boleh, tapi pahami kode di bawahnya dan
    kurangi abstraksi saat ke produksi.
    => Screening CV adalah tugas TERDEFINISI. Implikasi: DAG workflow dengan
       node LLM terbatas, bukan agen otonom.

[2] Lo et al. (CVPR Workshop 2025) — satu-satunya framework "multi-agent
    resume screening" yang cukup dikenal: 4 agen CrewAI (extractor,
    evaluator ber-RAG, summarizer dengan persona CEO/CTO/HR, formatter).
    Hasil: RAG menurunkan MAE terhadap skor HR (DeepSeek-V3 1.08 -> 0.90;
    GPT-4o 1.26 -> 1.05). Keterbatasan yang mereka akui: 105 CV, mayoritas
    HR, mengukur kesepakatan dengan skor HR (bukan outcome rekrutmen), bobot
    kategori sama untuk semua role, LLM mengeluarkan skor angka langsung,
    bias & privasi belum dievaluasi, penjelasan tidak dievaluasi kuantitatif.
    => Validasi: ekstraksi terstruktur + RAG kriteria membantu.
       Peringatan: desain "LLM memberi skor angka + debat persona" belum
       teruji untuk keadilan & stabilitas; jangan ditiru.

A2. Bias LLM dalam penyaringan CV
--------------------------------------------------------------------------------
[3] Wilson & Caliskan (AIES 2024): retrieval berbasis embedding (3 model
    berbasis Mistral-7B, 554 CV, 571 JD, 120 nama). Nama ber-asosiasi kulit
    putih disukai di 85.1% uji; nama laki-laki di 51.9%; laki-laki kulit
    hitam paling dirugikan. CV pendek (sedikit konteks) memperparah bias.
    => Embedding/cosine retrieval (komponen v1 Anda) BUKAN netral. Redaksi
       nama wajib, dan retrieval tidak boleh menjadi penentu skor.

[4] Eightfold (2025, 2507.02087): ~10.000 pasangan kandidat-pekerjaan.
    Semua LLM umum yang diuji (GPT-4o/4.1, o3/o4-mini, Gemini 2.5 Flash,
    Claude 3.5, Llama, DeepSeek R1) jatuh di bawah ambang four-fifths (0.8)
    untuk kelompok interseksional (impact ratio 0.60–0.77); model khusus
    yang disupervisi lebih akurat (ROC AUC 0.85 vs 0.77) dan lebih adil.
    Catatan: model pembanding milik penulis sendiri (konflik kepentingan).
    => LLM sebagai "pemberi skor holistik" berisiko adverse impact.
       Batasi LLM pada keputusan sempit yang bisa diaudit, dan pantau
       impact ratio di produksi.

[5] Rozado (2025, 2505.17049): 22 LLM, 70 profesi, perbandingan berpasangan.
    Bias gender konsisten DAN bias posisi kuat (kandidat yang disebut
    pertama lebih sering dipilih). Penilaian terisolasi (pointwise) hampir
    tidak menunjukkan efek gender.
    => Hindari perbandingan berpasangan kandidat tanpa kontrol urutan.
       Penilaian pointwise berbasis bukti lebih aman.

[6] Xu, Li, Jiang (2025, 2509.00462) — "AI self-preferencing": LLM penyaring
    lebih memilih ringkasan CV yang ditulis oleh LLM itu sendiri (67–82%
    bias untuk model besar setelah kontrol kualitas); kandidat yang memakai
    LLM yang sama dengan evaluator 23–60% lebih mungkin di-shortlist.
    Mitigasi system prompt + majority voting antarmodel menurunkan bias
    17–63% (relatif).
    => Risiko BARU yang belum ada di blueprint v2.0: gaya tulisan ber-AI
       bisa mengangkat skor. Bagian CV yang berupa klaim gaya-bahasa
       (summary/self-evaluation) tidak boleh menjadi bukti kompetensi.

A3. LLM sebagai penilai (LLM-as-a-judge)
--------------------------------------------------------------------------------
[8] Zheng et al. (NeurIPS 2023): bias posisi (Claude-v1 hanya konsisten
    23.8% saat urutan ditukar), verbosity bias (jawaban yang dibuat panjang
    dengan pengulangan lolos 91.3% pada beberapa model), self-enhancement,
    dan lemah menilai matematika (GPT-4 salah 14/20; turun ke 3/20 dengan
    reference-guided). Mitigasi: tukar posisi, few-shot, CoT, referensi.
    => Verbosity bias = keyword stuffing versi LLM. Perlu aturan kode yang
       membatasi bobot bukti "daftar panjang".

[9] CheckEval (EMNLP 2025): mengganti skala Likert dengan checklist
    pertanyaan biner per sub-dimensi menaikkan kesepakatan antar-evaluator
    (Krippendorff α rata-rata 0.09 -> 0.48) dan korelasi dengan manusia.
    => Mendukung kuat dekomposisi requirement menjadi FACET biner/ternary,
       bukan skor holistik.

[10] PRP (Qin et al., NAACL Findings 2024): ranking berpasangan dengan
     dua urutan; preferensi hanya dihitung bila konsisten di kedua urutan,
     sisanya seri. All-pairs paling robust, O(N²).
     => Bila ingin "penyempurnaan ranking" di puncak, satu-satunya cara
        yang bias-posisinya terkendali adalah dual-order + seri bila
        tidak konsisten.

A4. Ekstraksi informasi CV & grounding
--------------------------------------------------------------------------------
[11] Alibaba (2510.09722): parsing sadar-layout + LLM mengembalikan RANGE
     NOMOR BARIS (pointer), bukan menulis ulang teks -> hemat token dan
     mengurangi parafrase/halusinasi. Pasca-proses membuang entitas yang
     field kuncinya tidak ditemukan di sumber. Qwen3-0.6B hasil fine-tune
     mencapai F1 0.964 pada CV nyata, 1.54 s/CV, 240–300 CV/menit.
     Evaluasi pakai Hungarian alignment antar entitas + pencocokan
     per-field (tanggal di level tahun-bulan).
     => Validasi langsung prinsip "atom ID / pointer" di v2.0.
        Juga bukti bahwa model kecil lokal cukup untuk ekstraksi.

[12] Google LangExtract (2025): setiap ekstraksi dipetakan ke offset
     karakter persis di teks sumber; output terkontrol schema; few-shot;
     multi-pass untuk dokumen panjang.
     => Praktik industri yang sama: grounding = offset, bukan kutipan bebas.

[13] JobHop v2 (2607.11715): ekstraksi lintasan karier 440 ribu CV dengan
     LLM lokal (privasi), JSON ketat + retry (12.6% CV perlu retry, 100%
     akhirnya valid). Aturan tanggal: tolak durasi > 40 tahun, tukar
     start/end yang terbalik tipis, gabungkan entri bersebelahan yang sama,
     pecahan dari layout multi-kolom dirapikan. Label "unknown" (6.9%)
     dipilih demi presisi. Akurasi model terbaik hanya 1.1–2.7 poin di
     bawah plafon antar-anotator.
     => Mengonfirmasi normalizer tanggal deterministik + UNKNOWN eksplisit.
        Menambah: dedup entri ganda dari layout multi-kolom.

[14] Clavié & Soulié (2023, 2307.03539): pemetaan skill ke ESCO (13.890
     skill) dengan pola "retrieve kandidat via embedding -> LLM rerank
     memilih dari daftar pendek" menaikkan RP@10 dari ~39 ke 61–69.
     => KOREKSI untuk v2.0: ontologi tidak bisa dimasukkan utuh sebagai
        enum di prompt. Gunakan retrieve-then-select per atom.

[15] JobMatchAI (ACL 2026 demo, 2603.14558): BM25 + kNN + traversal graph
     skill (relasi RELATED_TO multi-hop, mis. Kubernetes -> "container
     orchestration") digabung RRF; skor deterministik white-box; LLM hanya
     menarasikan faktor yang sudah dihitung sehingga tidak bisa
     menggelembungkan skor. Audit 95 penjelasan: tidak ada klaim tanpa
     dukungan. Kelemahan: recall@100 turun karena fusi; belum ada audit bias.
     => Validasi ontologi graph + "LLM menjelaskan, kode menilai".

[16] LANTERN / LinkedIn (2510.05490): job-person fit (Low/Med/High +
     penjelasan). Teacher LLM dengan prompt multi-langkah terdekomposisi,
     output teacher disaring manusia, lalu didistilasi ke model kecil;
     encoder 0.4B untuk jalur klasifikasi bervolume tinggi, decoder kecil
     untuk penjelasan. Online: +0.24% apply rate. Pelajaran: pecah prompt
     panjang, temperature 0 untuk label, kompres sisi JD.
     => Jalur produksi jangka menengah: distilasi node LLM ke model lokal.

A5. Reasoning, format terstruktur, stabilitas
--------------------------------------------------------------------------------
[7]  Test of Time (ICLR 2025): pada kategori Duration (selisih dua tanggal)
     akurasi LLM frontier saat itu hanya 13.5–16%; banyak error meleset satu
     hari dan salah menghitung bulan mundur.
     => Bukti terkuat untuk prinsip "LLM tidak boleh menghitung durasi".

[17] Tam et al. "Let Me Speak Freely?" (EMNLP Industry 2024): JSON schema
     ketat dapat menjatuhkan akurasi tugas reasoning secara drastis,
     terutama bila field jawaban diletakkan sebelum field alasan. Untuk
     tugas KLASIFIKASI, format terstruktur justru membantu. Mitigasi:
     field reasoning sebelum jawaban, atau dua langkah (bahasa natural ->
     konversi format).
     => KOREKSI untuk v2.0: Matcher/Critic perlu field analisis singkat
        SEBELUM verdict.

[18] Atil et al. (2408.04667): temperature 0 + seed tetap pun tidak
     deterministik di API ter-hosting; variasi akurasi antar-run hingga 15%;
     output lebih panjang = kurang stabil; error stabilitas bersifat
     majemuk (4 komponen @95% ≈ 81% end-to-end). Rekomendasi: laporkan
     rentang min–max, regression test bertoleransi, batasi panjang output.
     => KOREKSI untuk v2.0: determinisme bersumber dari CACHE + output
        kategorikal pendek, bukan dari temperature 0. Rantai keputusan
        LLM per state harus sependek mungkin.

[19] Liu et al. "Lost in the Middle" (TACL 2024): akurasi turun saat
     informasi relevan berada di tengah konteks panjang (kurva U; GPT-3.5
     75.8% di posisi awal vs 53.8% di tengah, 20 dokumen).
     => KOREKSI untuk v2.0: batch "semua facet dalam satu call" perlu
        dibatasi ukurannya dan atom diurutkan.

A6. Keamanan: prompt injection di CV
--------------------------------------------------------------------------------
[20] Zhang et al. (2605.28999): 196.682 CV nyata (hireEZ). ~1% CV memuat
     injeksi tersembunyi (teks warna latar, font 1pt, di luar halaman,
     lapisan). 90–96% berupa DATA injection (paling banyak daftar skill
     tersembunyi), hanya 4–10% instruksi ke LLM. Detektor generik
     (PromptGuard dll.) recall-nya rendah. Rekomendasi: validasi lintas-
     modal (teks hasil ekstraksi vs tampilan yang terlihat manusia).
     => KOREKSI untuk v2.0: ancaman utama adalah keyword stuffing
        TERSEMBUNYI, bukan "ignore previous instructions". Pertahanan utama:
        hanya teks yang terlihat yang boleh menjadi atom bukti.

A7. Regulasi yang membentuk arsitektur
--------------------------------------------------------------------------------
[21] UU No. 27/2022 (PDP), Pasal 10 ayat (1): subjek data berhak mengajukan
     keberatan atas keputusan yang HANYA didasarkan pemrosesan otomatis,
     termasuk profiling, yang berakibat hukum/berdampak signifikan.
     UU PDP juga mewajibkan penilaian dampak (DPIA) untuk pemrosesan
     berisiko tinggi (menurut pemahaman saya Pasal 34, yang menyebut
     keputusan otomatis berdampak signifikan; masa transisi 2 tahun sejak
     17 Okt 2022 — VERIFIKASI ke teks resmi).
[22] EU AI Act: sistem AI untuk rekrutmen/penyaringan/ranking kandidat
     termasuk high-risk (Annex III). Setelah Digital Omnibus (disetujui
     Parlemen 16 Jun 2026, Dewan 29 Jun 2026) kewajiban high-risk
     stand-alone berlaku 2 Des 2027; kewajiban transparansi Pasal 50
     berlaku 2 Agt 2026. Relevan bila ada klien/kandidat di UE.
[23] NYC Local Law 144: audit bias independen maksimal 1 tahun sebelum
     dipakai, hasil ringkas dipublikasikan (selection rate & impact ratio
     per ras/etnis, jenis kelamin, interseksional), notifikasi kandidat
     ≥10 hari sebelumnya termasuk kualifikasi yang dinilai dan opsi alternatif.
     => Implikasi desain lintas yurisdiksi: (1) sistem MEREKOMENDASIKAN,
        manusia MEMUTUSKAN; tidak ada auto-reject; (2) penjelasan per
        kandidat yang bisa diekspor; (3) log lengkap; (4) kemampuan
        menghitung impact ratio; (5) daftar kualifikasi yang dinilai bisa
        dipublikasikan (RequirementIR yang di-approve = artefak ini).

################################################################################
 BAGIAN B — PERBANDINGAN RISET vs BLUEPRINT v2.0
################################################################################

B1. DIKONFIRMASI (dipertahankan, kini dengan landasan)
  [v2.0 P3] DAG statis + node LLM terbatas, bukan agen otonom ......... [1]
  [v2.0 P1] LLM melabeli, kode menghitung (durasi, skor, rank) .. [7][15][4]
  [v2.0 P2] Grounding lewat pointer/atom ID + offset, bukan kutipan bebas
            ............................................... [11][12][15]
  [v2.0 §4] Dekomposisi requirement -> facet ......................... [9]
  [v2.0 §4] Ontologi skill berarah + traversal multi-hop ......... [15][14]
  [v2.0 §3] Ekstraksi terstruktur sebelum evaluasi; kriteria via data
            yang bisa diubah recruiter (bukan fine-tune) ........... [2][16]
  [v2.0 §5] Normalisasi tanggal deterministik, UNKNOWN eksplisit,
            tolak anomali ............................................ [13]
  [v2.0 §7] Redaksi identitas sebelum embedding & LLM ............. [3][4]
  [v2.0 §9] Explainer hanya menarasikan hasil yang sudah dihitung ..... [15]

B2. DIREVISI (blueprint v2.0 keliru / kurang tepat)
  R1 Strict JSON tanpa ruang reasoning [17]
     v2.0: Matcher/Critic output enum langsung.
     v2.1: field `analysis` singkat (dibatasi, mis. ≤60 token per facet)
           DITEMPATKAN SEBELUM `verdict`. Critic memakai dua langkah
           (analisis bebas -> konversi ke schema) karena tugasnya reasoning.
           Profiler (tugas klasifikasi) tetap schema ketat tanpa reasoning.
  R2 "temperature 0 = reproducible" [18]
     v2.0: menyiratkan rerun identik karena temperature 0 + seed.
     v2.1: determinisme hanya dijamin oleh CACHE (output tersimpan,
           ber-key versi). Run tanpa cache diperlakukan sebagai sampel
           stokastik; stabilitas diukur (TARa@N) dan dijadikan gate rilis.
           Batasi max_tokens; minimalkan jumlah keputusan LLM berantai
           yang menentukan satu state.
  R3 Satu call batch berisi SEMUA facet [19]
     v2.1: batch dibatasi (≤6 facet / ≤40 atom per call); atom paling
           relevan di awal; facet MUST_HAVE tidak dicampur dengan banyak
           facet lain. Uji stabilitas dengan pengacakan urutan atom.
  R4 Ontologi dikirim sebagai enum utuh di prompt Profiler [14]
     v2.1: retrieve-then-select: per atom ambil top-15 konsep via embedding
           + alias lexical, LLM memilih dari daftar pendek itu (atau
           NONE / unmapped).
  R5 Fokus deteksi injeksi pada instruksi [20]
     v2.1: pertahanan utama = VISIBILITY GATE: atom hanya boleh berasal
           dari teks yang terlihat (warna kontras, ukuran font wajar,
           di dalam halaman, tidak tertutup). Cek lintas-modal (render
           halaman -> OCR) hanya untuk dokumen yang lolos heuristik
           mencurigakan (biaya OCR tinggi). Deteksi instruksi tetap ada
           sebagai lapisan kedua.
  R6 Summary/self-description sebagai atom bukti biasa [6][8]
     v2.1: atom kind `summary_sentence`/`self_claim` = CLAIM, tier T0:
           tidak pernah cukup untuk STRONG, hanya konteks. Kompetensi
           dibuktikan oleh aktivitas di pengalaman/proyek.

B3. DITAMBAHKAN (tidak ada di v2.0)
  N1 Pemantauan adverse impact di produksi (impact ratio four-fifths per
     kelompok, dari data self-ID sukarela yang disimpan terpisah dan TIDAK
     pernah masuk scoring) [4][23].
  N2 Counterfactual test "CV ditulis ulang oleh LLM" (fakta sama, gaya
     beda) -> verdict tidak boleh berubah; mitigasi self-preference [6].
  N3 Keragaman keluarga model: Critic dari keluarga model berbeda dari
     Matcher (mengurangi bias korelasi & self-preference) [6][1-voting].
  N4 Human-in-the-loop sebagai kontrak, bukan fitur: tidak ada auto-reject,
     keputusan NOT_PROCEED wajib manusia + alasan, ekspor penjelasan per
     kandidat, jalur keberatan kandidat [21][22][23].
  N5 Distilasi node LLM ke model kecil lokal (teacher cache -> review
     manusia -> student) untuk biaya, latensi, dan kedaulatan data [11][16].
  N6 Evaluasi ekstraksi dengan Hungarian alignment + metrik per-field [11].
  N7 Opsional: penyempurnaan ranking puncak dengan PRP dual-order [10].
  N8 Dedup entri pengalaman ganda dari layout multi-kolom [13].

B4. SENGAJA TIDAK DIADOPSI (dan alasannya)
  X1 Debat persona (CEO/CTO/HR) & skor angka dari LLM [2]: tidak diuji
     untuk bias/stabilitas; persona menambah variasi tanpa bukti manfaat.
  X2 Skor holistik LLM "kecocokan kandidat" [4][5]: terbukti rawan
     adverse impact & bias posisi.
  X3 Ranking listwise oleh LLM (masukkan 20 CV, minta urutkan) [10][19]:
     sensitif urutan input dan panjang konteks.
  X4 Neo4j/graph DB terpisah: JobMatchAI memakai Neo4j [15], tetapi skala
     ontologi Anda (ribuan konsep) cukup dengan Postgres + recursive CTE;
     satu database lebih mudah untuk backup, tenant isolation, dan audit.
  X5 Detektor "CV ditulis AI" untuk menghukum kandidat: tidak andal dan
     tidak adil; yang dikendalikan adalah PENGARUH gaya bahasa (R6, N2),
     bukan menghukum penggunaan AI.

################################################################################
 BAGIAN C — BLUEPRINT v2.1 FINAL
################################################################################

C0. DIAGNOSIS KODE v1 (ringkas; detail di blueprint v2.0)
  D1 classify_role_family (kind_rules.py): satu label per pengalaman dari
     regex JUDUL; "Software Engineer" tidak ada di role_families.yaml ->
     "other" -> pengalaman dibuang. Akar Problem 1.
  D2 eval_experience_duration: pengalaman dihitung utuh atau nol; union
     full-time & magang dijumlah terpisah -> overlap dihitung ganda; metrik
     di-hardcode "backend_months"; tahun-saja ditebak bulan 7/6.
  D3 Verifier LLM hanya dipanggil untuk PARTIAL/STRONG -> false negative
     rule tidak pernah dipulihkan.
  D4 Retrieval simetris (cosine+FTS+RRF) memberi bobot pada kemiripan teks,
     bukan pembuktian; ditambah bias embedding [3].

C1. PRINSIP DESAIN (aturan keras)
  P1 LLM hanya membuat KEPUTUSAN KATEGORIKAL SEMPIT atas bukti yang
     ditunjuk; kode menghitung semua angka. [7][4][15]
  P2 Grounding by construction: LLM merujuk atom ID; kode me-resolve ke
     teks, halaman, offset asli, bbox. ID tidak valid = output ditolak.
     [11][12]
  P3 Workflow DAG; "agentic" hanya di dalam node (reasoning terstruktur,
     satu loop ambil-konteks-tambahan, satu loop kritik). [1]
  P4 Kerja JD-independent (profiling) sekali per CV & di-cache; kerja
     JD-dependent (matching) per kandidat x lowongan.
  P5 Ketidakpastian adalah data (interval lo/hi, UNKNOWN, flag) -> REVIEW,
     tidak ditebak.
  P6 Determinisme = cache + output pendek kategorikal + versi tersemat;
     stabilitas diukur, bukan diasumsikan. [18]
  P7 Bukti > klaim: aktivitas terverifikasi di pengalaman/proyek lebih kuat
     dari daftar skill atau kalimat ringkasan. [6][8][20]
  P8 Sistem merekomendasikan, manusia memutuskan. [21][22][23]

C2. TOPOLOGI

GRAPH A — INGESTION & PROFILING (per dokumen, sekali)
  N0  Sanitize + Parse + Boundary + Classify          (v1, deterministik)
  N0b VISIBILITY GATE (baru, R5)                       (deterministik)
        tandai span tak terlihat (warna≈latar, font <4pt, di luar mediabox,
        tertutup objek). Skor kecurigaan tinggi -> render+OCR halaman itu,
        bandingkan; teks yang hanya ada di layer ekstraksi -> HIDDEN.
        Flag HIDDEN_TEXT; konten HIDDEN tidak pernah menjadi atom.
  N1  Redact + OffsetMap                                (v1 + offset map)
  N2  Atomizer (+ dedup multi-kolom, N8)                (deterministik)
        atom = bullet / baris proyek / kalimat ringkasan / item skill /
        header pengalaman, dengan offset asli & teredaksi, page, bbox,
        kind, entry_ref.
  N3  Concept candidate retrieval (R4)                  (deterministik)
        per atom: alias exact/fuzzy + embedding -> top-15 konsep ontologi.
  A1  PROFILER (LLM tier kecil; target jangka menengah: model lokal
      hasil distilasi, N5)
        Tugas klasifikasi -> schema ketat, tanpa reasoning field [17]:
          experiences[]: entry_ref, employment_type, date_text_start/end
            (string mentah), domain_allocation[] {domain, level PRIMARY|
            SECONDARY|INCIDENTAL, support_atoms[]}
          atom_tags[]: atom_key, concepts[] (HANYA dari kandidat N3 atau
            "unmapped:<surface>"), activities[], evidence_type {USAGE,
            OWNERSHIP, LEADERSHIP, MENTION_ONLY}, impact {quantified,
            metric_kind}
        Chunking per entri bila CV panjang (multi-pass seperti [12]).
  V1  Validator: schema, referensial (atom/konsep milik kandidat & versi
      ontologi ini), konsistensi (PRIMARY vs rasio atom bertag domain,
      flag INCONSISTENT_ALLOCATION), retry ≤2 dengan error, fallback rule
      v1 + PROFILER_FALLBACK.
  N4  Date normalizer -> interval lo/hi + presisi       (deterministik)
  N5  Embed atom (bukan per entri)                      (v1 embedding.py)
  ->  persist Competency Graph kandidat (tabel relasional, §C9)

GRAPH B — SCREENING (per kandidat x requirement_set APPROVED)
  S0  Load RequirementIR (facet + duration_policy + evidence policy)
  S1  Hard gates (eligibility v1, hard_filter). Gagal -> catat, TETAP
      tampil untuk review manusia (P8), tidak dihapus diam-diam.
  S2  TEMPORAL ENGINE (kode murni, §C4)
  S3  Evidence retriever per facet (v1 hybrid RRF + ekspansi ontologi),
      HANYA atom visible, top-K=6, diurutkan relevansi.
  S4  Ontology shortcut: facet yang terpenuhi oleh rantai IMPLIES dari
      atom T2+ -> SATISFIED (method=ontology). Murah & deterministik.
  S5  NLI triage lokal (opsional; kalibrasi pada data Anda) untuk facet
      non-MUST: entail/contra sangat yakin -> selesai (method=nli).
  S6  MATCHER (LLM tier menengah)
        batch ≤6 facet / ≤40 atom per call (R3); per facet:
          analysis (≤60 token, field PERTAMA, R1)
          verdict ENTAILED|PARTIAL|NOT_ENTAILED|CONTRADICTED|UNKNOWN
          support_atoms[], depth L0..L4, rationale_code (enum)
          needs_more_context (bool) -> ambil atom tetangga 1x
        Judul jabatan diberikan setelah atom, berlabel context_only.
        Atom CLAIM (summary/self) ditandai sebagai klaim.
  S7  AGGREGATOR (kode): facet -> requirement state; gabung temporal;
      hitung pemicu eskalasi.
  S8  CRITIC (LLM keluarga model BERBEDA dari Matcher, N3), dua langkah
      (analisis bebas -> schema), hanya bila pemicu:
        E1 MUST_HAVE yang menentukan gate/band
        E2 skor dalam ±3 poin dari batas band
        E3 NLI vs Matcher tidak sepakat
        E4 ≥60% atom pendukung bertipe MENTION_ONLY/skill_list/claim
        E5 INCONSISTENT_ALLOCATION / DATE_UNCERTAIN yang mengubah state
        E6 HIDDEN_TEXT atau INJECTION_SUSPECT
      Boleh downgrade; upgrade hanya dengan atom baru yang tervalidasi;
      tidak menyentuh angka. Tetap tidak sepakat -> state konservatif +
      AGENT_DISAGREEMENT -> MANUAL_CHECK.
  S9  SCORER deterministik (scorer.py v1 + §C5)
  S10 (Opsional, N7) TOP-BAND REFINEMENT: hanya kandidat dalam band sama,
      selisih skor < δ, maks 8 kandidat; PRP dual-order per pasangan
      berbasis ledger bukti (bukan CV mentah); hanya mengubah urutan di
      dalam kelompok seri; tidak konsisten -> tetap seri, tie-break v1.
  S11 EXPLAINER: template dari ledger; narasi LLM opsional hanya boleh
      menyebut atom yang ada di ledger.

Orkestrator: LangGraph StateGraph boleh dipakai untuk checkpoint & interrupt
human-in-the-loop, dengan syarat [1]: node = fungsi async murni yang
bisa diuji tanpa framework; tidak memakai prebuilt ReAct agent; fan-out per
kandidat tetap di jobs_queue v1. Alternatif setara: runner asyncio ±200
baris di atas jobs_queue. Mulai dengan yang lebih sederhana bila tim kecil.

C3. SOLUSI PROBLEM 1 — TITLE vs CONTEXT
  1) Facet decomposition (saat kompilasi JD, di-approve recruiter) [9]
     "Frontend Developer" ->
       F1 [core] membangun komponen UI di framework SPA
       F2 [core] mengelola state sisi klien
       F3 [core] implementasi layout/slicing dari desain, responsive
       F4 [supp] integrasi API sisi klien
       F5 [supp] testing/performa frontend
     Template facet per role disimpan di ontologi (konsisten antar JD);
     compiler LLM hanya memilih & menyesuaikan.
  2) Entailment berarah per facet (Matcher), bukan similarity judul.
     Prompt: nilai apakah atom, dibaca harfiah, membuktikan facet; judul
     context_only, tidak boleh jadi dasar tunggal.
  3) Role equivalence dihitung KODE:
       STRONG  = semua core ENTAILED dan ≥2 core depth ≥ L2, bukti dari
                 atom tier ≥ T2
       PARTIAL = ≥2 core ENTAILED, atau semua core ≥ PARTIAL
       lainnya = NOT_DEMONSTRATED
  4) Ontologi berarah (Postgres) [14][15]: IMPLIES (react -> javascript),
     PART_OF, SUBSUMES, PARTIAL_OF (fullstack -> frontend, 0.5). Asimetri
     ada di arah edge. Seed dari config/taxonomy v1, diperkaya ESCO
     skills/occupations (EN; label ID ditambah manual), opsional pemetaan
     KBJI untuk konteks Indonesia.
  5) Judul -> hanya prior bila atom sangat sedikit + flag
     TITLE_CONTEXT_MISMATCH (judul Frontend, nol atom frontend).
  Uji langsung: varian prompt dengan/tanpa judul; delta verdict = metrik
  title-bias (§C11).

C4. SOLUSI PROBLEM 2 — FRAGMENTED DURATION (kode murni, dibenarkan [7])
  1) LLM hanya: teks tanggal mentah + employment_type + domain_allocation.
  2) Normalizer (perluas parse_ym v1; aturan [13]): kamus bulan ID/EN
     (Agt/Agu/Ags, Mei, Okt, Des), "s.d./hingga/sampai", "sekarang/saat
     ini/present". Output Interval(start_lo,start_hi,end_lo,end_hi).
     "2018–2019" -> start∈[2018-01,2018-12], end∈[2019-01,2019-12].
     Tukar start/end bila terbalik ≤1 bulan + flag; tolak durasi >40 th,
     start > as_of -> DATE_ANOMALY.
  3) Bobot (kebijakan RequirementIR, di-approve, tampil di UI):
       w(e,d) = alloc[level(e,d)] x emp[type(e)]
       alloc default: PRIMARY 1.0 | SECONDARY 0.5 | INCIDENTAL 0
       emp default  : full-time/kontrak 1.0 | part-time 0.5 |
                      magang 0.5 | freelance 0.75 | unknown 1.0 + flag
  4) Weighted calendar union per domain:
       months_d = Σ_bulan m  max_{e aktif di m} w(e,d)
     MAX (bukan SUM) -> pekerjaan paralel di domain sama tidak dihitung
     ganda; per domain -> FE & BE paralel tetap dihitung di domainnya
     masing-masing. Sweep-line O(N log N). Dihitung untuk interval
     pesimistik & optimistik -> months_lo, months_hi.
  5) State:
       lo ≥ min            -> STRONG
       hi < min            -> PARTIAL (>0) / NOT_DEMONSTRATED
       lo < min ≤ hi       -> PARTIAL + DATE_UNCERTAIN (eskalasi E5)
  6) Recency opsional: potong ke [as_of − window, as_of] sebelum union.
  7) Ledger per bulan (entry_ref, w) -> UI timeline + bukti header atom.
  Kasus Anda (min 36 bln backend): A 18 (PRIMARY) + B 6 magang x0.5 = 3 +
  C 12 ("Software Engineer", PRIMARY dari atom) = 33 -> PARTIAL; dengan
  kebijakan magang 1.0 -> 36 -> STRONG. Perbedaan = kebijakan, bukan akurasi;
  karena itu diputuskan recruiter dan tercatat di versi.
  Test: property-based (union ≤ Σ durasi; invarian urutan; entri w=0 tidak
  berpengaruh; lo ≤ hi; duplikat = satu), plus golden case.

C5. PROBLEM 3 — RANKING KOMPETENSI ANTI-STUFFING
  Tier bukti (aturan kode):
    T0 skill_list_item, summary/self_claim, MENTION_ONLY -> maks PARTIAL
    T1 project_bullet USAGE
    T2 exp_bullet USAGE
    T3 exp_bullet OWNERSHIP/LEADERSHIP
    T4 T2/T3 + impact.quantified
    HIDDEN -> tidak pernah atom
  Depth L0..L4 berjangkar (deskripsi + contoh di system prompt statis ->
  prompt caching).
  Skor: weight x state_factor x depth_factor; impact bonus dibatasi (≤10%
  bobot kategori); band cap & tie-break v1 tetap; semua faktor di
  scoring_version.
  Diversity: satu atom tidak boleh jadi satu-satunya bukti >3 facet tanpa
  flag; bonus kecil bila facet dibuktikan di ≥2 entri pengalaman.
  Panjang CV TIDAK menambah skor: jumlah atom pendukung per facet di-cap
  (mis. 3) agar CV verbose tidak diuntungkan [8].

C6. DETERMINISTIK vs NON-DETERMINISTIK
  LLM : allocation level, concept selection (dari daftar pendek), verdict
        facet, depth, critic verdict, (opsional) PRP preference.
  Kode: visibility, parsing, redaksi, atom, offset, tanggal, union, state,
        skor, band, rank, tie-break, explainer template.
  Grounding: atom menyimpan offset asli + teredaksi (OffsetMap); evidence
    ledger selalu menampilkan offset ASLI + page + bbox; atom yang
    beririsan span PII ditolak validator.
  Reproducibility (R2): cache key = sha256(task|model_id|prompt_version|
    schema_version|ontology_version|canonical_input); replay = cache.
    Tanpa cache: ukur TARa@5 per node; gate rilis.
  Validasi tiap output: schema -> referensial -> konsistensi -> retry ≤2 ->
    fallback + flag. Tak ada output LLM masuk DB tanpa lolos validator.

C7. FAIRNESS, KEAMANAN, KEPATUHAN
  Input LLM: hanya teks teredaksi (gateway.verify_redacted_text v1 tetap).
  Opsi kebijakan tenant: mask nama institusi/perusahaan untuk facet
    non-pendidikan (menekan prestige bias).
  Uji counterfactual di CI: variasi nama, gender-coded wording, kampus,
    kota, bahasa ID/EN, DAN "ditulis ulang oleh LLM" (N2) -> verdict sama.
  Uji urutan: acak urutan atom (seed tetap) -> verdict stabil [19].
  Produksi (N1): impact ratio per kelompok dari self-ID sukarela (tabel
    terpisah, akses dibatasi, tidak pernah ke scoring); alert bila < 0.8
    pada sampel cukup; laporan berkala siap audit [23].
  Injeksi: visibility gate (utama), deteksi instruksi (sekunder), structured
    output membatasi dampak; HIDDEN_TEXT tidak bisa naik ke band A tanpa
    review manusia [20].
  Human-in-the-loop (N4): tidak ada auto-reject; band R/MANUAL_CHECK
    eksplisit; NOT_PROCEED wajib alasan (v1 sudah); ekspor penjelasan per
    kandidat (requirement, state, bukti, kebijakan durasi); jalur keberatan
    kandidat; DPIA sebelum go-live [21]; notifikasi penggunaan AI ke
    kandidat [22][23].

C8. EFISIENSI TOKEN & BIAYA
  1 Profiling sekali per CV, dipakai lintas lowongan.
  2 Ontology shortcut (S4) & NLI triage (S5) sebelum LLM.
  3 Matcher batch terbatas (≤6 facet), top-K atom, output pendek.
  4 Critic hanya saat pemicu (perkiraan 15–30% kandidat; ukur).
  5 Routing tier per task + prompt caching untuk rubrik statis [1].
  6 Funnel untuk batch besar: pre-score deterministik semua kandidat ->
    matcher penuh untuk top-N + kandidat yang gagal hanya karena role/durasi
    (kelompok false-negative v1).
  7 Budget guard per run; lewat batas -> jalur deterministik +
    BUDGET_DEGRADED.
  8 Jangka menengah (N5): distilasi Profiler (dan facet classifier Matcher)
    ke model kecil lokal dari output teacher yang sudah tersimpan di cache
    dan disaring manusia [11][16]; LLM besar tinggal untuk Critic.
  Catat aktual di model_calls (kolom tokens/cost sudah ada).

C9. SKEMA DATABASE (tambahan atas skema v1)
  redaction_offset_maps(document_id PK, segments jsonb)
  evidence_atoms(id, profile_id, atom_key, kind [+ 'self_claim'],
    visibility {VISIBLE,HIDDEN,SUSPECT}, entry_ref, page, char_start,
    char_end, red_start, red_end, bbox, text_redacted, embedding vector(640),
    fts, UNIQUE(profile_id, atom_key))  -- HNSW + GIN
  experience_entries(id, profile_id, entry_ref, header_atom_id, title_raw,
    employment_type, date_text_start/end, start_lo, start_hi, end_lo,
    end_hi, is_current, date_flags[])
  ontology_versions(version, sha256), concepts(version,id,label,kind,
    aliases[], esco_uri), concept_edges(version,src,dst,relation
    {IMPLIES,PART_OF,SUBSUMES,PARTIAL_OF},weight), facet_templates(version,
    role_concept, facet_key, hypothesis, core, concepts[])
  atom_tags(atom_id PK, concepts[], activities[], evidence_type,
    impact_quantified, impact_kind, model_call_id, ontology_version)
  experience_domain_allocations(experience_id, domain, level,
    support_atom_ids[], code_atom_ratio, flags[], model_call_id)
  requirements + kolom: target_domains[], duration_policy jsonb,
    accepted_evidence[], depth_floor; requirement_facets(requirement_uuid,
    facet_key, hypothesis, core, concepts[])
  facet_judgments(run_id, candidate_id, requirement_id, facet_key, verdict,
    depth_level, support_atom_ids[], method {ontology,nli,matcher,critic,
    manual}, analysis text, nli_p_entail, rationale_code,
    superseded_by_critic)
  domain_durations(run_id, candidate_id, domain, policy_hash, months_lo,
    months_hi, month_ledger jsonb)
  agent_steps(id, graph, run_id, document_id, candidate_id, node, attempt,
    input_hash, output jsonb, validation_status {OK,RETRY,FALLBACK,FAILED},
    validation_errors, model_call_id, escalation_reasons[], created_at)
  stability_probes(run_id, node, sample_n, tara, created_at)      -- R2
  fairness_selfid(candidate_id PK, tenant_id, attributes bytea terenkripsi,
    consent_at)          -- terpisah dari scoring, akses audit saja (N1)
  fairness_reports(id, tenant_id, job_id, run_id, metric, group_key,
    selection_rate, impact_ratio, n, created_at)
  candidate_objections(id, candidate_id, run_id, received_at, status,
    resolution, reviewer_id)                                     -- N4
  ontology_suggestions(id, surface, proposed_concept, source, status)
  evidence + kolom atom_id; requirement_scores.method + 'agent'
  Checkpoint LangGraph (bila dipakai) di schema terpisah 'lg'.
  Rapikan: komentar dimensi 1024 vs vector(640) di db_schema.sql.

C10. PETA MODUL v1 -> v2.1
  PERTAHANKAN: infrastructure/* (gateway diperluas: tier routing, budget,
    schema output, keluarga model untuk Critic), worker/sanitizer
    (+visibility gate), docling_parser, boundary, classifier, redaction
    (+OffsetMap), anchor, embedding (per atom), domain/pii, auth,
    policy_linter (juga lint facet), eligibility, scorer (diperluas;
    test_scorer_parity tetap), retrieval (jadi evidence retriever),
    jobs_queue/worker, api/*, migrasi 0001–0009, test infra & keamanan.
  REFACTOR: worker/adapter.py (773 baris) -> atomizer deterministik
    (find_provenance dipakai ulang) + Profiler; processor.py -> Graph A;
    jd_compiler.py -> RequirementIR (rule-based tetap fallback);
    taxonomy.py + config/taxonomy/*.yaml -> ontologi berarah; verifier.py ->
    Critic (cache & grounding guard dipakai ulang); screening_service.py ->
    Graph B runner; explainer.py -> berbasis ledger.
  TULIS ULANG: kind_rules.py — classify_role_family dicopot sebagai gate;
    eval_experience_duration -> domain/temporal/; eval_skill/
    responsibility/achievement/leadership -> facet pipeline;
    eval_education/certification tetap rule-based (fakta diskret);
    parse_ym & merge_intervals pindah ke temporal/ dan diperluas.

  Struktur repo:
  src/infrastructure/   config, database, logging, gateway
  src/api/              + /runs/{id}/ledger, /candidates/{id}/timeline,
                          /candidates/{id}/explanation-export,
                          /objections, /fairness/reports, /ontology/curation
  src/ingestion/        sanitizer, visibility, docling_parser, boundary,
                        classifier, redaction, atomizer, embedding
  src/domain/ontology/  requirements/  temporal/  scoring/  eligibility/
             pii/  auth/  fairness/
  src/agents/schemas/   Pydantic I/O (single source of truth)
  src/agents/prompts/   profiler_vN.md, matcher_vN.md, critic_vN.md
  src/agents/           profiler.py matcher.py critic.py nli_triage.py
                        prp_refiner.py validators.py
  src/graphs/           ingestion_graph.py screening_graph.py state.py
  tests/unit/temporal/  (hypothesis)   tests/agents/ (respons terekam)
  tests/eval/           golden v2, counterfactual, stability
  config/               ontology/, policies/, scoring/, models.yaml

C11. EVALUASI (gate rilis)
  Ekstraksi : F1 per-field dengan Hungarian alignment entri [11];
              MAE durasi per domain (bulan); % DATE_UNCERTAIN.
  Keputusan : confusion matrix per state, fokus false-negative MUST_HAVE.
  Ranking   : NDCG@10, Precision@shortlist, Spearman/Kendall vs label
              recruiter (sebanding dengan [2]).
  Grounding : 100% judgment ENTAILED punya atom valid & visible (wajib);
              % atom yang Critic nilai DOES_NOT_SUPPORT.
  Title-bias: delta verdict dengan/tanpa judul jabatan.
  Fairness  : counterfactual flip = 0; impact ratio simulasi ≥ 0.8 [4][23];
              flip pada "CV ditulis ulang LLM" [6].
  Stabilitas: TARa@5 per node tanpa cache; Jaccard top-10 antar-run;
              band flip di luar zona batas = 0 [18].
  Robustness: CV dengan skill tersembunyi -> skor tidak berubah [20];
              pengacakan urutan atom [19].
  Biaya     : token & biaya per CV per lowongan; % facet selesai di
              ontology/NLI; % kandidat ke Critic.
  CI memakai respons terekam (gratis & deterministik); eval live terjadwal
  dan wajib saat ganti model/prompt.

C12. ROADMAP
  F0 (1 mgg)  Fork, CI hijau. Golden set v2 (≥60 kasus): title-mismatch,
              durasi terfragmentasi, concurrent, magang overlap, tahun-saja,
              stuffing terlihat & TERSEMBUNYI, CV ber-impact tapi sedikit
              keyword, CV ditulis ulang LLM, injeksi, bilingual. Label
              manusia + catat baseline v1.
  F1 (1–2)    Visibility gate, OffsetMap, Atomizer, evidence_atoms, embed
              per atom. Test: offset asli -> substring identik.
  F2 (1)      Temporal engine + Profiler minimal (employment_type,
              allocation). Shadow mode vs v1, laporan diff durasi.
  F3 (2–3)    Ontologi (seed v1 + ESCO) + retrieve-then-select, facet
              templates, RequirementIR + UI approve, ontology shortcut,
              NLI triage, Matcher. Shadow mode penuh, laporan rank-diff.
  F4 (1–2)    Critic (keluarga model berbeda), pemicu, scorer v2, tier bukti,
              stabilitas & counterfactual di CI.
  F5 (2)      UI: timeline per domain, tabel facet, highlight atom di PDF,
              badge metode, antrian MANUAL_CHECK, ekspor penjelasan,
              keberatan kandidat, laporan fairness. DPIA. Cutover per
              tenant (params.engine = v1|v2); v1 tetap sebagai fallback.
  F6 (lanjutan) Distilasi Profiler/facet classifier ke model lokal kecil
              dari cache teacher yang disaring manusia [11][16]; PRP
              top-band refinement bila data menunjukkan manfaat.
  Kriteria go-live: semua metrik C11 lolos ambang yang Anda tetapkan,
  dengan grounding 100%, counterfactual flip 0, dan v2 > v1 pada NDCG@10
  serta recall MUST_HAVE tanpa penurunan precision > 2 poin.

C13. RISIKO UTAMA
  Perilaku model berubah di ID sama -> eval live terjadwal; cache = replay.
  Ontologi tak lengkap -> facet tetap dinilai via teks atom; ontologi
    hanya akselerator.
  Latensi batch besar -> profiling saat upload; funnel; semaphore.
  Over-reliance recruiter -> UI menampilkan bukti dulu, skor kedua.
  Kebijakan durasi diperdebatkan -> parameter eksplisit per lowongan.
  Bias residual -> monitoring impact ratio + audit berkala + jalur
    keberatan.
  Data pribadi ke LLM eksternal -> redaksi + guard gateway + opsi model
    lokal (F6).

################################################################################
 BAGIAN D — REFERENSI
################################################################################
 [1]  Anthropic. Building effective agents.
      https://www.anthropic.com/research/building-effective-agents
 [2]  Lo et al. AI Hiring with LLMs: A Context-Aware and Explainable
      Multi-Agent Framework for Resume Screening. CVPR Workshops 2025.
      https://arxiv.org/abs/2504.02870
 [3]  Wilson & Caliskan. Gender, Race, and Intersectional Bias in Resume
      Screening via Language Model Retrieval. AIES 2024.
      https://arxiv.org/html/2407.20371v1
 [4]  Eightfold AI. Evaluating the Promise and Pitfalls of LLMs in Hiring
      Decisions. 2025. https://arxiv.org/html/2507.02087v1
 [5]  Rozado. Gender and Positional Biases in LLM-Based Hiring Decisions.
      2025. https://arxiv.org/abs/2505.17049v2
 [6]  Xu, Li, Jiang. AI Self-preferencing in Algorithmic Hiring. 2025.
      https://arxiv.org/html/2509.00462v3
 [7]  Fatemi et al. Test of Time: A Benchmark for Evaluating LLMs on
      Temporal Reasoning. ICLR 2025. https://arxiv.org/html/2406.09170v1
 [8]  Zheng et al. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena.
      NeurIPS 2023. https://arxiv.org/html/2306.05685v4
 [9]  Lee et al. CheckEval: A reliable LLM-as-a-Judge framework using
      checklists. EMNLP 2025. https://arxiv.org/html/2403.18771v2
 [10] Qin et al. Large Language Models are Effective Text Rankers with
      Pairwise Ranking Prompting. NAACL Findings 2024.
      https://arxiv.org/html/2306.17563v2
 [11] Layout-Aware Parsing Meets Efficient LLMs: A Unified, Scalable
      Framework for Resume Information Extraction and Evaluation. 2025.
      https://arxiv.org/pdf/2510.09722
 [12] Google. Introducing LangExtract. 2025.
      https://developers.googleblog.com/en/introducing-langextract-a-gemini-powered-information-extraction-library/
 [13] JobHop v2: A Large-Scale Career Trajectory Dataset from Unstructured
      Resumes. 2026. https://arxiv.org/pdf/2607.11715
 [14] Clavié & Soulié. Large Language Models as Batteries-Included
      Zero-Shot ESCO Skills Matchers. 2023. https://arxiv.org/html/2307.03539v1
 [15] JobMatchAI: An Intelligent Job Matching Platform Using Knowledge
      Graphs, Semantic Search and Explainable AI. ACL 2026 demo.
      https://arxiv.org/html/2603.14558v1
 [16] LANTERN: Scalable Distillation of LLMs for Job-Person Fit and
      Explanation (LinkedIn). 2025. https://arxiv.org/pdf/2510.05490
 [17] Tam et al. Let Me Speak Freely? Impact of Format Restrictions on LLM
      Performance. EMNLP Industry 2024. https://arxiv.org/html/2408.02442v1
 [18] Atil et al. Non-Determinism of "Deterministic" LLM Settings.
      https://arxiv.org/html/2408.04667v5
 [19] Liu et al. Lost in the Middle: How Language Models Use Long Contexts.
      TACL 2024. https://huggingface.co/papers/2307.03172
 [20] Zhang et al. Measuring Real-World Prompt Injection Attacks in
      LLM-based Resume Screening. 2026. https://arxiv.org/pdf/2605.28999
 [21] UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi.
      https://peraturan.bpk.go.id/Details/229798/uu-no-
      ringkasan Pasal 10: https://justisio.com/regulation/indonesia/sjl9k22zlhhkpa0r87j2itst
 [22] EU AI Act setelah Digital Omnibus (ringkasan).
      https://www.nodes.inc/research/digital-omnibus-ai-hiring
 [23] NYC Local Law 144 — final rules (ringkasan).
      https://perkinscoie.com/en/news-insights/nyc-adopts-final-rules-for-law-governing-automated-employment-decision-tools.html
================================================================================
