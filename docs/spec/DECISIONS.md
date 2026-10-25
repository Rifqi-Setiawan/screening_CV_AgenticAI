# DECISIONS — Perubahan dari Draf Awal Agent dan Alasannya

Draf awal (dari agent di VPS) sudah bagus strukturnya. Beberapa bagian diubah supaya hasilnya bisa
dipertanggungjawabkan, tidak bias, dan bisa diuji. Kalau agent tidak setuju dengan salah satu keputusan di
bawah, tulis alasannya di `docs/ANSWERS.md` dan tanyakan ke pemilik produk. **Jangan mengubah diam-diam.**

| # | Draf awal | Keputusan | Alasan |
| --- | --- | --- | --- |
| D1 | LLM Judge memberi skor 0–100 + pros/cons per kandidat | LLM **tidak** memberi skor. Skor dihitung kode dari status per kriteria × bobot. LLM hanya memilih status untuk kriteria ambigu dari pilihan tertutup, dengan kutipan yang dicek kode | Skor LLM berubah-ubah antar run, sensitif ke prompt, mahal per CV, tidak bisa diaudit, dan rawan prompt injection. Golden dataset mewajibkan hasil identik saat diulang |
| D2 | Kategori "Soft Skills / Prestasi" 15% | Diganti "Pencapaian & Kepemimpinan Terbukti" 15%: hanya pencapaian bernomor dan pengalaman memimpin yang tertulis | Soft skill tidak bisa dibuktikan dari CV dan rawan bias (gaya bahasa, latar belakang). Soft skill dipindah ke panduan interview |
| D3 | Ranking murni dari skor total | Ranking per **band** dulu (semua wajib terbukti → 1 wajib belum → ≥ 2 wajib belum), lalu skor; skor band B dibatasi 74 dan band C dibatasi 49 | Kandidat yang gagal kriteria wajib tidak boleh menyalip kandidat yang lolos hanya karena banyak nilai tambah (kasus S3 vs M1 di golden dataset) |
| D4 | Rekomendasi "Shortlist / Review / Reject" | "Disarankan shortlist / Perlu ditinjau / Prioritas rendah / Perlu cek manual". Tidak ada "Reject" dari mesin | Penolakan adalah keputusan manusia. PP 33/2026 (UU PDP) memberi hak keberatan atas keputusan yang sepenuhnya otomatis |
| D5 | Aturan red flag "pelamar salah jurusan total" | Tidak ada aturan khusus. Skor rendah muncul alami karena kriteria tidak terbukti | Aturan "salah jurusan" mudah bias (mis. lulusan non-IT yang berpengalaman) |
| D6 | Tabel `candidates` berisi nama, email, telepon | Identitas dipisah ke `candidate_identities`; penilaian memakai profil teredaksi; tabel ranking default blind mode | Studi University of Washington (2024) menemukan model embedding memihak nama tertentu saat menyaring resume. Redaksi harus sebelum embedding/LLM, bukan hanya di tampilan |
| D7 | 3 tabel (`jobs`, `candidates`, `screenings`) | 19 tabel termasuk kriteria berversi, bukti per kriteria, run immutable, audit | Butuh bukti per kriteria, hasil yang bisa diulang dan dibandingkan, dan jejak audit |
| D8 | PostgreSQL/SQLite + DuckDB/Chroma | PostgreSQL + pgvector saja | Satu tempat untuk data pribadi = satu tempat untuk diamankan, di-backup, dan dihapus. pgvector cukup untuk skala ini |
| D9 | Frontend React/Tailwind atau Streamlit | React + Vite + TS + Tailwind + TanStack Table + pdf.js | Preview CV dengan highlight kutipan dan tabel interaktif lebih rapi di React |
| D10 | Tidak ada langkah persetujuan kriteria | Draf kriteria **wajib** disetujui recruiter sebelum screening; policy linter menolak kriteria diskriminatif | Kriteria salah = semua ranking salah. JD di Indonesia sering memuat syarat usia/gender/penampilan |
| D11 | Golden dataset 10–20 CV dummy (belum ada) | Disediakan 15 CV inti + 9 edge case + label + evaluator otomatis | Supaya akurasi diukur sejak hari pertama, bukan diklaim |
| D12 | `GET /jobs/{id}/rankings` | `GET /screenings/{run_id}/rankings` | Ranking melekat pada run (versi kriteria, model, tanggal), sehingga bisa diulang dan dibandingkan |
| D13 | Semantic embedding menentukan relevansi ("Golang relevan dengan Backend") | Embedding dipakai untuk mencari kandidat (pool besar) dan memilih potongan bukti; status kriteria tetap ditentukan aturan + verifier | Kemiripan embedding bukan bukti. "Golang" relevan untuk role backend, tapi tidak membuktikan "Python" |
| D14 | Cache hasil evaluasi | Cache per tahap: hasil ekstraksi (per hash file + versi extractor), embedding (per hash chunk + model), panggilan LLM (per hash input + model + prompt) | Run ulang tidak memanggil LLM lagi; perubahan model/prompt otomatis membatalkan cache yang relevan |
| D15 | Target "3 hari menjadi 5 menit" | Target terukur: proses mesin 300 CV < 15 menit; shortlist termasuk review < 60 menit (diuji saat pilot) | Angka harus bisa diverifikasi; waktu review manusia tetap ada |
