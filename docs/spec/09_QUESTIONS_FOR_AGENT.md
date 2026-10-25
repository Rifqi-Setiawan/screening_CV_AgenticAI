# 09 — Pertanyaan untuk Agent (jawab sebelum menulis kode)

Jawab semua pertanyaan di bawah dalam file `docs/ANSWERS.md` di repo. Untuk pertanyaan teknis, **jalankan
perintahnya dan tempel hasilnya**, jangan menebak. Setelah selesai, kirim ringkasan ke pemilik produk dan
**tunggu konfirmasi** untuk bagian yang ditandai ⚠️.

## A. Kondisi VPS

1. Spesifikasi: `nproc`, `free -h`, `df -h`, `uname -a`, `cat /etc/os-release`, `nvidia-smi` (kalau ada).
2. Apa saja yang sudah terpasang dan berjalan: `docker --version`, `docker compose version`,
   `docker ps`, `systemctl list-units --type=service --state=running`, `psql --version`, `python3 --version`,
   `node --version`, `tesseract --list-langs`.
3. Port yang sudah dipakai: `ss -tlnp`.
4. Apakah VPS punya domain/subdomain untuk aplikasi ini? Apakah HTTPS sudah ada?
5. Layanan lain apa yang jalan di VPS yang sama (mis. Hermes, web lain)? Berapa RAM yang aman dipakai aplikasi
   ini tanpa mengganggu layanan lain?

## B. Engine `cv-extractor` yang sudah ada

6. Lokasi kode, bahasa, dan cara memanggilnya (CLI, HTTP, import Python). Tempel contoh perintah.
7. Format input yang didukung (PDF teks, PDF scan, DOCX, gambar)? Apakah ada OCR? Engine OCR apa?
8. Tempel **contoh output lengkap** untuk satu CV (pakai `golden_dataset/cvs/core/S1_senior_backend_id.pdf`).
9. Apakah output menyertakan nomor halaman, posisi karakter, atau bounding box untuk tiap nilai? Kalau tidak,
   bagaimana rencana adapter mencari posisi kutipan?
10. Jalankan extractor ke 15 CV inti, buat adapter cepat ke format `extraction-export`, lalu jalankan
    `python golden_dataset/evaluate.py --extraction out/extraction.json`. Tempel hasilnya.
11. Format mana yang gagal (scan, dua kolom, DOCX, tanggal tertentu)? Usulkan perbaikan minimal.
12. Apakah extractor memakai LLM? Kalau ya: model apa, lokal atau API, dan data apa yang dikirim?

## C. LLM dan model

13. ⚠️ LLM apa yang tersedia: lokal (Ollama/llama.cpp/vLLM, model apa) atau API (provider apa, ada API key)?
14. ⚠️ Kebijakan data: boleh mengirim **teks CV teredaksi** ke API luar negeri (`redacted_api`), atau hanya
    lokal (`local_only`)?
15. Ukur kecepatan LLM lokal (kalau ada): token/detik untuk prompt 1.500 token + output 300 token.
16. Bisakah VPS menjalankan model embedding 0.6B di CPU? Ukur waktu embedding 100 potongan teks.
17. Apakah Jev (TypeSafe) sudah punya akses? (Opsional; hanya untuk eksperimen verifier.)

## D. Produk

18. ⚠️ Siapa pengguna awal (HR internal, satu perusahaan klien, atau demo portofolio)? Berapa CV per lowongan
    yang realistis?
19. ⚠️ Berapa lama data CV disimpan (default usulan: 12 bulan setelah lowongan ditutup)?
20. Apakah nama kandidat boleh tampil di tabel, atau blind mode dikunci ON?
21. Perlukan login multi-user di MVP, atau satu akun admin cukup untuk tahap awal?

## E. Rencana

22. Tulis rencana implementasi singkat per milestone (07_IMPLEMENTATION_PLAN.md) dengan perkiraan waktu
    berdasarkan kondisi VPS.
23. Sebutkan bagian spesifikasi yang menurutmu tidak realistis atau bertentangan, beserta usulan
    penggantinya. Jangan diam-diam menyimpang dari spesifikasi.
