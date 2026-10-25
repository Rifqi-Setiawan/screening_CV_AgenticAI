# 08 — Temuan dari 6 CV Asli (anonim)

Pemilik produk memberi 6 contoh CV asli. Isinya **tidak** disertakan di bundle ini (data pribadi). Yang ditulis
di sini hanya pola teknis yang ditemukan, tanpa nama, kontak, atau detail yang bisa mengidentifikasi orang.
Kalau pemilik produk menaruh file aslinya di VPS, simpan di `golden_dataset/private/` dan jangan di-commit.

## 1. Ringkasan per file

| # | Sumber pembuat | Layout | Text layer | Bahasa | Tantangan |
| --- | --- | --- | --- | --- | --- |
| 1 | Canva | 2 kolom (kiri pengalaman, kanan kontak/skill/pendidikan), foto | Ada, tapi urutan baca kacau | EN (kandidat luar negeri) | Isi kolom kanan muncul di tengah daftar pengalaman saat teks dibaca mentah; kontak berupa grafik; tanggal `01/2019 - Present` |
| 2 | Canva | 2 kolom, sidebar kiri + foto | **Tidak ada** (gambar penuh) | EN (kandidat luar negeri) | Wajib OCR; dua jabatan di bawah satu perusahaan; IPK skala 10 |
| 3 | Word → "Microsoft Print to PDF" | 1 kolom, foto, ukuran kertas Legal | Ada | EN | Bulan bahasa Indonesia di CV Inggris (`NOVEMBER 2022 – JANUARI 2023`); tahun pendidikan di kolom terpisah dari nama kampus; istilah "IPK" di CV Inggris |
| 4 | Canva | 1 kolom, 3 halaman | Ada (PDF sedikit rusak: parser memberi peringatan "Syntax Error") | ID | Pemisah perusahaan pakai huruf `l` bukan `\|` (`PT … l Bandung`); satu perusahaan, dua jabatan berurutan (promosi); skill tersebar di kalimat ("…menggunakan Laravel") |
| 5 | Word → "Microsoft Print to PDF" | 1 kolom, foto | **Tidak ada** (gambar penuh) | ID | Wajib OCR; ada tempat/tanggal lahir di baris kontak; ada bagian Sertifikasi dengan "Area kompetensi kerja"; posisi non-IT (HR/administrasi/guru) |
| 6 | Microsoft Word | 1 kolom, ramah ATS | Ada, paling bersih | EN | "Projects and Academic Activities" berisi jabatan seperti "Backend Developer \| UKM …" (kegiatan organisasi kampus, bukan kerja); bulan Indonesia di CV Inggris (`Desember 2025`); baris lokasi muncul sebelum jabatan |

## 2. Hasil uji cepat

**OCR tanpa analisis layout pada CV 2 kolom (file #2)** mencampur kolom:

```
PROFI LE 9°. [NAMA UNIVERSITAS] University
With 4 years of experience as a SAP * GPA:[angka]
```

Profil (sidebar kiri) bercampur dengan pendidikan (kolom kanan). Kesimpulan: **deteksi layout/kolom harus
dilakukan sebelum OCR**.

**OCR pada CV 1 kolom (file #5)** cukup baik, dengan salah baca kecil yang konsisten:

| Asli | Hasil OCR |
| --- | --- |
| `S1 Pendidikan` | `$1 Pendidikan` |
| `September 2021 – Desember 2024` | `September 2021 -—Desember 2024` |
| `SQ03` | `$Q03` |
| alamat beraksen Vietnam | rusak total |

Tesseract yang terpasang di lingkungan uji hanya punya bahasa `eng`. Di VPS, pasang minimal `ind` + `eng`,
atau pakai PaddleOCR.

**Ekstraksi teks langsung (file #1)**: teks ada tapi urutannya mengikuti urutan objek di PDF, bukan urutan
baca. Judul "Contact Info" dan "Relevant Skills" muncul di antara dua pengalaman kerja.

## 3. Implikasi ke sistem

1. **Cascade parsing** wajib: teks langsung → deteksi layout dua kolom → OCR untuk halaman tanpa teks → VLM
   kalau tersedia.
2. **Normalisasi OCR**: `$1`/`$2`/`$3` di dekat kata pendidikan → `S1`/`S2`/`S3`; strip ganda `-—` → `–`;
   `$Q` → `SQ` hanya di konteks kode.
3. **Parser tanggal dua bahasa** (lihat `reference/date_formats.yaml`), termasuk bulan Indonesia di CV Inggris
   dan huruf kapital.
4. **Kamus judul bagian** EN + ID (lihat `reference/section_headings.yaml`).
5. **Konteks pengalaman** wajib diklasifikasi: kerja / magang / freelance / proyek / organisasi. Jabatan di
   organisasi kampus tidak dihitung sebagai pengalaman kerja.
6. **Pemisah judul–perusahaan** bervariasi: `—`, `|`, `l`, `,`, baris baru. Jangan bergantung pada satu
   pemisah.
7. **Satu perusahaan, beberapa jabatan** (promosi): simpan sebagai entri terpisah, gabungkan rentang saat
   menghitung durasi.
8. **Skala IPK** berbeda (4,00 vs 10). IPK tidak dinilai.
9. **Data sensitif** muncul di CV asli: foto, tempat/tanggal lahir, petunjuk agama. Redaksi wajib sebelum
   embedding dan LLM.
10. **Kandidat luar negeri**: nama dan alamat beraksen (Vietnam) perlu OCR/teks yang mendukung Unicode penuh.
11. **PDF sedikit rusak** masih bisa dibaca: tangkap peringatan parser, jangan langsung menolak.
