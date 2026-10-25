# Prompt untuk dikirim ke agent di VPS

Salin teks di bawah garis ini apa adanya, bersama file `cv-screening-spec.zip`.

---

Halo. Terlampir `cv-screening-spec.zip` berisi spesifikasi lengkap sistem screening CV yang akan kita bangun di
VPS ini, sesuai dokumen yang kamu minta (PRD, scoring rubric, arsitektur, data model & API, UI/UX, golden test
dataset), ditambah rencana implementasi, dataset uji siap pakai, dan evaluator otomatis.

Tolong lakukan ini, berurutan:

1. Ekstrak zip ke folder `docs/spec/` di repo proyek (buat repo baru `cv-screening` kalau belum ada).
2. Baca `00_README_UNTUK_AGENT.md` lebih dulu, lalu semua dokumen sesuai urutan di sana. `DECISIONS.md`
   menjelaskan bagian draf awalmu yang diubah dan alasannya.
3. Jalankan `cd docs/spec/golden_dataset && python evaluate.py --self-test`. Harus `LULUS`.
4. Kerjakan **M0 (Discovery)** di `07_IMPLEMENTATION_PLAN.md`: jawab semua pertanyaan di
   `09_QUESTIONS_FOR_AGENT.md` ke `docs/ANSWERS.md`. Jalankan perintahnya dan tempel output asli; jangan menebak.
   Termasuk: uji `cv-extractor` yang sudah ada di VPS pada 15 CV inti dan jalankan `evaluate.py --extraction`.
5. Kirim ke saya ringkasan M0: spesifikasi VPS, hasil uji `cv-extractor` (angka PASS/FAIL), jawaban yang butuh
   keputusan saya (bertanda ⚠️), bagian spesifikasi yang menurutmu bermasalah beserta usulanmu, dan rencana
   M1–M6 dengan perkiraan waktu.
6. **Berhenti dan tunggu konfirmasi saya** sebelum mulai M1.

Aturan penting selama mengerjakan:

- LLM tidak boleh memberi skor kandidat; skor dihitung kode (`golden_dataset/generator/reference_scorer.py`).
- Setiap klaim tentang kandidat harus punya kutipan CV yang dicek kode.
- Identitas kandidat dipisah sebelum embedding/LLM/penilaian.
- Jangan ubah label golden dataset untuk meluluskan tes.
- Jangan kirim CV asli ke API LLM eksternal tanpa izin tertulis saya.
- Jangan commit `.env`, CV asli, atau data pribadi.
- Kalau ada bagian spesifikasi yang tidak bisa atau tidak masuk akal dikerjakan, tanya dulu; jangan menyimpang
  diam-diam.

Laporan pakai Bahasa Indonesia, ringkas, dengan angka konkret. Terima kasih.
