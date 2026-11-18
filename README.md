# Rekrutmen TIG

Aplikasi untuk mengelola lowongan, menerima lamaran, dan membantu staf rekrutmen menilai kecocokan pelamar.

1. Staf membuat lowongan. Admin mengatur kriteria dan membuka formulir untuk pelamar.
2. Pelamar memakai link publik tanpa akun. CV PDF atau Word bersifat opsional. Teks CV membantu mengisi formulir, lalu pelamar bisa mengoreksi isian sebelum mengirim.
3. Worker meminta gateway model menilai data formulir yang relevan. Formulir disimpan terenkripsi. Nama, kontak, dan atribut demografis tidak digunakan untuk penilaian.
4. Staf melihat skor dan penjelasan, lalu menentukan tahap secara manual.

## Menjalankan

Gunakan Python 3.12, Node.js yang mendukung Vite 8, PostgreSQL dengan ekstensi vector untuk riwayat migrasi, dan gateway model yang kompatibel dengan API OpenAI. Pasang antiword jika perlu membaca Word .doc lama.

Salin .env.example ke .env, isi koneksi database, kunci, dan konfigurasi gateway model, lalu jalankan:

    python -m venv .venv
    .venv/bin/pip install -e ".[dev]"
    make migrate
    cd frontend && npm ci && npm run build && cd ..
    make run-api

Jalankan make run-worker di proses terpisah. Dasbor staf tersedia di /app pada port 8111. Dasbor memerlukan akun staf yang aktif. Admin dapat membagikan link formulir dari halaman lowongan.

Untuk tes, isi TEST_DATABASE_URL dengan database terisolasi yang namanya berakhiran _test, lalu jalankan make test.
