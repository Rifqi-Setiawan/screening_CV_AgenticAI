# 02. Tahap 2: Ingestion Berkas, Sanitasi & Gateway Keamanan UU PDP

Tahap 2 menangani proses penerimaan berkas pelamar (*file ingestion*), pembersihan berkas dari potensi ancaman keamanan dan manipulasi visual (*sanitization & visibility gating*), serta penegakan privasi data pribadi (*UU Perlindungan Data Pribadi / UU PDP*).

---

## 1. Pipeline Ingestion Berkas Multi-Format

Modul `src/worker/processor.py` dan `src/worker/sanitizer.py` mendukung berbagai format dokumen pelamar:
- **Dokumen Teks:** PDF (`%PDF-`), Microsoft Word DOCX (`PK\x03\x04`), DOC biner (`\xd0\xcf\x11\xe0`).
- **Arsip Batch:** Berkas ZIP yang berisi kumpulan CV pelamar diekstrak secara otomatis di memori.
- **Hasil Pindai (Scan Gambar):** Format JPG, PNG, atau TIFF melalui jalur OCR.

### Validasi Integritas Awal:
1. **Deteksi Magic Bytes:** Sistem memeriksa tanda tangan biner awal berkas, bukan sekadar melihat ekstensi nama file, untuk mencegah berkas palsu yang dinamai ulang.
2. **Pencegahan Berkas Kosong & Rusak:** Berkas dengan ukuran 0 byte atau PDF yang gagal dibuka oleh parser langsung ditandai dengan status `REJECTED` beserta alasan `EMPTY_DOCUMENT` atau `CORRUPTED_FILE`.
3. **Pemeriksaan Berkas Terenkripsi:** Berkas PDF yang dilindungi password langsung ditolak dengan status `REJECTED` (`ENCRYPTED_FILE`) agar tidak menggantung proses worker antrean.

---

## 2. Gerbang Visibilitas Visual (*Visibility Gate*)

Banyak pelamar nakal mencoba memanipulasi algoritma ATS dengan teknik **White Fonting** atau **Prompt Injection Tersembunyi**. Modul `src/worker/sanitizer.py` menjalankan analisis lapis rendah pada setiap halaman dokumen PDF menggunakan PyMuPDF:

```text
       [ Setiap Blok Teks di Halaman PDF ]
                        │
                        ▼
    ┌───────────────────────────────────────┐
    │ 1. Ukuran Font < 4.0 pt?              │ ──► Ya ──► [ FLAG: HIDDEN_TEXT ]
    └───────────────────┬───────────────────┘             (Teks Dibuang dari Prompt)
                        │ Tidak
                        ▼
    ┌───────────────────────────────────────┐
    │ 2. Warna Teks Mendekati Putih         │ ──► Ya ──► [ FLAG: HIDDEN_TEXT ]
    │    (RGB > 0.95 pada latar putih)?     │             (Teks Dibuang dari Prompt)
    └───────────────────┬───────────────────┘
                        │ Tidak
                        ▼
    ┌───────────────────────────────────────┐
    │ 3. Koordinat Bounding Box di Luar     │ ──► Ya ──► [ FLAG: OFFSCREEN_TEXT ]
    │    Batas Halaman Kertas (Off-screen)? │             (Teks Dibuang dari Prompt)
    └───────────────────┬───────────────────┘
                        │ Tidak
                        ▼
    ┌───────────────────────────────────────┐
    │ 4. Teks Mengandung Pola Prompt        │ ──► Ya ──► [ FLAG: PROMPT_INJECTION ]
    │    Injection ("System Prompt:", dll)? │             (Eskalasi ke Critic Agent)
    └───────────────────┬───────────────────┘
                        │ Tidak
                        ▼
           [ Teks Bersih & Kasat Mata ]
```

### Hasil Tindakan Sistem:
- Teks yang tidak kasat mata otomatis **dibuang dari payload evaluasi**.
- Dokumen diberi label tanda peringatan `HIDDEN_TEXT`.
- Pelamar yang terbukti menyembunyikan teks akan memicu pemanggilan **Critic Agent** pada Graph B untuk diturunkan status kelulusannya ke `MANUAL_CHECK`.

---

## 3. Modul Penyensor Data Pribadi (*PII Scrubber*)

Sesuai amanat UU Perlindungan Data Pribadi (UU PDP No. 27 Tahun 2022), data identitas pribadi kandidat yang tidak relevan dengan penilaian kompetensi harus disensor sebelum dokumen diproses lebih jauh. Modul `src/worker/redaction.py` menerapkan sensor berbasis pola (*regex scrubber*):

### A. Format Nomor Telepon Indonesia yang Disensor:
Regex komprehensif mendeteksi semua variasi penulisan nomor kontak:
```python
PHONE_PATTERN = re.compile(
    r'(?:(?:\+?62)|0)[ -.]?'          # Awalan +62, 62, atau 0
    r'(?:8[1-9][0-9])[ -.]?'          # Kode prefix seluler (0811, 0812, 0813, dst.)
    r'(?:[0-9]{3,4})[ -.]?'           # Blok tengah 3-4 digit
    r'(?:[0-9]{3,5})\b'               # Blok akhir digit
)
```
Semua nomor kontak yang cocok disensor menjadi placeholder standar: `[KONTAK_TERSEMBUNYI]`.

### B. Alamat Email & Tautan Pribadi:
Alamat email disensor menjadi `[EMAIL_TERSEMBUNYI]`, dan tautan profil sosial media pribadi disaring untuk menjaga netralitas penilaian (*Blind Review*).

---

## 4. Dua Lapis Pengaman Gateway UU PDP (*Two-Tier Privacy Gateway*)

Pada arsitektur sistem (`src/infrastructure/gateway.py`), permintaan ke model AI luar (seperti Gemini atau Claude) diproteksi dengan sistem gerbang ganda:

```text
[ Teks Bukti CV yang Mau Dikirim ke LLM ]
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ LAPIS 1: PRE-FLIGHT SANITIZER & VERIFIER              │
│ Memeriksa apakah masih ada nomor HP mentah yang lolos  │
│ dari ekstraksi tabel atau kolom sekunder PDF.          │
└──────────────────┬─────────────────────────────────────┘
                   │
         Ada nomor HP mentah?
         ├── Ya ──► [ AUTO-REDACTION ]: Ganti otomatis jadi [KONTAK_HR]
         └── Tidak ──► (Lolos Langsung)
                   │
                   ▼
┌────────────────────────────────────────────────────────┐
│ LAPIS 2: HARD SAFETY CHECK GATEWAY                     │
│ Memastikan tidak ada data kontak yang lolos ke kabel   │
│ jaringan publik.                                       │
└──────────────────┬─────────────────────────────────────┘
                   │
                   ▼
       [ Payload Aman Dikirim ke 9Router ]
```

### Manfaat Arsitektur Auto-Redaction Ini:
Pada versi awal, jika ada nomor telepon yang lolos sensor, sistem melempar `PrivacyViolationError` dan menggagalkan seluruh proses evaluasi pelamar (seperti insiden CV Denis Hanif). 

Dengan mekanisme **Auto-Redaction di Gateway**, sistem **otomatis mensterilkan teks di tempat menjadi `[KONTAK_HR]`**, sehingga:
1. Privasi pelamar **tetap terlindungi 100%** (tidak ada nomor telepon yang keluar ke model publik).
2. Pipeline proses **tetap berjalan mulus tanpa crash** atau berhenti di tengah jalan!

---

## 5. Penanganan Berkas Bermasalah & Aksi Pengguna

Pada tabel berkas di Step 2 antarmuka web, setiap berkas memiliki tombol kontrol individual di kolom **AKSI**:
- **Tombol Coba Ulang (`↺`):** Memicu pemrosesan ulang dokumen jika terjadi gangguan koneksi atau proses OCR terhenti.
- **Tombol Hapus (`🗑`):** Menghapus dokumen tunggal beserta seluruh artefak database anakannya secara bersih (*cascade delete*) tanpa perlu mengosongkan berkas pelamar lainnya.
- **Tabel Berkas Dikecualikan di Leaderboard:** Berkas yang rusak parah, duplikat, atau murni gambar tanpa layer teks dipisahkan ke dalam tabel khusus di bawah Leaderboard, transparan menampilkan alasan kendala teknisnya.
