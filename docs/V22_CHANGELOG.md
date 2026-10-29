# Perubahan v2.2 (turunan v2.1)

Berdasarkan acuan arsitektur v3.0 dan audit 19 CV riil. Semua perubahan ada di salinan kerja; belum ada yang
di-deploy. Pengujian live ke beberapa CV dilakukan terakhir (lihat bagian "Perlu divalidasi live").

## Temuan dari kode dan data yang mendasari perubahan

| # | Temuan | Dampak di run 19 CV |
|---|---|---|
| 1 | Setiap kriteria (apa pun jenisnya) mendapat 5 facet template role (`screening_service` memanggil `decompose_role_to_facets(description)`) | 6 kriteria bergantung pada facet yang sama: satu facet lemah menurunkan semuanya ke PARTIAL (8 kandidat tepat 50,0) dan Matcher memanggil facet yang sama sekali per kriteria (353 panggilan) |
| 2 | Hasil Critic hanya di-agregasi ulang untuk **satu** kriteria (pemetaan `facet_key -> requirement` menyimpan yang terakhir) | State kriteria dalam satu kandidat tidak konsisten; replay menunjukkan 4 dari 19 kandidat berbeda dari state yang tersimpan |
| 3 | Rubrik kedalaman L0..L4 tidak pernah berlaku di pipeline penuh: enum `DepthLevel` diubah ke teks `"DEPTHLEVEL.L2"` yang tidak dikenali skor | Skor hanya berbasis state (kandidat all-L2 mendapat 100). Sekarang eksplisit dan default mati |
| 4 | `AGENT_DISAGREEMENT` memaksa Band R berapa pun skornya; E1 memicu Critic untuk hampir semua kandidat; E2 memakai batas 50/75 yang hanya batas warna | 17 dari 19 kandidat Band R (termasuk skor 92,1); Critic dipanggil untuk 17 dari 19 |
| 5 | Visibility gate tidak pernah dipanggil dari worker (`run_profiling_pipeline` dipanggil tanpa `pdf_spans`); sanitizer menandai teks putih sebagai tersembunyi walau di atas latar gelap | Pertahanan teks tersembunyi hanya `strip_hidden_pdf_spans` (font <4pt) |
| 6 | Atom tanpa lokasi di dokumen tetap dipakai (offset 0..0); offset dari parser tidak diverifikasi | 29 atom bukti dengan span kosong pada run 19 CV |
| 7 | Prompt Matcher/Critic menaruh teks CV mentah tanpa pembatas | Tidak ada pemisahan data dan instruksi |
| 8 | `resolve_role_family("backend")` mengembalikan `fullstack` (alias ontologi mengalahkan nama role persis) | Template role salah untuk kata "backend" saja |

## Perubahan perilaku

**Fase 1: latensi dan facet**
- Facet per kriteria (`facet_narrowing.py`): pernyataan pengalaman umum ("minimal N tahun sebagai role") tetap memakai
  template role; kriteria lain (SKILL dst.) dinilai lewat satu facet berisi teks kriterianya sendiri. Hanya facet yang
  tampak hasil auto-isi template yang diganti; facet buatan recruiter/compiler tidak disentuh.
- Setiap facet unik dinilai sekali per kandidat, hasilnya dipakai semua kriteria yang memakainya.
- Kandidat diproses paralel (`SCREENING_CANDIDATE_CONCURRENCY`), batch Matcher paralel, batas global permintaan LLM
  (`LLM_MAX_CONCURRENCY`) dengan backoff berjitter.
- Hasil Critic kini diagregasi ulang untuk semua kriteria pengguna facet itu.
- `MATCHER_RETRIEVAL_TOP_K` (default 0 = kirim semua atom) untuk retrieval sebelum judging; ukur dulu sebelum dinyalakan.
- Perbaikan `resolve_role_family`: nama role persis diutamakan atas alias ontologi.

**Fase 2: Critic dan skor**
- Critic hanya untuk anomali (E2 batas nyata 49/70/74, E3-E6), top-K sementara (`CRITIC_TOP_K`), dan sampel acak yang
  dapat diulang (`CRITIC_RANDOM_AUDIT_RATE`). E1 sendiri tidak lagi memicu Critic.
- `AGENT_DISAGREEMENT` menjadi sinyal review: band mengikuti skor, SHORTLIST turun ke REVIEW, flag
  `AGENT_DISAGREEMENT_REVIEW`. Perilaku lama: `AGENT_DISAGREEMENT_FORCES_BAND_R=true`.
- Skor interval (`score_lo/score_hi`, UNKNOWN sebagai kasus terburuk/terbaik); interval yang melewati batas shortlist
  70 memberi flag dan memicu audit.
- `rank_v2` mengurutkan kandidat yang terpangkas cap band berdasarkan skor mentah sebelum hash.
- Implikasi konteks domain (`domain_inference.py`): sistem transaksi/pembayaran/trading mengangkat facet basis data dari
  NOT_ENTAILED/UNKNOWN ke PARTIAL L1 saja, dengan atom pendukung nyata dan flag `DOMAIN_INFERENCE`.
- Rubrik kedalaman: `SCORER_DEPTH_FACTORS_ENABLED` (default `false`, sama dengan perilaku efektif v2.1). Menyalakannya
  mengubah skala semua skor; putuskan dengan data evaluasi.

**Fase 3: hardening**
- Span atom diverifikasi (pencarian toleran spasi); offset parser yang tidak menunjuk teks yang benar dicari ulang;
  atom yang tidak ditemukan ditolak sebagai bukti (`REQUIRE_VERIFIED_SPANS`), kecuali bila itu menghapus semua bukti
  (flag `SPAN_VERIFICATION_UNAVAILABLE`).
- Visibility gate dipasang di worker dan sanitizer, dengan cek piksel (teks tanpa tinta terender dianggap tersembunyi;
  putih di atas latar gelap tetap terlihat). DOCX: deteksi run `vanish`, putih, font <4pt.
- Higiene teks: NFKC, karakter tak terlihat/bidi dibuang di batas LLM, deteksi homoglif, pola injeksi ID+EN.
- Prompt Matcher/Critic: atom dalam blok `<cv_data_NONCE>` dengan nonce dari isi, penutup/penanda seksi dinetralkan,
  aturan "data tidak tepercaya" di system prompt, flag `INJECTION_SUSPECT` dari model masuk ke pemicu E6.
- Flag dari hulu (sanitizer, matcher, mesin tanggal) sekarang ikut menentukan pemicu E4/E5/E6.

**Fase 4: fairness**
- Pernyataan atribut terlindungi (agama, gender, usia, status pernikahan, suku, fisik, alamat) di-scrub dari teks yang
  dikirim ke LLM (`SCRUB_PROTECTED_ATTRIBUTES`); atom pendidikan tidak dikirim ke Matcher/Critic kecuali ada kriteria
  EDUCATION (`MATCHER_EXCLUDED_ATOM_KINDS`).
- Tes counterfactual (`tests/fairness`) dan gate model (`test_live_model_gate.py`): mengganti model yang dikonfigurasi
  mewajibkan `scripts/run_live_fairness.py` dijalankan ulang.

**Fase 5: recruiter-in-the-loop**
- Probe wawancara berdasarkan value of information (`domain/interview`), anggaran sama per kandidat, blocklist topik
  terlindungi, status `PENDING_APPROVAL`. Jawaban dinilai recruiter (STRONG/ADEQUATE/WEAK) menjadi atom
  `interview_answer` (tier T2/T1) dan skor dihitung ulang di kode; hasil asli tidak berubah.
- Copilot HR (`domain/copilot`): empat tool terstruktur, sitasi atom wajib (`enforce_citations`), penolakan query
  inferensi atribut terlindungi, audit trail `copilot_audit_log`.
- Endpoint baru di `recruiter_assist.py`, migrasi `0014_recruiter_assist`.

**Penjelasan skor dan penelusuran sumber (explainability)**
- Temuan: tautan dari putusan facet ke kutipan CV tidak pernah tersimpan (kolom `support_atom_ids` bertipe uuid[] hanya
  menerima UUID, sedangkan atom dirujuk lewat kunci seperti `E3.B4`; 0 dari 95 putusan pada run 19 CV punya tautan).
  UI juga hanya menampilkan penjelasan versi v1 (template dari tabel `evidence`), tidak memakai data facet/atom/Critic yang
  sudah dikirim API, dan penampil CV menampilkan teks karangan bila `full_text` kosong.
- Migrasi `0015_facet_support_keys`: kolom `facet_judgments.support_atom_keys text[]`; pipeline dan Matcher menyimpan kunci atom.
- `domain/score_trace.py` + `score_trace`, `full_text`, `source_highlights` pada `GET .../candidates/{id}`:
  skor -> kriteria (bobot x nilai state = poin) -> facet (putusan, kedalaman, alasan, audit Critic) -> atom -> kalimat asli
  di CV (kutipan verbatim + konteks, letak, tier bukti), alasan band dan rekomendasi, durasi per periode, arti tiap flag.
  Angka akhir dihitung ulang dengan scorer yang sama dan dibandingkan dengan angka tersimpan; bila berbeda (run lama),
  trace menyatakannya dan angka tersimpan tetap berlaku.
- Pencocokan span atom diperketat: potongan yang memotong kalimat di tengah kata ditolak dan dicari ulang.
- UI: tab baru "Asal-usul Skor" (`ScoreTrace.tsx`) dan penampil CV yang menyorot kalimat bukti dan melompat ke kutipan
  yang dipilih; teks karangan pada penampil CV dihapus. Hasil run lama tetap tampil, dengan catatan bahwa kutipan sumber
  baru tersedia setelah screening ulang.

## Konfigurasi baru

`LLM_MAX_CONCURRENCY=8`, `SCREENING_CANDIDATE_CONCURRENCY=4`, `FACET_NARROWING_ENABLED=true`,
`MATCHER_RETRIEVAL_TOP_K=0`, `REQUIRE_VERIFIED_SPANS=true`, `SCRUB_PROTECTED_ATTRIBUTES=true`,
`MATCHER_EXCLUDED_ATOM_KINDS=["education"]`, `SCORER_DEPTH_FACTORS_ENABLED=false`, `DOMAIN_INFERENCE_ENABLED=true`,
`CRITIC_TOP_K=5`, `CRITIC_RANDOM_AUDIT_RATE=0.05`, `CRITIC_BORDER_MARGIN=3.0`, `AGENT_DISAGREEMENT_FORCES_BAND_R=false`.

## Perlu divalidasi live (belum bisa diukur offline)

1. Latensi dan biaya per CV, serta panggilan Matcher sebenarnya setelah dedupe facet.
2. Pengaruh facet per kriteria pada peringkat (replay offline tidak bisa menilai facet baru).
3. Efek `CRITIC_TOP_K` dan sampel acak pada false negative.
4. Apakah scrub atribut dan pengecualian atom pendidikan menurunkan akurasi.
5. Fairness dengan model sungguhan: `scripts/run_live_fairness.py`.
6. Hasil replay: facet bersama + propagasi Critic yang benar membuat semua kriteria turun bersamaan; perbaikan propagasi
   dan facet per kriteria harus dirilis bersama.
